"""Tahap 4: mencocokkan teks dengan database cek fakta (multilingual-e5-base, onnxruntime, NumPy, tanpa PyTorch).

Model dan vektor 21 ribu artikel dimuat sekali saat server menyala (`pencarian.siapkan`). Kalau berkas atau paket
tidak ada, server tetap jalan dengan pencarian nonaktif dan alasan yang jelas; /analisis lalu tidak menemukan
kecocokan. Pencarian berjalan lokal, jadi kuerinya teks bersih asli (bukan yang disamarkan untuk LLM).

Cara pakai e5 sama dengan server/alat/cek_fakta (embed.py, skema.py): kueri berawalan "query: ", artikel
berawalan "passage: " (judul tanpa awalan label + ". " + narasi), mean pooling lalu normalisasi L2, sehingga
skor cosine = perkalian titik. Fungsi yang dipakai untuk memeriksa vektor terhadap artikel disalin kecil-kecil
di sini; tes paritas menjaga keduanya tetap sama.
"""

import asyncio
import dataclasses
import hashlib
import json
import logging
import math
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path

from ..konfigurasi import Pengaturan, pengaturan as pengaturan_global
from . import klaim
from .tipe import Kandidat

log = logging.getLogger("uvicorn.error").getChild("cekhoaks")

MAKS_TOKEN_BAWAAN = 256
BERKAS_MODEL = {"fp32": "model.onnx", "int8": "model_qint8_avx512_vnni.onnx"}

STATUS_SIAP = "siap"
STATUS_BELUM = "belum_dimuat"
STATUS_NONAKTIF = "nonaktif"
STATUS_TIDAK_TERSEDIA = "tidak_tersedia"

# --- Salinan kecil dari server/alat/cek_fakta/skema.py (untuk memeriksa vektor terhadap artikel) ---

_KATA_LABEL = r"(?:SALAH|HOAX|HOAKS|HASUT|FITNAH|DISINFORMASI|MISINFORMASI|PENIPUAN|BENAR|FAKTA|FALSE)"
_AWALAN_BERKURUNG = r"\s*[\[(]\s*([^\])]+?)\s*[\])]\s*:?\s*"
_AWALAN_TANPA_TUTUP = rf"\s*\[\s*({_KATA_LABEL})\s+(?=\S)"
_AWALAN_TITIK_DUA = rf"\s*({_KATA_LABEL})\s*:\s*"
_AWALAN_TANPA_BUKA = rf"\s*({_KATA_LABEL})\s*\]\s*"


def judul_bersih(judul: str) -> str:
    """Judul tanpa awalan label ("[SALAH] ...", "HOAX: ...")."""
    judul = judul or ""
    for pola in (_AWALAN_BERKURUNG, _AWALAN_TANPA_TUTUP, _AWALAN_TITIK_DUA, _AWALAN_TANPA_BUKA):
        m = re.match(pola, judul, flags=re.I if pola != _AWALAN_BERKURUNG else 0)
        if m:
            return judul[m.end():].strip()
    return judul.strip()


def teks_passage(artikel: dict) -> str:
    judul = judul_bersih(artikel.get("judul", ""))
    narasi = artikel.get("narasi", "") or ""
    return f"passage: {judul}. {narasi}".strip() if narasi else f"passage: {judul}"


def sidik_teks(artikel: list[dict]) -> str:
    h = hashlib.sha1()
    for a in artikel:
        h.update(f"{a['id']}\n{teks_passage(a)}\n".encode("utf-8"))
    return h.hexdigest()[:16]


# --- Pemuatan dan pencarian ---


class PencarianTidakTersedia(Exception):
    """Berkas atau paket yang dibutuhkan tidak ada. Pesannya siap dicetak ke developer."""


def ram_proses_mb() -> float | None:
    """Working set proses ini dalam MB (hanya Windows; None di tempat lain atau bila gagal)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Penghitung(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.WinDLL("psapi")
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Penghitung), wintypes.DWORD]
        p = Penghitung()
        p.cb = ctypes.sizeof(p)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(p), p.cb):
            return None
        return p.WorkingSetSize / (1024 * 1024)
    except Exception:
        return None


class EmbedderE5:
    """multilingual-e5 lewat onnxruntime dan tokenizers (paket diimpor saat dibuat, bukan saat modul diimpor)."""

    def __init__(self, model: Path, tokenizer: Path, maks_token: int):
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as e:
            raise PencarianTidakTersedia(
                f"paket {e.name} belum terpasang (pip install tokenizers==0.23.2 di .venv server)"
            ) from None
        self.tok = Tokenizer.from_file(str(tokenizer))
        self.tok.enable_truncation(max_length=maks_token)
        self.tok.enable_padding(pad_id=self.tok.token_to_id("<pad>") or 1, pad_token="<pad>")
        opsi = ort.SessionOptions()
        opsi.log_severity_level = 3
        self.sesi = ort.InferenceSession(str(model), opsi, providers=["CPUExecutionProvider"])
        self.nama_masukan = {i.name for i in self.sesi.get_inputs()}

    def encode_kueri(self, teks: list[str]):
        """Matriks float32 (n, dimensi), baris ternormalisasi L2."""
        import numpy as np

        enc = self.tok.encode_batch(["query: " + t for t in teks])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        masukan = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.nama_masukan:
            masukan["token_type_ids"] = np.zeros_like(ids)
        keluar = self.sesi.run(None, masukan)[0]
        m = mask[:, :, None].astype(np.float32)
        vek = (keluar * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
        vek /= np.clip(np.linalg.norm(vek, axis=1, keepdims=True), 1e-12, None)
        return vek.astype(np.float32)


def _embedder_e5(cfg: Pengaturan, maks_token: int) -> EmbedderE5:
    model = cfg.e5_model_berkas or cfg.model_folder / f"e5-{cfg.cek_fakta_ukuran}" / BERKAS_MODEL[cfg.cek_fakta_varian]
    tokenizer = cfg.model_folder / f"e5-{cfg.cek_fakta_ukuran}" / "tokenizer.json"
    for berkas in (model, tokenizer):
        if not berkas.exists():
            raise PencarianTidakTersedia(f"berkas model tidak ditemukan: {berkas}")
    return EmbedderE5(model, tokenizer, maks_token)


def _tanggal(nilai) -> date | None:
    try:
        return date.fromisoformat(str(nilai)[:10]) if nilai else None
    except ValueError:
        return None


def rapikan_kueri(teks: str) -> str:
    return re.sub(r"\s+", " ", teks or "").strip()


class Pencarian:
    """Artikel dan vektornya di memori; pencarian cosine brute-force."""

    def __init__(self, buat_embedder: Callable[[Pengaturan, int], object] | None = None):
        self._buat_embedder = buat_embedder or _embedder_e5
        self.status = STATUS_BELUM
        self.alasan = ""
        self.jumlah = 0
        self.detik_muat = 0.0
        self.ram_tambahan_mb: float | None = None
        self.nama_model = ""
        self._artikel: list[dict] = []
        self._vektor = None
        self._embedder = None
        self._idf: dict[str, float] = {}

    def muat(self, cfg: Pengaturan | None = None) -> None:
        """Memuat artikel, vektor, dan model. Tidak pernah melempar: kegagalan menjadi status + alasan."""
        cfg = cfg or pengaturan_global
        if not cfg.cek_fakta_aktif:
            self.status, self.alasan = STATUS_NONAKTIF, "dimatikan lewat CEKHOAKS_CEKFAKTA=mati"
            return
        mulai, ram_awal = time.perf_counter(), ram_proses_mb()
        try:
            self._muat(cfg)
        except PencarianTidakTersedia as e:
            self.status, self.alasan = STATUS_TIDAK_TERSEDIA, str(e)
            return
        except Exception as e:  # server tetap harus menyala
            self.status, self.alasan = STATUS_TIDAK_TERSEDIA, f"gagal memuat ({type(e).__name__})"
            return
        self.detik_muat = time.perf_counter() - mulai
        ram_akhir = ram_proses_mb()
        self.ram_tambahan_mb = (ram_akhir - ram_awal) if ram_awal is not None and ram_akhir is not None else None
        self.status, self.alasan = STATUS_SIAP, ""

    def _muat(self, cfg: Pengaturan) -> None:
        import numpy as np

        folder = cfg.cek_fakta_folder
        jalur_artikel = folder / "artikel.jsonl"
        nama = f"vektor_{cfg.cek_fakta_ukuran}_{cfg.cek_fakta_varian}"
        jalur_vektor = cfg.e5_vektor_berkas or folder / f"{nama}.npy"
        jalur_meta = jalur_vektor.with_suffix(".json")
        for berkas in (jalur_artikel, jalur_vektor, jalur_meta):
            if not berkas.exists():
                raise PencarianTidakTersedia(f"berkas database tidak ditemukan: {berkas}")
        with open(jalur_artikel, encoding="utf-8") as f:
            artikel = [json.loads(b) for b in f if b.strip()]
        meta = json.loads(jalur_meta.read_text(encoding="utf-8"))
        vektor = np.load(jalur_vektor)
        if meta.get("jumlah") != len(artikel) or vektor.shape[0] != len(artikel) or meta.get("teks_sha1") != sidik_teks(artikel):
            raise PencarianTidakTersedia(
                "vektor tidak cocok dengan artikel.jsonl (artikel atau urutannya berubah); "
                "bangun ulang vektor dengan alat/cek_fakta/evaluasi.py"
            )
        # Panjang token kueri dari Pengaturan (terpisah dari panjang passage di meta; vektor tidak dibangun ulang).
        embedder = self._buat_embedder(cfg, int(cfg.e5_maks_token_kueri))
        self._artikel, self._vektor, self._embedder = artikel, vektor, embedder
        self._idf = hitung_idf(artikel)
        self.jumlah = len(artikel)
        self.nama_model = f"e5-{cfg.cek_fakta_ukuran} {cfg.cek_fakta_varian}"

    async def siapkan(self) -> float:
        """Memuat di thread terpisah. Mengembalikan lama pemuatan (detik)."""
        await asyncio.to_thread(self.muat)
        return self.detik_muat

    def ringkasan(self) -> str:
        if self.status == STATUS_SIAP:
            jumlah = f"{self.jumlah:,}".replace(",", ".")
            lama = f"{self.detik_muat:.1f}".replace(".", ",")
            ram = f", RAM tambahan sekitar {self.ram_tambahan_mb:,.0f} MB".replace(",", ".") if self.ram_tambahan_mb else ""
            return f"siap, {jumlah} artikel ({self.nama_model}), dimuat dalam {lama} detik{ram}"
        if self.status == STATUS_BELUM:
            return "belum dimuat"
        akhiran = "dinonaktifkan" if self.status == STATUS_NONAKTIF else "TIDAK TERSEDIA"
        return f"{akhiran}: {self.alasan}"

    def cari(self, teks: str, k: int, kecualikan_id: frozenset[str] | None = None) -> list[Kandidat]:
        """Masukan: teks. Keluaran: sampai k kandidat, skor tertinggi lebih dulu. Kosong bila tidak siap.

        `kecualikan_id` (id artikel di artikel.jsonl) hanya untuk alat evaluasi leave-one-out; server tidak pernah
        mengisinya (cari_kecocokan tidak meneruskannya) dan tidak bisa diisi lewat HTTP atau lingkungan."""
        import numpy as np

        kueri = rapikan_kueri(teks)
        if self.status != STATUS_SIAP or not kueri:
            return []
        vektor_kueri = self._embedder.encode_kueri([kueri])
        skor = (vektor_kueri @ self._vektor.T)[0]
        k = min(k, len(skor))
        if k <= 0:
            return []
        if kecualikan_id:
            skor = np.where([a.get("id") in kecualikan_id for a in self._artikel], -np.inf, skor)
        teratas = np.argpartition(-skor, k - 1)[:k]
        teratas = teratas[np.argsort(-skor[teratas])]
        if kecualikan_id:
            teratas = teratas[np.isfinite(skor[teratas])]
        kata_teks = kata_isi(kueri)
        hasil = []
        for i in teratas:
            kand = self._kandidat(int(i), float(skor[i]))
            rel = relevansi_judul(kata_teks, kand.judul, self._idf, len(self._artikel))
            hasil.append(dataclasses.replace(kand, relevansi=rel))
        return hasil

    def _kandidat(self, i: int, skor: float) -> Kandidat:
        a = self._artikel[i]
        return Kandidat(
            judul=str(a.get("judul") or ""),
            sumber=str(a.get("sumber") or ""),
            url=str(a.get("url") or ""),
            skor=max(0.0, min(1.0, skor)),
            label=str(a.get("label") or "lainnya"),
            tanggal=_tanggal(a.get("tanggal")),
            url_format_lama=bool(a.get("url_format_lama")),
            narasi=str(a.get("narasi") or ""),
        )


# Diganti pencarian palsu oleh uji.
pencarian = Pencarian()


@dataclasses.dataclass(frozen=True)
class HasilPencarian:
    """`lengkap` False bila pencarian tidak berjalan (nonaktif, tidak tersedia, atau gagal): hasil kosong lalu
    berarti "tidak diperiksa", bukan "tidak ada yang mirip"."""

    kandidat: list[Kandidat]
    lengkap: bool


async def cari_kecocokan(teks_bersih: str, cfg: Pengaturan | None = None) -> HasilPencarian:
    """Masukan: teks bersih. Keluaran: kandidat artikel mirip (skor tertinggi lebih dulu; boleh kosong).

    Kegagalan pencarian tidak menggagalkan /analisis: hasilnya kosong dan hanya jenis galatnya yang dicatat."""
    cfg = cfg or pengaturan_global
    if pencarian.status != STATUS_SIAP:
        return HasilPencarian([], False)
    try:
        return HasilPencarian(await asyncio.to_thread(pencarian.cari, teks_bersih, cfg.cocok_top_k), True)
    except Exception as e:
        log.warning("Pencarian cek fakta gagal (%s); dilanjutkan tanpa kecocokan", type(e).__name__)
        return HasilPencarian([], False)


# --- Kata isi dan relevansi leksikal ---

_KATA_BERHENTI = klaim.KATA_SAMBUNG | frozenset({
    "yang", "ini", "itu", "adalah", "juga", "telah", "sudah", "para", "sebuah", "tidak", "bukan", "lebih",
    "semua", "setiap", "setelah", "sebelum", "ketika", "saat", "hanya", "masih", "banyak", "harus", "dapat",
})


def kata_isi(teks: str) -> set[str]:
    """Kata isi huruf kecil: sedikitnya 4 huruf, atau sedikitnya 3 karakter bila memuat angka (tahun, nominal)."""
    return {
        k for k in re.findall(r"[a-z0-9]+", (teks or "").lower())
        if k not in _KATA_BERHENTI and (len(k) >= 4 or (len(k) >= 3 and any(c.isdigit() for c in k)))
    }


def _ada(kata: str, himpunan: set[str]) -> bool:
    """Kata ada di himpunan, atau salah satunya memuat yang lain (miskin / termiskin); minimal 5 huruf."""
    if kata in himpunan:
        return True
    if len(kata) < 5:
        return False
    return any(len(t) >= 5 and (kata in t or t in kata) for t in himpunan)


def hitung_idf(artikel: list[dict]) -> dict[str, float]:
    """Bobot kata dari seluruh database: kata yang jarang (nama orang, lembaga, istilah) bernilai tinggi."""
    n = len(artikel)
    df: Counter = Counter()
    for a in artikel:
        df.update(kata_isi(f"{judul_bersih(a.get('judul', ''))} {a.get('narasi', '') or ''}"))
    return {k: math.log((n + 1) / (v + 1)) for k, v in df.items()}


def _ada_toleran(kata: str, himpunan: set[str], cfg: Pengaturan) -> bool:
    """`_ada`, atau (bila `relevansi_toleransi_ocr`) kata judul sedikitnya 5 huruf tanpa angka yang berbeda paling
    banyak `relevansi_edit_pendek` (5-6 huruf) atau `relevansi_edit_panjang` (>= 7 huruf) huruf dari kata teks
    sedikitnya 5 huruf. Untuk salah eja OCR pada nama; kata pendek dan angka tetap harus persis."""
    if _ada(kata, himpunan):
        return True
    if not cfg.relevansi_toleransi_ocr or len(kata) < 5 or any(c.isdigit() for c in kata):
        return False
    from .setia import _jarak  # impor di sini: setia mengimpor modul ini

    batas = cfg.relevansi_edit_pendek if len(kata) <= 6 else cfg.relevansi_edit_panjang
    return any(
        len(t) >= 5 and abs(len(t) - len(kata)) <= batas and _jarak(kata, t) <= batas for t in himpunan
    )


def kata_judul_di_teks(kata_teks: set[str], judul: str, cfg: Pengaturan | None = None) -> int:
    """Jumlah kata isi judul artikel yang ada di teks (dengan toleransi OCR bila menyala)."""
    cfg = cfg or pengaturan_global
    return sum(1 for k in kata_isi(judul_bersih(judul)) if _ada_toleran(k, kata_teks, cfg))


def relevansi_judul(
    kata_teks: set[str], judul: str, idf: dict[str, float], n_artikel: int, cfg: Pengaturan | None = None
) -> float:
    """Bagian bobot kata isi judul artikel yang ada di teks (0-1). Judul tanpa kata isi tidak disaring (1,0)."""
    cfg = cfg or pengaturan_global
    kata_judul = kata_isi(judul_bersih(judul))
    bobot_unseen = math.log(n_artikel + 1) if n_artikel else 1.0
    total = sum(idf.get(k, bobot_unseen) for k in kata_judul)
    if not kata_judul or total <= 0:
        return 1.0
    cocok_ = sum(idf.get(k, bobot_unseen) for k in kata_judul if _ada_toleran(k, kata_teks, cfg))
    return cocok_ / total


# --- Kalimat bukti untuk ciri pernah_dibantah ---

def potong_di_batas_kata(teks: str, maks: int) -> str:
    """Memotong di batas kata tanpa menambahkan elipsis (elipsis ditambahkan tampilan, bukan bukti)."""
    if len(teks) <= maks:
        return teks
    potong = teks[:maks]
    if teks[maks] != " " and " " in potong:
        potong = potong.rsplit(" ", 1)[0]
    return potong.rstrip(" ,;:-")


MIN_KATA_SERUPA = 3


def _bersihkan_tepi(kata: str) -> str:
    return re.sub(r"^\W+|\W+$", "", kata).lower()


def _pangkas_tepi(kata: list[str], awal: int, akhir: int, acuan: set[str]) -> tuple[int, int]:
    """Membuang kata di tepi yang bukan kata isi acuan (nama akun, jam, kata pembuka). Kata pendek (<= 3 huruf,
    misalnya "Air") dipertahankan bila menempel pada kata acuan."""

    def di_acuan(i: int) -> bool:
        return 0 <= i < len(kata) and _bersihkan_tepi(kata[i]) in acuan

    while awal < akhir - 1 and not di_acuan(awal):
        if len(_bersihkan_tepi(kata[awal])) <= 3 and di_acuan(awal + 1):
            break
        awal += 1
    while akhir - 1 > awal and not di_acuan(akhir - 1):
        if len(_bersihkan_tepi(kata[akhir - 1])) <= 3 and di_acuan(akhir - 2):
            break
        akhir -= 1
    return awal, akhir


def _jendela_terbaik(
    kalimat: str, acuan_judul: set[str], acuan: set[str], maks: int
) -> tuple[str, tuple[int, int, float]]:
    """Potongan kata berurutan dari `kalimat` (persis dari teks, panjang <= maks karakter) yang paling mirip
    artikel. Nilai: (kata isi judul yang sama, kata isi judul+narasi yang sama, rasio); kata judul didahulukan
    karena narasi artikel sering memuat seluruh pesan berantai. Seri dimenangkan jendela yang paling awal.
    Kata di tepi yang bukan kata isi acuan dibuang."""
    kata = kalimat.split()

    def nilai(awal: int, akhir: int) -> tuple[int, int, float]:
        isi = kata_isi(" ".join(kata[awal:akhir]))
        return len(isi & acuan_judul), len(isi & acuan), len(isi & acuan) / len(isi) if isi else 0.0

    if len(kalimat) <= maks:  # muat utuh: hanya tepinya yang dirapikan
        n = nilai(0, len(kata))
        awal, akhir = _pangkas_tepi(kata, 0, len(kata), acuan_judul if n[0] >= MIN_KATA_SERUPA else acuan)
        return " ".join(kata[awal:akhir]), n
    terbaik, nilai_terbaik = (0, len(kata)), (0, 0, 0.0)
    for awal in range(len(kata)):
        akhir, panjang = awal, 0
        while akhir < len(kata) and panjang + len(kata[akhir]) + (1 if akhir > awal else 0) <= maks:
            panjang += len(kata[akhir]) + (1 if akhir > awal else 0)
            akhir += 1
        if akhir == awal:
            akhir = awal + 1  # satu kata yang lebih panjang dari batas
        n = nilai(awal, akhir)
        if n > nilai_terbaik:
            terbaik, nilai_terbaik = (awal, akhir), n
        if akhir == len(kata):
            break  # jendela berikutnya hanya lebih pendek dari ini di ekor yang sama
    pangkas = acuan_judul if nilai_terbaik[0] >= MIN_KATA_SERUPA else acuan
    awal, akhir = _pangkas_tepi(kata, *terbaik, pangkas)
    return " ".join(kata[awal:akhir]), nilai_terbaik


def kalimat_serupa(teks_bersih: str, artikel: Kandidat, cfg: Pengaturan | None = None) -> str:
    """Potongan teks bersih yang menjadi bukti `pernah_dibantah`: bagian teks dengan kata isi terbanyak yang sama
    dengan judul (lalu narasi) artikel, sedikitnya 3 kata. Kalimat yang lebih panjang dari batas bukti (misalnya
    teks kapital tanpa titik) tidak dipotong dari awalnya, tetapi dicari jendela kata yang paling mirip dengan
    artikel. Kalau tidak ada yang cukup mirip: kalimat klaim heuristik, lalu baris pertama.
    Selalu potongan persis dari teks (modulo spasi), tanpa elipsis, supaya bisa disorot di layar."""
    cfg = cfg or pengaturan_global
    maks = cfg.ciri_bukti_maks_karakter
    acuan_judul = kata_isi(judul_bersih(artikel.judul))
    acuan = acuan_judul | kata_isi(artikel.narasi)
    terbaik, nilai_terbaik = "", (0, 0, 0.0)
    for kalimat in klaim.pisah_kalimat(teks_bersih, cfg):
        kalimat = re.sub(r"\s+", " ", kalimat).strip()
        potongan, nilai = _jendela_terbaik(kalimat, acuan_judul, acuan, maks)
        if nilai[1] >= MIN_KATA_SERUPA and nilai > nilai_terbaik:
            terbaik, nilai_terbaik = potongan, nilai
    if not terbaik:
        terbaik = klaim.klaim_heuristik(teks_bersih, cfg=cfg).rstrip("…").strip()
    if not terbaik:
        terbaik = next((b.strip() for b in teks_bersih.splitlines() if b.strip()), "")
    return potong_di_batas_kata(re.sub(r"\s+", " ", terbaik).strip(), maks)
