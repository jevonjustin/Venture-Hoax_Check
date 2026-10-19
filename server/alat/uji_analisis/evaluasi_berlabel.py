"""Evaluasi data berlabel (Sesi 5.6): menjalankan pipeline /analisis yang sama dengan server pada gambar di
server\\data_lokal\\evaluasi\\, dengan cache per gambar supaya OCR, pencarian, dan LLM tidak diulang.

Pipeline TIDAK diduplikasi: alat memanggil orkestrator.jalankan, dan hanya mengganti tiga tahap berat dengan
pembungkus ber-cache (pembaca OCR, pencarian e5, llm.analisis). Penyamaran teks untuk LLM tetap dilakukan
orkestrator (samarkan.py) sebelum teks sampai ke pembungkus LLM; alat tidak punya jalur lain ke LLM.

Perintah (dari folder server, venv server):
  kumpul      mengisi cache dev dan uji. Tidak mencetak tingkat apa pun. Tahap: ocr, cari, llm.
  nilai       --set dev (boleh berulang) atau --set uji --final (sekali; ditolak kali kedua kecuali --paksa).
  ringkas-token  mencetak penghitung panggilan dan token (per tanggal lokal) tanpa memanggil apa pun.
  segel-awal  menyimpan hasil tingkat kode awal untuk set uji (tanpa ringkasan) ke cache\\hasil_awal_uji.json.

LLM: hanya Groq (cadangan Gemini tidak pernah dipakai), jeda minimal 8 detik antar percobaan HTTP, setiap percobaan
dihitung di cache\\jumlah_panggilan_llm.json, --maks-panggilan wajib, berhenti (dengan cache sebagai checkpoint) bila
sisa kuota harian rendah atau 3 kali 429 beruntun. Tidak ada teks yang ditulis ke log; hanya id dan angka.
Laporan ke server\\data_lokal\\hasil_analisis\\<nama>.md memuat id, kategori, label, dan skor; tanpa teks gambar.
Lihat README.md di folder ini untuk contoh perintah.
"""

import argparse
import asyncio
import csv
import dataclasses
import hashlib
import itertools
import json
import os
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tahap_a import SERVER, sebagai_png, tidak_putus  # noqa: E402

sys.path.insert(0, str(SERVER))
from app import konfigurasi  # noqa: E402
from app.galat import GalatApi  # noqa: E402
from app.pipeline import baca, cocok, llm, tautan  # noqa: E402
from app.pipeline.tipe import BarisTeks, HasilBaca, Kandidat, KandidatLLM, Konteks  # noqa: E402

# --- Lokasi (diganti uji) ---


@dataclasses.dataclass(frozen=True)
class Jalur:
    akar: Path

    @property
    def metadata(self) -> Path:
        return self.akar / "metadata.csv"

    @property
    def gambar(self) -> Path:
        return self.akar / "gambar"

    @property
    def cache(self) -> Path:
        return self.akar / "cache"

    @property
    def beku(self) -> Path:
        return self.akar / "uji_beku.sha256"

    @property
    def penanda_uji(self) -> Path:
        return self.cache / "uji_sudah_dinilai.json"

    @property
    def hasil_awal(self) -> Path:
        return self.cache / "hasil_awal_uji.json"

    @property
    def penghitung(self) -> Path:
        return self.cache / "jumlah_panggilan_llm.json"

    @property
    def checkpoint(self) -> Path:
        return self.cache / "checkpoint_kumpul.json"


def jalur_dari(akar: Path) -> Jalur:
    return Jalur(Path(akar))


J = jalur_dari(SERVER / "data_lokal" / "evaluasi")
FOLDER_HASIL = SERVER / "data_lokal" / "hasil_analisis"
LOG_BAWAAN = Path(r"C:\Users\User\AndroidStudioProjects\CekHoaks\.orkestrasi\logs\evaluasi_berlabel.log")

# --- Konstanta ---

LABEL_SAH = ("kuat", "hati_hati", "tidak_ditemukan", "teks_tidak_terbaca")
LABEL_POSITIF = ("kuat", "hati_hati")
KATEGORI_SAH = (
    "screenshot_asli", "positif_db", "penipuan", "satir", "berita", "edukasi", "pengumuman", "obrolan", "promosi_sah",
)
KATEGORI_NEGATIF = ("berita", "edukasi", "pengumuman", "obrolan", "promosi_sah")
KATEGORI_POSITIF = ("positif_db", "penipuan", "satir", "screenshot_asli")
LEBAR_CACHE_CARI = 20  # kandidat per gambar di cache pencarian, supaya ambang dan top_k bisa disapu ulang
JEDA_LLM_MINIMUM = 8.0
SISA_PERMINTAAN_MINIMUM = 25  # berhenti bila sisa permintaan harian Groq di bawah ini
SISA_TOKEN_MINIMUM = 1500  # sisa token per menit di bawah ini: tunggu reset (batas 65 detik)
MAKS_429_BERUNTUN = 3
MAKS_TUNGGU_429 = 60.0
PERKIRAAN_TOKEN_BAWAAN = 1200  # token per panggilan bila belum ada data
POLA_429_HARIAN = re.compile(r"per day|\bTPD\b|\bRPD\b", re.IGNORECASE)
HASIL_LAIN = ("cache_kosong", "galat")

# Ambang yang boleh ditimpa lewat --ambang dan --sapu (nama bebas atau nama bidang Pengaturan); bawaan = nilai server.
ALIAS_AMBANG = {
    "skor_kuat": "ambang_cocok", "skor_cocok": "ambang_cocok", "skor_mirip": "ambang_mirip",
    "relevansi": "relevansi_minimum", "selisih": "selisih_konflik", "satir": "satir_hati_hati",
    "top_k": "cocok_top_k", "teks": "ambang_teks_karakter", "kesetiaan": "klaim_kesetiaan_minimum",
    # Sesi 5.6 (T7): perilaku baru di balik Pengaturan, bawaan mati.
    "toleransi_ocr": "relevansi_toleransi_ocr", "kombinasi": "kuat_kombinasi_aktif",
    "kombinasi_skor": "kuat_kombinasi_skor", "kombinasi_relevansi": "kuat_kombinasi_relevansi",
    "kombinasi_kata": "kuat_kombinasi_min_kata", "kesetiaan_ketat": "periksa_kesetiaan_klaim",
    "lolos": "relevansi_lolos_skor",
}
AMBANG_BOLEH = frozenset({
    "ambang_cocok", "ambang_mirip", "relevansi_minimum", "selisih_konflik", "satir_hati_hati", "cocok_top_k",
    "cek_fakta_maks", "ambang_teks_karakter", "klaim_kesetiaan_minimum", "klaim_skor_minimum",
    "relevansi_toleransi_ocr", "relevansi_edit_pendek", "relevansi_edit_panjang", "kuat_kombinasi_aktif",
    "kuat_kombinasi_skor", "kuat_kombinasi_relevansi", "kuat_kombinasi_min_kata", "periksa_kesetiaan_klaim",
    "relevansi_lolos_skor",
})


class GalatAlat(Exception):
    """Kesalahan pemakaian alat; pesannya siap dicetak."""


class CacheKosong(Exception):
    """Tahap dimatikan atau tidak boleh memanggil sumber asli dan cache-nya belum ada."""


class BatasPanggilan(Exception):
    """--maks-panggilan tercapai: tidak ada percobaan HTTP lagi."""


class TransportDitolak(Exception):
    """Transport hanya boleh ke Groq."""


# --- Berkas bantu ---


def sekarang() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_teks(t: str) -> str:
    return sha_bytes(t.encode("utf-8"))


def sha_berkas(jalur: Path) -> str:
    h = hashlib.sha256()
    with open(jalur, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def baca_json(jalur: Path):
    """None bila berkas tidak ada atau rusak."""
    try:
        return json.loads(jalur.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def tulis_json(jalur: Path, isi) -> None:
    jalur.parent.mkdir(parents=True, exist_ok=True)
    sementara = jalur.with_name(jalur.name + ".tmp")
    sementara.write_text(json.dumps(isi, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(sementara, jalur)


class Pencatat:
    """Log proses panjang: PID di awal lalu progres berkala. Hanya id dan angka."""

    def __init__(self, jalur: Path | None, gema: bool = True):
        self.jalur, self.gema = jalur, gema
        if jalur:
            jalur.parent.mkdir(parents=True, exist_ok=True)

    def tulis(self, pesan: str) -> None:
        if self.gema:
            print(pesan, flush=True)
        if self.jalur:
            with open(self.jalur, "a", encoding="utf-8") as f:
                f.write(f"{sekarang()} {pesan}\n")


# --- Metadata ---


@dataclasses.dataclass(frozen=True)
class Baris:
    id: str
    berkas: str
    set: str
    label_harapan: str
    label_boleh: tuple[str, ...]
    kategori: str
    sintetis: bool
    id_artikel_sumber: str


def baca_metadata() -> list[Baris]:
    if not J.metadata.exists():
        raise GalatAlat(f"metadata tidak ditemukan: {J.metadata}")
    hasil, terlihat = [], set()
    with open(J.metadata, encoding="utf-8-sig", newline="") as f:
        for no, b in enumerate(csv.DictReader(f), start=2):
            def pesan(x):
                return GalatAlat(f"metadata baris {no}: {x}")

            id_ = (b.get("id") or "").strip()
            boleh = tuple(x.strip() for x in (b.get("label_boleh") or "").split(";") if x.strip())
            baris = Baris(
                id=id_, berkas=(b.get("berkas") or "").strip(), set=(b.get("set") or "").strip(),
                label_harapan=(b.get("label_harapan") or "").strip(), label_boleh=boleh,
                kategori=(b.get("kategori") or "").strip(), sintetis=(b.get("sintetis") or "").strip() == "ya",
                id_artikel_sumber=(b.get("id_artikel_sumber") or "").strip(),
            )
            if not id_ or id_ in terlihat:
                raise pesan("id kosong atau ganda")
            terlihat.add(id_)
            if baris.set not in ("dev", "uji"):
                raise pesan(f"set tidak sah ({baris.set!r}) untuk {id_}")
            if baris.label_harapan not in LABEL_SAH or any(x not in LABEL_SAH for x in boleh):
                raise pesan(f"label tidak sah untuk {id_}")
            if baris.kategori not in KATEGORI_SAH:
                raise pesan(f"kategori tidak sah untuk {id_}")
            if (b.get("sintetis") or "").strip() not in ("ya", "tidak"):
                raise pesan(f"sintetis harus ya atau tidak untuk {id_}")
            hasil.append(baris)
    return hasil


def pilih_set(semua: list[Baris], nama: str) -> list[Baris]:
    return [b for b in semua if nama == "semua" or b.set == nama]


# --- Segel set uji ---


def verifikasi_beku(baris_uji: list[Baris]) -> None:
    """Memeriksa uji_beku.sha256 terhadap gambar set uji. Melempar GalatAlat bila tidak cocok.

    Format yang dikenali: baris gaya sha256sum ("<hash>  <berkas>", jalur boleh memuat gambar/), atau satu hash
    tunggal (sha256 dari hash gambar uji yang diurutkan, satu per baris, diakhiri baris baru)."""
    if not J.beku.exists():
        raise GalatAlat(f"{J.beku.name} tidak ada: set uji belum dibekukan")
    isi = [b.strip() for b in J.beku.read_text(encoding="utf-8").splitlines() if b.strip() and not b.startswith("#")]
    sha_gambar = {b.berkas: sha_berkas(J.gambar / b.berkas) for b in baris_uji}
    tunggal = len(isi) == 1 and len(isi[0].split()) == 1
    if tunggal:
        gabungan = sha_teks("\n".join(sorted(sha_gambar.values())) + "\n")
        if isi[0].lower() != gabungan:
            raise GalatAlat("uji_beku.sha256 tidak cocok dengan gambar set uji (hash tunggal)")
        return
    tercatat: dict[str, str] = {}
    for baris in isi:
        bagian = baris.split(None, 1)
        if len(bagian) != 2:
            raise GalatAlat("format uji_beku.sha256 tidak dikenali")
        nama = bagian[1].strip().lstrip("*").replace("\\", "/")
        nama = nama[len("gambar/"):] if nama.startswith("gambar/") else nama
        tercatat[nama] = bagian[0].lower()
    for berkas, sha in sha_gambar.items():
        if tercatat.get(berkas) != sha:
            raise GalatAlat(f"set uji berubah atau tidak tercatat di uji_beku.sha256: {berkas}")


# --- Penghitung panggilan LLM ---


_kunci_penghitung = threading.Lock()


def jumlah_panggilan_total() -> int:
    d = baca_json(J.penghitung)
    return int(d.get("total", 0)) if isinstance(d, dict) else 0


def hari_ini() -> str:
    """Tanggal lokal (YYYY-MM-DD) untuk penghitung harian."""
    return date.today().isoformat()


def _muat_penghitung() -> dict:
    if J.penghitung.exists():
        d = baca_json(J.penghitung)
        if not isinstance(d, dict) or "total" not in d:
            raise GalatAlat(f"{J.penghitung.name} rusak; perbaiki sebelum melanjutkan")
        return d
    return {"total": 0}


def _entri_hari(d: dict, hari: str) -> dict:
    e = d.setdefault("per_hari", {}).setdefault(hari, {})
    for k in ("panggilan", "token", "prompt", "completion", "panggilan_ber_token"):
        e.setdefault(k, 0)
    return e


def tambah_penghitung(n: int = 1) -> int:
    """Menambah penghitung kumulatif di disk (satu percobaan HTTP = 1) dan penghitung panggilan hari ini.
    Berkas rusak tidak ditimpa."""
    with _kunci_penghitung:
        d = _muat_penghitung()
        d["total"] = int(d["total"]) + n
        _entri_hari(d, hari_ini())["panggilan"] += n
        d["diperbarui"] = sekarang()
        tulis_json(J.penghitung, d)
        return d["total"]


def catat_token(prompt: int, completion: int, total: int) -> None:
    """Menambah token hari ini dari satu balasan sukses (usage Groq)."""
    with _kunci_penghitung:
        d = _muat_penghitung()
        e = _entri_hari(d, hari_ini())
        e["token"] += total
        e["prompt"] += prompt
        e["completion"] += completion
        e["panggilan_ber_token"] += 1
        d["diperbarui"] = sekarang()
        tulis_json(J.penghitung, d)


def token_hari_ini() -> int:
    d = baca_json(J.penghitung)
    if not isinstance(d, dict):
        return 0
    return int(d.get("per_hari", {}).get(hari_ini(), {}).get("token", 0))


def rata_token_panggilan() -> int:
    """Rata-rata token per panggilan sukses sepanjang catatan; PERKIRAAN_TOKEN_BAWAAN bila belum ada data."""
    d = baca_json(J.penghitung)
    token = n = 0
    if isinstance(d, dict):
        for e in d.get("per_hari", {}).values():
            token += int(e.get("token", 0))
            n += int(e.get("panggilan_ber_token", 0))
    return round(token / n) if n else PERKIRAAN_TOKEN_BAWAAN


def baca_usage(isi: str) -> dict | None:
    """{"prompt", "completion", "total"} dari balasan 200 Groq; None bila tidak ada."""
    try:
        u = json.loads(isi)["usage"]
        p, c = int(u["prompt_tokens"]), int(u["completion_tokens"])
        return {"prompt": p, "completion": c, "total": int(u.get("total_tokens", p + c))}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def ringkasan_token_teks(sesi_panggilan: int | None = None, sesi_token: int | None = None) -> list[str]:
    d = baca_json(J.penghitung)
    e = d.get("per_hari", {}).get(hari_ini(), {}) if isinstance(d, dict) else {}
    baris = []
    if sesi_panggilan is not None:
        baris.append(f"panggilan sesi ini: {sesi_panggilan}; token sesi ini: {sesi_token}")
    baris.append(
        f"hari ini ({hari_ini()}): panggilan {e.get('panggilan', 0)}, token {e.get('token', 0)}; "
        f"rata-rata token per panggilan: {rata_token_panggilan()}"
    )
    return baris


def _header_kuota(h) -> dict[str, str]:
    try:
        return {k.lower(): str(v)[:40] for k, v in h.items() if k.lower().startswith("x-ratelimit") or k.lower() == "retry-after"}
    except Exception:
        return {}


def _angka_bulat(nilai) -> int | None:
    try:
        return int(float(str(nilai).strip()))
    except (ValueError, TypeError):
        return None


class TransportGroq:
    """Transport llm.analisis: hanya Groq, jeda minimal antar percobaan, menghitung setiap percobaan HTTP, batas
    keras, dan membaca header sisa kuota. Mengembalikan (status, isi, header terpilih) seperti transport server."""

    def __init__(self, jeda: float, maks: int | None, tidur=time.sleep, jam=time.monotonic, kirim=None):
        self.jeda, self.maks, self.tidur, self.jam = jeda, maks, tidur, jam
        self._kirim = kirim or self._kirim_urllib
        self.sesi = 0
        self.kuota: dict = {}
        self.body_ok: str | None = None
        self.usage_ok: dict | None = None
        self.token_sesi = 0
        self.harian = False  # 429 batas HARIAN (TPD/RPD) terdeteksi
        self._terakhir: float | None = None
        self._kunci = threading.Lock()

    def habis(self) -> bool:
        return self.maks is not None and self.sesi >= self.maks

    @staticmethod
    def _kirim_urllib(penyedia, badan, kunci, timeout):
        permintaan = urllib.request.Request(
            f"{penyedia.url}/chat/completions", data=json.dumps(badan).encode("utf-8"),
            headers={"Authorization": f"Bearer {kunci}", "Content-Type": "application/json", "User-Agent": llm.USER_AGENT},
            method="POST",
        )
        try:
            with urllib.request.urlopen(permintaan, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", errors="replace"), _header_kuota(r.headers)
        except urllib.error.HTTPError as e:
            try:
                isi = e.read(llm.MAKS_BADAN_GALAT).decode("utf-8", errors="replace")
            except Exception:
                isi = ""
            return e.code, isi, _header_kuota(e.headers)
        except Exception:
            raise llm.GagalJaringan from None

    def __call__(self, penyedia, badan, kunci, timeout):
        if penyedia.nama != llm.GROQ.nama:
            raise TransportDitolak
        with self._kunci:
            if self.habis():
                raise BatasPanggilan
            if self._terakhir is not None:
                sisa = self.jeda - (self.jam() - self._terakhir)
                if sisa > 0:
                    self.tidur(sisa)
            self.sesi += 1
            tambah_penghitung()
            try:
                status, isi, header = self._kirim(penyedia, badan, kunci, timeout)
            finally:
                self._terakhir = self.jam()
        self._catat_kuota(header)
        if status == 200:
            self.body_ok = isi
            self.usage_ok = baca_usage(isi)
            if self.usage_ok:
                self.token_sesi += self.usage_ok["total"]
                catat_token(self.usage_ok["prompt"], self.usage_ok["completion"], self.usage_ok["total"])
        elif status == 429 and POLA_429_HARIAN.search(isi or ""):
            self.harian = True
        return status, isi, {k: v for k, v in header.items() if k in llm.HEADER_DISIMPAN}

    def _catat_kuota(self, header: dict) -> None:
        sisa_req = _angka_bulat(header.get("x-ratelimit-remaining-requests"))
        sisa_tok = _angka_bulat(header.get("x-ratelimit-remaining-tokens"))
        if sisa_req is not None:
            self.kuota["sisa_permintaan"] = sisa_req
        if sisa_tok is not None:
            self.kuota["sisa_token"] = sisa_tok
            self.kuota["reset_token"] = llm._durasi_detik(header.get("x-ratelimit-reset-tokens", ""))


# --- Pembungkus tahap ber-cache ---


class PembacaBerCache:
    """Pengganti baca.pembaca: OCR dibaca dari cache; hanya memanggil pembaca asli bila `boleh`."""

    def __init__(self, asli, boleh: bool):
        self.asli, self.boleh, self.sha = asli, boleh, ""
        self.baru = 0

    async def siapkan(self) -> float:
        return 0.0

    @staticmethod
    def versi() -> str:
        try:
            return baca.versi_mesin()
        except Exception:
            return "tidak-diketahui"

    def jalur(self) -> Path:
        return J.cache / "ocr" / f"{self.sha}.json"

    async def baca(self, data: bytes) -> HasilBaca:
        c = baca_json(self.jalur())
        if isinstance(c, dict) and c.get("versi") == self.versi() and "baris" in c:
            baris = [BarisTeks(b["teks"], tuple(tuple(t) for t in b["kotak"]), b["skor"]) for b in c["baris"]]
            return HasilBaca(c["teks"], baris)
        if not self.boleh:
            raise CacheKosong("ocr")
        hasil = await self.asli.baca(data)
        tulis_json(self.jalur(), {
            "sha_gambar": self.sha, "versi": self.versi(), "teks": hasil.teks,
            "baris": [{"teks": b.teks, "kotak": [list(t) for t in b.kotak], "skor": b.skor} for b in hasil.baris],
        })
        self.baru += 1
        return hasil

    def simpan_teks_bersih(self, teks_bersih: str) -> None:
        c = baca_json(self.jalur())
        if isinstance(c, dict) and c.get("teks_bersih") != teks_bersih:
            c["teks_bersih"] = teks_bersih
            tulis_json(self.jalur(), c)


def _kandidat_ke_dict(k: Kandidat, id_: str | None) -> dict:
    return {
        "id": id_, "skor": k.skor, "relevansi": k.relevansi, "judul": k.judul, "sumber": k.sumber, "url": k.url,
        "label": k.label, "tanggal": k.tanggal.isoformat() if k.tanggal else None,
        "url_format_lama": k.url_format_lama, "narasi": k.narasi,
    }


def _dict_ke_kandidat(d: dict) -> Kandidat:
    return Kandidat(
        judul=d["judul"], sumber=d["sumber"], url=d["url"], skor=d["skor"], label=d["label"],
        tanggal=date.fromisoformat(d["tanggal"]) if d.get("tanggal") else None,
        url_format_lama=bool(d.get("url_format_lama")), narasi=d.get("narasi", ""), relevansi=d.get("relevansi", 1.0),
    )


class PencarianBerCache:
    """Pengganti cocok.pencarian. Cache: top-20 kandidat lengkap dengan skor, kunci = gambar + isi kueri + versi
    database. Mode `loo` mengeluarkan artikel id_artikel_sumber (hook Pencarian.cari(kecualikan_id=...))."""

    status = cocok.STATUS_SIAP
    alasan = ""

    def __init__(self, asli, boleh: bool):
        self.asli, self.boleh = asli, boleh
        self.sha, self.mode, self.id_sumber = "", "biasa", ""
        self.kosong = False
        self.terakhir: list[dict] = []
        self.baru = 0
        self.versi_tetap: str | None = None
        self._peta: dict | None = None
        self._idf: tuple[dict[str, float], int] | None = None

    async def siapkan(self) -> float:
        return 0.0

    def ringkasan(self) -> str:
        return "siap (cache evaluasi)"

    def versi_db(self) -> str:
        if self.versi_tetap is not None:
            return self.versi_tetap
        cfg = konfigurasi.pengaturan
        meta = baca_json(
            cfg.e5_vektor_berkas.with_suffix(".json") if cfg.e5_vektor_berkas
            else cfg.cek_fakta_folder / f"vektor_{cfg.cek_fakta_ukuran}_{cfg.cek_fakta_varian}.json"
        )
        if not isinstance(meta, dict):
            return "tanpa-meta"
        # Varian model, berkas model/vektor khusus, dan panjang token kueri ikut kunci: sapuan 256 vs 512 dan
        # fp32 vs int8 tersimpan terpisah.
        model = cfg.e5_model_berkas.name if cfg.e5_model_berkas else "bawaan"
        model += f"|{cfg.e5_vektor_berkas.name}" if cfg.e5_vektor_berkas else ""
        return (
            f"{meta.get('teks_sha1')}|e5-{cfg.cek_fakta_ukuran}-{cfg.cek_fakta_varian}|{meta.get('maks_token')}"
            f"|kueri{cfg.e5_maks_token_kueri}|{model}"
        )

    @staticmethod
    def sufiks_varian() -> str:
        """Akhiran nama berkas cache bagi konfigurasi e5 selain bawaan (fp32, kueri 256, model bawaan), supaya
        berkas varian lain tidak menimpa berkas bawaan. Berakhir `__loo`/`__biasa` + sufiks sebelum `.json`."""
        cfg, dasar = konfigurasi.pengaturan, konfigurasi.Pengaturan()
        bagian = []
        if cfg.cek_fakta_varian != dasar.cek_fakta_varian:
            bagian.append(cfg.cek_fakta_varian)
        if cfg.e5_maks_token_kueri != dasar.e5_maks_token_kueri:
            bagian.append(f"k{cfg.e5_maks_token_kueri}")
        if cfg.e5_model_berkas:
            bagian.append(cfg.e5_model_berkas.stem)
        if cfg.e5_vektor_berkas:
            bagian.append(cfg.e5_vektor_berkas.stem)
        return "".join(f"_{b}" for b in bagian)

    def _id(self, k: Kandidat) -> str | None:
        if self._peta is None:
            self._peta = {}
            for a in getattr(self.asli, "_artikel", []) or []:
                self._peta.setdefault((str(a.get("url") or ""), str(a.get("judul") or "")), a.get("id"))
        return self._peta.get((k.url, k.judul))

    def idf(self) -> tuple[dict[str, float], int]:
        """IDF dan jumlah artikel dari database (sama dengan pencarian server); dimuat sekali bila perlu."""
        if self._idf is None:
            artikel = getattr(self.asli, "_artikel", None) or []
            if not artikel:
                jalur = konfigurasi.pengaturan.cek_fakta_folder / "artikel.jsonl"
                with open(jalur, encoding="utf-8") as f:
                    artikel = [json.loads(b) for b in f if b.strip()]
            self._idf = (cocok.hitung_idf(artikel), len(artikel))
        return self._idf

    def hitung_ulang_relevansi(self, kueri: str, hasil: list[dict]) -> list[dict]:
        """Relevansi di cache dihitung dengan Pengaturan saat kumpul (bisa profil lain), jadi selalu dihitung ulang
        dari judul kandidat dan kueri dengan Pengaturan sekarang (fungsi cocok.relevansi_judul yang sama)."""
        cfg = konfigurasi.pengaturan
        idf, n = self.idf()
        kata_teks = cocok.kata_isi(kueri)
        return [{**d, "relevansi": cocok.relevansi_judul(kata_teks, d["judul"], idf, n, cfg)} for d in hasil]

    def mode_efektif(self) -> str:
        return "loo" if self.mode == "loo" and self.id_sumber else "biasa"

    def _muat_asli(self) -> None:
        if self.asli.status != cocok.STATUS_SIAP and hasattr(self.asli, "muat"):
            self.asli.muat()
        if self.asli.status != cocok.STATUS_SIAP:
            raise CacheKosong(f"pencarian tidak siap: {self.asli.ringkasan()}")

    def cari(self, teks: str, k: int) -> list[Kandidat]:
        kueri = cocok.rapikan_kueri(teks)
        if not kueri:
            self.terakhir = []
            return []
        mode, versi, sha_kueri = self.mode_efektif(), self.versi_db(), sha_teks(kueri)
        berkas = J.cache / "cari" / f"{self.sha}__{mode}{self.sufiks_varian()}.json"
        c = baca_json(berkas)
        if isinstance(c, dict) and c.get("versi") == versi and c.get("kueri_sha") == sha_kueri and c.get("lebar") == LEBAR_CACHE_CARI:
            hasil = c["hasil"]
        else:
            if not self.boleh:
                self.kosong = True
                raise CacheKosong("cari")
            self._muat_asli()
            if mode == "loo":
                kandidat = self.asli.cari(teks, LEBAR_CACHE_CARI, kecualikan_id=frozenset({self.id_sumber}))
            else:
                kandidat = self.asli.cari(teks, LEBAR_CACHE_CARI)
            hasil = [_kandidat_ke_dict(x, self._id(x)) for x in kandidat]
            tulis_json(berkas, {
                "sha_gambar": self.sha, "mode": mode, "versi": versi, "kueri_sha": sha_kueri, "lebar": LEBAR_CACHE_CARI,
                "kecualikan": [self.id_sumber] if mode == "loo" else [], "hasil": hasil,
            })
            self.baru += 1
        hasil = self.hitung_ulang_relevansi(kueri, hasil)
        self.terakhir = hasil
        return [_dict_ke_kandidat(d) for d in hasil[:k]]


class LLMBerCache:
    """Pengganti llm.analisis. Menerima teks yang SUDAH disamarkan oleh orkestrator. LLM tidak menerima hasil
    pencarian, jadi satu cache dipakai bersama mode biasa dan loo. Kunci cache: hash teks yang dikirim + model +
    hash badan permintaan (prompt, skema, parameter). Hanya hasil sukses yang disimpan."""

    def __init__(
        self, asli, boleh: bool, transport: TransportGroq | None = None, jalan: int = 1, tanpa: bool = False,
        sisa_min: int = SISA_PERMINTAAN_MINIMUM, pencatat: Pencatat | None = None, tidur=time.sleep,
        maks_token_hari: int | None = None,
    ):
        self.asli, self.boleh, self.transport, self.jalan, self.tanpa = asli, boleh, transport, jalan, tanpa
        self.sisa_min, self.pencatat, self.tidur = sisa_min, pencatat, tidur
        self.maks_token_hari = maks_token_hari
        self.sha = ""
        self.samar_terakhir: str | None = None
        self.kosong = False
        self.berhenti = ""
        self.beruntun_429 = 0
        self.baru = 0
        self.gagal = 0

    def jalur(self) -> Path:
        return J.cache / "llm" / f"{self.sha}.json"

    def cfg_llm(self, cfg=None) -> konfigurasi.Pengaturan:
        """Salinan pengaturan untuk panggilan sungguhan: tanpa Gemini, tanpa ulang 429 cepat (jeda diatur
        transport), dan batas waktu diperlebar sebesar jeda karena transport tidur di dalam batas itu."""
        dasar = cfg or konfigurasi.pengaturan
        jeda = self.transport.jeda if self.transport else 0.0
        return dataclasses.replace(
            dasar, llm_aktif=True, llm_cadangan_aktif=False, llm_tunggu_429_maks=0.0,
            llm_timeout_groq=dasar.llm_timeout_groq + jeda, llm_anggaran_total=dasar.llm_anggaran_total + 2 * jeda,
        )

    def kunci(self, teks_samar: str) -> dict:
        badan = llm._badan(llm.GROQ, "", self.cfg_llm())
        return {
            "teks_sha": sha_teks(teks_samar), "model": llm.GROQ.model,
            "prompt_sha": sha_teks(json.dumps(badan, sort_keys=True, ensure_ascii=False))[:16],
        }

    @staticmethod
    def _hasil(j: dict) -> llm.HasilLLM:
        return llm.HasilLLM(
            j["klaim_utama"], [KandidatLLM(c["id"], list(c["kutipan"])) for c in j["kandidat"]], j["penyedia"],
            int(j.get("durasi_ms", 0)), int(j.get("percobaan", 1)),
        )

    def ada_cache(self, teks_samar: str, jalan: int) -> bool:
        e = baca_json(self.jalur())
        return isinstance(e, dict) and e.get("kunci") == self.kunci(teks_samar) and str(jalan) in e.get("jalan", {})

    async def analisis(self, teks_samar, cfg=None, transport=None, jejak=None):
        if self.tanpa:
            return None
        self.samar_terakhir = teks_samar
        e = baca_json(self.jalur())
        kunci = self.kunci(teks_samar)
        if isinstance(e, dict) and e.get("kunci") == kunci and str(self.jalan) in e.get("jalan", {}):
            return self._hasil(e["jalan"][str(self.jalan)])
        if not self.boleh:
            self.kosong = True
            return None
        return await self._nyata(teks_samar, kunci, self.jalan, jejak)

    async def lengkapi_jalan(self, sampai: int) -> None:
        """Menjalankan jalan ke-2..sampai untuk teks terakhir yang dikirim (hanya bila belum di cache)."""
        if self.samar_terakhir is None or not self.boleh or self.tanpa:
            return
        kunci = self.kunci(self.samar_terakhir)
        for j in range(2, sampai + 1):
            if self.berhenti:
                return
            if not self.ada_cache(self.samar_terakhir, j):
                await self._nyata(self.samar_terakhir, kunci, j, None)

    def _kuota_rendah(self) -> str:
        k = self.transport.kuota if self.transport else {}
        if k.get("sisa_permintaan") is not None and k["sisa_permintaan"] < self.sisa_min:
            return "kuota_harian_rendah"
        return ""

    async def _nyata(self, teks_samar: str, kunci: dict, jalan: int, jejak_luar) -> llm.HasilLLM | None:
        while not self.berhenti:
            if self.transport.habis():
                self.berhenti = "batas_panggilan"
                break
            if self.maks_token_hari is not None and token_hari_ini() + rata_token_panggilan() > self.maks_token_hari:
                self.berhenti = "maks_token_hari"
                break
            alasan = self._kuota_rendah()
            if alasan:
                self.berhenti = alasan
                break
            k = self.transport.kuota
            if k.get("sisa_token") is not None and k["sisa_token"] < SISA_TOKEN_MINIMUM:
                tunggu = min(65.0, (k.get("reset_token") or 30.0) + 1.0)
                self.tidur(tunggu)
                k["sisa_token"] = None  # dibaca ulang dari balasan berikutnya
            jejak: list = []
            hasil = await self.asli(teks_samar, self.cfg_llm(), transport=self.transport, jejak=jejak)
            if jejak_luar is not None:
                jejak_luar.extend(jejak)
            if hasil is not None:
                self.beruntun_429 = 0
                self._simpan(kunci, jalan, hasil)
                return hasil
            if self.transport.habis() and any(j["status"] == "galat_tak_terduga" for j in jejak):
                self.berhenti = "batas_panggilan"
                break
            if self.transport.harian and any(j["status"] == 429 for j in jejak):
                self.berhenti = "429_harian"  # batas harian: menunggu tidak membantu
                break
            if any(j["status"] == 429 for j in jejak):
                self.beruntun_429 += 1
                if self.beruntun_429 >= MAKS_429_BERUNTUN:
                    self.berhenti = "429_beruntun"
                    break
                saran = [j["tunggu"] for j in jejak if j.get("tunggu") is not None]
                self.tidur(min(MAKS_TUNGGU_429, max(saran + [15.0])))
                continue
            self.beruntun_429 = 0
            self.gagal += 1
            return None
        return None

    def _simpan(self, kunci: dict, jalan: int, hasil: llm.HasilLLM) -> None:
        e = baca_json(self.jalur())
        if not (isinstance(e, dict) and e.get("kunci") == kunci):
            e = {"sha_gambar": self.sha, "kunci": kunci, "jalan": {}}
        e["jalan"][str(jalan)] = {
            "klaim_utama": hasil.klaim_utama,
            "kandidat": [{"id": c.id, "kutipan": list(c.kutipan)} for c in hasil.kandidat],
            "penyedia": hasil.penyedia, "durasi_ms": hasil.durasi_ms, "percobaan": hasil.percobaan,
            "respons_mentah": self.transport.body_ok, "usage": self.transport.usage_ok, "waktu": sekarang(),
        }
        tulis_json(self.jalur(), e)
        self.baru += 1


@dataclasses.dataclass
class Komponen:
    pembaca: PembacaBerCache
    pencarian: PencarianBerCache
    llm: LLMBerCache

    def atur_gambar(self, sha: str, baris: Baris, mode: str) -> None:
        self.pembaca.sha = self.pencarian.sha = self.llm.sha = sha
        self.pencarian.mode, self.pencarian.id_sumber = mode, baris.id_artikel_sumber
        self.pencarian.kosong = False
        self.pencarian.terakhir = []
        self.llm.kosong = False
        self.llm.samar_terakhir = None


def buat_komponen(
    ocr: bool = False, cari: bool = False, nyata_llm: bool = False, maks_panggilan: int | None = None,
    jeda: float = JEDA_LLM_MINIMUM, jalan: int = 1, tanpa_llm: bool = False, sisa_min: int = SISA_PERMINTAAN_MINIMUM,
    kirim=None, tidur=time.sleep, pencatat: Pencatat | None = None, maks_token_hari: int | None = None,
) -> Komponen:
    """`ocr`, `cari`, `nyata_llm`: tahap boleh memanggil sumber asli (selain itu hanya membaca cache)."""
    transport = TransportGroq(max(jeda, JEDA_LLM_MINIMUM), maks_panggilan, tidur=tidur, kirim=kirim) if nyata_llm else None
    return Komponen(
        PembacaBerCache(baca.pembaca, ocr), PencarianBerCache(cocok.pencarian, cari),
        LLMBerCache(llm.analisis, nyata_llm, transport, jalan, tanpa_llm, sisa_min, pencatat, tidur, maks_token_hari),
    )


@contextmanager
def terpasang(komp: Komponen):
    """Memasang pembungkus ke modul pipeline selama blok berjalan (orkestrator memakai modul yang sama)."""
    lama = (baca.pembaca, cocok.pencarian, llm.analisis)
    baca.pembaca, cocok.pencarian, llm.analisis = komp.pembaca, komp.pencarian, komp.llm.analisis
    try:
        yield komp
    finally:
        baca.pembaca, cocok.pencarian, llm.analisis = lama


# --- Ambang ---


def _konversi(nama: str, teks: str):
    bawaan = getattr(konfigurasi.Pengaturan(), nama)
    t = teks.strip().lower()
    try:
        if isinstance(bawaan, bool):
            if t in ("1", "ya", "true", "aktif"):
                return True
            if t in ("0", "tidak", "false", "mati"):
                return False
            raise ValueError
        return int(t) if isinstance(bawaan, int) else float(t)
    except ValueError:
        raise GalatAlat(f"nilai ambang tidak sah: {nama}={teks}") from None


def nama_ambang(nama: str) -> str:
    asli = ALIAS_AMBANG.get(nama.strip(), nama.strip())
    if asli not in AMBANG_BOLEH:
        raise GalatAlat(f"ambang tidak dikenal: {nama}")
    return asli


def urai_ambang(teks: str | None) -> dict:
    """"skor_kuat=0.88,relevansi=0.40" -> {"ambang_cocok": 0.88, "relevansi_minimum": 0.4}."""
    profil: dict = {}
    for bagian in (teks or "").split(","):
        if not bagian.strip():
            continue
        if "=" not in bagian:
            raise GalatAlat(f"format ambang harus nama=nilai: {bagian}")
        nama, nilai = bagian.split("=", 1)
        asli = nama_ambang(nama)
        profil[asli] = _konversi(asli, nilai)
    periksa_profil(profil)
    return profil


def periksa_profil(profil: dict) -> None:
    if profil.get("cocok_top_k", 0) > LEBAR_CACHE_CARI:
        raise GalatAlat(f"cocok_top_k maksimum {LEBAR_CACHE_CARI} (lebar cache pencarian)")


def urai_sapu(teks: str) -> dict[str, list]:
    """"skor_kuat=0.86:0.90:0.02,relevansi=0.3/0.4/0.5" -> {"ambang_cocok": [...], "relevansi_minimum": [...]}."""
    grid: dict[str, list] = {}
    for bagian in teks.split(","):
        if "=" not in bagian:
            raise GalatAlat(f"format sapu harus nama=awal:akhir:langkah atau nama=a/b/c: {bagian}")
        nama, spec = bagian.split("=", 1)
        asli = nama_ambang(nama)
        if ":" in spec:
            try:
                a, b, c = (float(x) for x in spec.split(":"))
            except ValueError:
                raise GalatAlat(f"rentang sapu tidak sah: {bagian}") from None
            if c <= 0 or b < a:
                raise GalatAlat(f"rentang sapu tidak sah: {bagian}")
            n = int(round((b - a) / c + 1e-9)) + 1
            nilai = [round(a + i * c, 6) for i in range(n)]
            if isinstance(getattr(konfigurasi.Pengaturan(), asli), int):
                nilai = [int(round(v)) for v in nilai]
        else:
            nilai = [_konversi(asli, x) for x in spec.split("/")]
        grid[asli] = nilai
    jumlah = 1
    for v in grid.values():
        jumlah *= len(v)
    if jumlah > 400:
        raise GalatAlat(f"grid sapu terlalu besar ({jumlah} > 400)")
    return grid


def kombinasi(grid: dict[str, list]) -> list[dict]:
    nama = list(grid)
    return [dict(zip(nama, v)) for v in itertools.product(*(grid[n] for n in nama))]


@contextmanager
def terapkan_profil(profil: dict):
    """Menimpa bidang Pengaturan global selama blok berjalan (semua tahap pipeline membaca objek global yang
    sama), lalu mengembalikannya. Profil kosong tidak mengubah apa pun."""
    cfg = konfigurasi.pengaturan
    lama = {k: getattr(cfg, k) for k in profil}
    for k, v in profil.items():
        setattr(cfg, k, v)
    try:
        yield cfg
    finally:
        for k, v in lama.items():
            setattr(cfg, k, v)


# --- Menjalankan satu gambar lewat orkestrator ---


async def jalankan_gambar(komp: Komponen, baris: Baris, mode: str = "biasa") -> dict:
    """Satu gambar lewat orkestrator.jalankan yang sama dengan server. Mengembalikan ringkasan tanpa teks."""
    from app.pipeline import orkestrator

    jalur = J.gambar / baris.berkas
    data = sebagai_png(jalur)
    sha = sha_berkas(jalur)
    komp.atur_gambar(sha, baris, mode)
    diag: dict = {}
    ctx = Konteks(id_permintaan=uuid.uuid4().hex, jeda_detik=(0.0, 0.0), klien_putus=tidak_putus, diagnostik=diag)
    hasil_gambar = {"id": baris.id, "hasil": "", "varian": "", "ciri": [], "skor_top1": None, "id_top1": None,
                    "rank_sumber": None, "skor_sumber": None, "llm_ada": None, "llm_kosong": False, "ms": 0}
    try:
        hasil = await orkestrator.jalankan(data, ctx)
    except CacheKosong:
        hasil_gambar["hasil"] = "cache_kosong"
        return hasil_gambar
    except GalatApi as e:
        hasil_gambar["hasil"] = "teks_tidak_terbaca" if e.kode == "teks_tidak_terbaca" else "galat"
        _lengkapi_bersih(komp, diag)
        return hasil_gambar
    except Exception:
        hasil_gambar["hasil"] = "galat"
        return hasil_gambar
    _lengkapi_bersih(komp, diag)
    if komp.pencarian.kosong:
        hasil_gambar["hasil"] = "cache_kosong"
        return hasil_gambar
    putusan = diag["putusan"]
    top = komp.pencarian.terakhir
    hasil_gambar.update(
        hasil=hasil.tingkat.value, varian=putusan.varian, ms=hasil.durasi_ms,
        ciri=[[c.id, c.keyakinan] for c in hasil.ciri],
        skor_top1=top[0]["skor"] if top else None, id_top1=top[0]["id"] if top else None,
        llm_ada=(not komp.llm.tanpa) and not komp.llm.kosong and diag.get("llm", {}).get("penyedia") is not None,
        # Cache LLM tidak ada (kumpul gagal untuk gambar ini): tingkat dinilai seperti LLM gagal, bukan galat.
        llm_kosong=(not komp.llm.tanpa) and komp.llm.kosong,
    )
    if mode == "biasa" and baris.id_artikel_sumber:
        for i, d in enumerate(top, start=1):
            if d["id"] == baris.id_artikel_sumber:
                hasil_gambar["rank_sumber"], hasil_gambar["skor_sumber"] = i, d["skor"]
                break
    return hasil_gambar


def _lengkapi_bersih(komp: Komponen, diag: dict) -> None:
    """Menyimpan teks bersih di cache OCR (informasi; tidak dibaca kembali oleh alat)."""
    hb = diag.get("bersih")
    if hb is not None:
        try:
            komp.pembaca.simpan_teks_bersih(tautan.gabung_tautan_terpecah(hb.teks))
        except Exception:
            pass


# --- Penilaian ---


def hasil_negatif(b: Baris) -> bool:
    return b.kategori in KATEGORI_NEGATIF


def hasil_positif(b: Baris) -> bool:
    return b.kategori in ("positif_db", "penipuan", "satir") or (
        b.kategori == "screenshot_asli" and b.label_harapan in LABEL_POSITIF
    )


async def nilai_baris(
    komp: Komponen, baris: list[Baris], profil: dict, mode: str, pencatat: Pencatat | None = None
) -> dict[str, dict[str, dict]]:
    """{"biasa": {id: hasil}, "loo": {id: hasil}} untuk mode yang diminta (keduanya bila mode == "keduanya")."""
    modes = ("biasa", "loo") if mode == "keduanya" else (mode,)
    keluaran: dict[str, dict[str, dict]] = {m: {} for m in modes}
    with terapkan_profil(profil), terpasang(komp):
        for urut, b in enumerate(baris, start=1):
            biasa = None
            for m in modes:
                if m == "loo" and not b.id_artikel_sumber and biasa is not None:
                    keluaran[m][b.id] = biasa  # tanpa artikel sumber, loo sama dengan biasa
                    continue
                r = await jalankan_gambar(komp, b, m)
                keluaran[m][b.id] = r
                if m == "biasa":
                    biasa = r
            if pencatat and (urut % 25 == 0 or urut == len(baris)):
                pencatat.tulis(f"nilai {urut}/{len(baris)}")
    return keluaran


def _cocok_harapan(b: Baris, r: dict) -> bool:
    return r["hasil"] == b.label_harapan


def _cocok_boleh(b: Baris, r: dict) -> bool:
    return r["hasil"] == b.label_harapan or r["hasil"] in b.label_boleh


def metrik(pasangan: list[tuple[Baris, dict]]) -> dict:
    neg = [(b, r) for b, r in pasangan if hasil_negatif(b)]
    pos = [(b, r) for b, r in pasangan if hasil_positif(b)]
    return {
        "n": len(pasangan),
        "n_neg": len(neg), "neg_kuat": sum(r["hasil"] == "kuat" for _, r in neg),
        "neg_hh": sum(r["hasil"] == "hati_hati" for _, r in neg),
        "n_pos": len(pos), "pos_kuat": sum(r["hasil"] == "kuat" for _, r in pos),
        "pos_hh": sum(r["hasil"] == "hati_hati" for _, r in pos),
        "cocok_harapan": sum(_cocok_harapan(b, r) for b, r in pasangan),
        "cocok_boleh": sum(_cocok_boleh(b, r) for b, r in pasangan),
        "belum": sum(r["hasil"] in ("cache_kosong", "galat") for _, r in pasangan),
        "llm_kosong": sum(bool(r.get("llm_kosong")) for _, r in pasangan),
    }


def _ids(pasangan, saring) -> str:
    daftar = sorted(b.id for b, r in pasangan if saring(b, r))
    return ", ".join(daftar) if daftar else "-"


def _median(nilai: list[float]) -> str:
    return f"{statistics.median(nilai):.3f}" if nilai else "-"


def ringkasan_markdown(judul: str, pasangan: list[tuple[Baris, dict]], peringkat: bool) -> list[str]:
    baris = [f"#### {judul} (n={len(pasangan)})", ""]
    if not pasangan:
        return baris + ["(tidak ada gambar)", ""]
    kolom = list(LABEL_SAH) + ["cache_kosong/galat"]

    baris += ["Matriks tingkat (baris = harapan, kolom = hasil):", "",
              "| harapan \\ hasil | " + " | ".join(kolom) + " | jumlah |", "|---|" + "---|" * (len(kolom) + 1)]
    for h in LABEL_SAH:
        sub = [r for b, r in pasangan if b.label_harapan == h]
        sel_ = [sum(r["hasil"] == k for r in sub) for k in LABEL_SAH] + [sum(r["hasil"] in HASIL_LAIN for r in sub)]
        baris.append(f"| {h} | " + " | ".join(map(str, sel_)) + f" | {len(sub)} |")
    baris.append("")

    baris += ["Negatif (kuat atau hati_hati adalah salah tandai):", "",
              "| kategori | n | kuat | hati_hati | id kuat | id hati_hati |", "|---|---|---|---|---|---|"]
    for kat in KATEGORI_NEGATIF:
        sub = [(b, r) for b, r in pasangan if b.kategori == kat]
        baris.append(
            f"| {kat} | {len(sub)} | {sum(r['hasil'] == 'kuat' for _, r in sub)} | "
            f"{sum(r['hasil'] == 'hati_hati' for _, r in sub)} | {_ids(sub, lambda b, r: r['hasil'] == 'kuat')} | "
            f"{_ids(sub, lambda b, r: r['hasil'] == 'hati_hati')} |"
        )
    neg = [(b, r) for b, r in pasangan if hasil_negatif(b)]
    baris.append(
        f"| semua negatif | {len(neg)} | {sum(r['hasil'] == 'kuat' for _, r in neg)} | "
        f"{sum(r['hasil'] == 'hati_hati' for _, r in neg)} | | |"
    )
    asli_neg = [(b, r) for b, r in pasangan if b.kategori == "screenshot_asli" and b.label_harapan not in LABEL_POSITIF]
    baris.append(
        f"| screenshot_asli (harapan bukan kuat/hati_hati; di luar hitungan negatif) | {len(asli_neg)} | "
        f"{sum(r['hasil'] == 'kuat' for _, r in asli_neg)} | {sum(r['hasil'] == 'hati_hati' for _, r in asli_neg)} | "
        f"{_ids(asli_neg, lambda b, r: r['hasil'] == 'kuat')} | {_ids(asli_neg, lambda b, r: r['hasil'] == 'hati_hati')} |"
    )
    baris.append("")

    baris += ["Recall positif (kuat + hati_hati):", "",
              "| kategori | n | kuat | hati_hati | recall | median skor top-1 | id terlewat |", "|---|---|---|---|---|---|---|"]
    for kat in KATEGORI_POSITIF:
        sub = [(b, r) for b, r in pasangan if b.kategori == kat and hasil_positif(b)]
        if not sub:
            continue
        kuat = sum(r["hasil"] == "kuat" for _, r in sub)
        hh = sum(r["hasil"] == "hati_hati" for _, r in sub)
        baris.append(
            f"| {kat} | {len(sub)} | {kuat} | {hh} | {(kuat + hh) / len(sub):.2f} | "
            f"{_median([r['skor_top1'] for _, r in sub if r['skor_top1'] is not None])} | "
            f"{_ids(sub, lambda b, r: r['hasil'] not in LABEL_POSITIF)} |"
        )
    baris.append("")

    m = metrik(pasangan)
    baris.append(
        f"Cocok label_harapan: {m['cocok_harapan']}/{m['n']}. Cocok label_harapan atau label_boleh: "
        f"{m['cocok_boleh']}/{m['n']}. Belum terkumpul atau galat: {m['belum']}"
        + (f" ({_ids(pasangan, lambda b, r: r['hasil'] in ('cache_kosong', 'galat'))})." if m["belum"] else ".")
        + f" Tanpa cache LLM (dinilai seperti LLM gagal, tidak termasuk galat): {m['llm_kosong']}"
        + (f" ({_ids(pasangan, lambda b, r: bool(r.get('llm_kosong')))})." if m["llm_kosong"] else ".")
    )
    baris.append("")

    if peringkat:
        sub = [(b, r) for b, r in pasangan if b.id_artikel_sumber]
        if sub:
            rank = [r["rank_sumber"] for _, r in sub]
            rr = [1 / x if x else 0.0 for x in rank]
            baris += [
                "Peringkat artikel sumber (mode biasa; tidak ditemukan di top-20 dihitung rank tak terbatas):", "",
                "| n | rank@1 | rank@5 | MRR | median skor artikel sumber | di luar top-20 |", "|---|---|---|---|---|---|",
                f"| {len(sub)} | {sum(x == 1 for x in rank)} | {sum(x is not None and x <= 5 for x in rank)} | "
                f"{sum(rr) / len(rr):.3f} | {_median([r['skor_sumber'] for _, r in sub if r['skor_sumber'] is not None])} | "
                f"{_ids(sub, lambda b, r: r['rank_sumber'] is None)} |", "",
            ]
    return baris


def kelompok_sintetis(pasangan: list[tuple[Baris, dict]]) -> list[tuple[str, list[tuple[Baris, dict]]]]:
    return [
        ("Semua", pasangan),
        ("Asli (sintetis = tidak)", [(b, r) for b, r in pasangan if not b.sintetis]),
        ("Sintetis (sintetis = ya)", [(b, r) for b, r in pasangan if b.sintetis]),
    ]


def stabilitas_llm(baris: list[Baris], jalan_maks: int) -> list[str]:
    """Konsistensi id ciri LLM antar jalan (--ulang-llm) dari cache: hanya id gambar dan id ciri."""
    kosong = ["Stabilitas LLM antar jalan: tidak ada gambar dengan lebih dari satu jalan di cache.", ""]
    perbedaan, n_gambar = [], 0
    ciri_tidak_stabil: dict[str, int] = {}
    for b in baris:
        e = baca_json(J.cache / "llm" / f"{sha_berkas(J.gambar / b.berkas)}.json")
        if not isinstance(e, dict) or len(e.get("jalan", {})) < 2:
            continue
        n_gambar += 1
        himpunan = [frozenset(c["id"] for c in j["kandidat"]) for _, j in sorted(e["jalan"].items())]
        semua, irisan = frozenset().union(*himpunan), frozenset.intersection(*himpunan)
        if semua != irisan:
            perbedaan.append(b.id)
            for c in semua - irisan:
                ciri_tidak_stabil[c] = ciri_tidak_stabil.get(c, 0) + 1
    if not n_gambar:
        return kosong
    return [
        f"Stabilitas LLM antar jalan: {n_gambar} gambar punya lebih dari satu jalan; ciri berbeda pada "
        f"{len(perbedaan)} gambar ({', '.join(sorted(perbedaan)) or '-'}).",
        "Ciri paling sering tidak stabil: " + (", ".join(f"{k} ({v})" for k, v in sorted(ciri_tidak_stabil.items(), key=lambda x: -x[1])) or "-") + ".",
        "",
    ]


def laporan(
    nama: str, nama_set: str, profil: dict, baris: list[Baris], hasil: dict[str, dict[str, dict]],
    sapuan: list[tuple[dict, dict[str, dict]]] | None = None, awal: dict | None = None, jalan: int = 1,
) -> Path:
    """Menulis laporan markdown. Hanya id, kategori, label, dan angka; tidak ada teks gambar."""
    per_id = {b.id: b for b in baris}
    teks = [
        f"# Evaluasi berlabel: {nama}", "",
        f"- Set: {nama_set}; gambar: {len(baris)}; waktu: {sekarang()}; jalan LLM yang dipakai: {jalan}",
        f"- Profil ambang: {konfigurasi.pengaturan.profil_ambang}; kueri e5 {konfigurasi.pengaturan.e5_maks_token_kueri} "
        f"token; ditimpa --ambang: {json.dumps(profil, sort_keys=True) if profil else 'tidak ada'}",
        f"- Panggilan LLM kumulatif (semua sesi): {jumlah_panggilan_total()}",
    ]
    cfg = konfigurasi.pengaturan
    teks += [
        f"- Ambang bawaan server: skor kuat {cfg.ambang_cocok}, mirip {cfg.ambang_mirip}, relevansi {cfg.relevansi_minimum}, "
        f"selisih konflik {cfg.selisih_konflik}", "",
    ]
    llm_ada = [r["llm_ada"] for m in hasil.values() for r in m.values() if r["llm_ada"] is not None]
    if llm_ada:
        tanpa_panggilan = sum(r["llm_ada"] is None for m in hasil.values() for r in m.values())
        teks += [
            f"- Gambar dengan hasil LLM dari cache: {sum(llm_ada)}/{len(llm_ada)} (mode pertama dan kedua dihitung "
            f"terpisah); tanpa tahap LLM (teks_tidak_terbaca atau galat sebelum LLM): {tanpa_panggilan}", "",
        ]
    for mode, per in hasil.items():
        pasangan = [(per_id[i], r) for i, r in per.items() if i in per_id]
        judul = "Mode biasa" if mode == "biasa" else "Mode loo (artikel sumber dikeluarkan dari pencarian)"
        teks += [f"## {judul}", ""]
        for sub, p in kelompok_sintetis(pasangan):
            teks += ringkasan_markdown(sub, p, peringkat=(mode == "biasa"))
    teks += stabilitas_llm(baris, jalan)
    if awal:
        teks += ["## Perbedaan terhadap tingkat kode awal (hasil_awal_uji.json)", ""]
        for mode, per in hasil.items():
            lama = awal.get("hasil", {}).get(mode, {})
            beda = sorted(i for i, r in per.items() if i in lama and lama[i]["hasil"] != r["hasil"])
            teks += [f"- Mode {mode}: {len(beda)} gambar berubah ({', '.join(beda) or '-'}).", ""]
    if sapuan:
        teks += ["## Sapuan ambang", "",
                 "| profil | mode | FP kuat | FP hati_hati | n negatif | recall (kuat+hh) | kuat | n positif | cocok harapan | cocok boleh |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
        for p, per_mode in sapuan:
            for mode, per in per_mode.items():
                m = metrik([(per_id[i], r) for i, r in per.items() if i in per_id])
                rec = (m["pos_kuat"] + m["pos_hh"]) / m["n_pos"] if m["n_pos"] else 0.0
                teks.append(
                    f"| {json.dumps(p, sort_keys=True)} | {mode} | {m['neg_kuat']} | {m['neg_hh']} | {m['n_neg']} | "
                    f"{rec:.2f} | {m['pos_kuat']} | {m['n_pos']} | {m['cocok_harapan']}/{m['n']} | {m['cocok_boleh']}/{m['n']} |"
                )
        teks.append("")
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    jalur = FOLDER_HASIL / f"{nama}.md"
    jalur.write_text("\n".join(teks), encoding="utf-8")
    return jalur


# --- Perintah ---


def _periksa_konfigurasi() -> None:
    if konfigurasi.kesalahan:
        raise GalatAlat(f"Pengaturan tidak sah: {konfigurasi.kesalahan}")


def _gambar_ada(baris: list[Baris]) -> None:
    hilang = [b.id for b in baris if not (J.gambar / b.berkas).exists()]
    if hilang:
        raise GalatAlat(f"gambar tidak ada untuk id: {', '.join(hilang[:20])}")


def kumpulkan_id(a) -> list[str]:
    """Id dari --id (dipisah koma) dan --id-berkas (satu per baris; baris kosong dan # diabaikan)."""
    ids = [x.strip() for x in (a.id or "").split(",") if x.strip()]
    if a.id_berkas:
        try:
            teks = Path(a.id_berkas).read_text(encoding="utf-8-sig")
        except OSError:
            raise GalatAlat(f"--id-berkas tidak bisa dibaca: {a.id_berkas}") from None
        ids += [b.strip() for b in teks.splitlines() if b.strip() and not b.strip().startswith("#")]
    return list(dict.fromkeys(ids))


def batasi_id(semua: list[Baris], terpilih: list[Baris], ids: list[str], nama_set: str) -> list[Baris]:
    """Membatasi gambar ke id yang diminta (urutan metadata). Id tidak dikenal atau id uji pada --set dev ditolak."""
    peta = {b.id: b for b in semua}
    tak_dikenal = [i for i in ids if i not in peta]
    if tak_dikenal:
        raise GalatAlat(f"id tidak dikenal: {', '.join(tak_dikenal[:20])}")
    if nama_set == "dev" and any(peta[i].set == "uji" for i in ids):
        raise GalatAlat("id milik set uji tidak boleh dipakai dengan --set dev: " + ", ".join(i for i in ids if peta[i].set == "uji")[:200])
    ada = {b.id for b in terpilih}
    di_luar = [i for i in ids if i not in ada]
    if di_luar:
        raise GalatAlat(f"id di luar --set {nama_set}: {', '.join(di_luar[:20])}")
    minta = set(ids)
    return [b for b in terpilih if b.id in minta]


def _cetak_ringkasan_token(komp: Komponen, pencatat: Pencatat) -> None:
    t = komp.llm.transport
    if t is None:
        return
    for baris in ringkasan_token_teks(t.sesi, t.token_sesi):
        pencatat.tulis("token: " + baris)


async def perintah_ringkas_token(a, pencatat: Pencatat) -> int:
    """Mencetak penghitung panggilan dan token tanpa memanggil apa pun."""
    d = baca_json(J.penghitung)
    if not isinstance(d, dict):
        print("belum ada penghitung")
        return 0
    print(f"panggilan total (semua hari): {d.get('total', 0)}")
    for hari, e in sorted(d.get("per_hari", {}).items()):
        print(f"{hari}: panggilan {e.get('panggilan', 0)}, token {e.get('token', 0)} "
              f"(prompt {e.get('prompt', 0)}, completion {e.get('completion', 0)}), "
              f"panggilan ber-token {e.get('panggilan_ber_token', 0)}")
    for baris in ringkasan_token_teks():
        print(baris)
    return 0


async def perintah_kumpul(a, pencatat: Pencatat) -> int:
    _periksa_konfigurasi()
    tahap = {t.strip() for t in a.tahap.split(",") if t.strip()}
    if not tahap <= {"ocr", "cari", "llm"}:
        raise GalatAlat("tahap harus bagian dari ocr,cari,llm")
    if a.tanpa_llm:
        tahap.discard("llm")
    if "llm" in tahap:
        if a.maks_panggilan is None or a.maks_panggilan <= 0:
            raise GalatAlat("tahap llm wajib --maks-panggilan N (N > 0); gunakan --tanpa-llm untuk melewatinya")
        if a.jeda_llm < JEDA_LLM_MINIMUM:
            raise GalatAlat(f"--jeda-llm minimal {JEDA_LLM_MINIMUM:.0f} detik")
        if not llm.muat_kunci(llm.GROQ.env):
            raise GalatAlat("kunci Groq tidak terisi")
    semua = baca_metadata()
    baris = pilih_set(semua, a.set)
    ids = kumpulkan_id(a)
    if ids:
        baris = batasi_id(semua, baris, ids, a.set)
    if a.maks_token_hari is not None and a.maks_token_hari <= 0:
        raise GalatAlat("--maks-token-hari harus > 0")
    _gambar_ada(baris)
    modes = ("biasa", "loo") if a.mode == "keduanya" else (a.mode,)
    komp = buat_komponen(
        ocr="ocr" in tahap, cari="cari" in tahap, nyata_llm="llm" in tahap, maks_panggilan=a.maks_panggilan,
        jeda=a.jeda_llm, tanpa_llm="llm" not in tahap, sisa_min=a.sisa_min, pencatat=pencatat,
        maks_token_hari=a.maks_token_hari,
    )
    pencatat.tulis(
        f"kumpul mulai pid={os.getpid()} set={a.set} gambar={len(baris)} tahap={','.join(sorted(tahap))} "
        f"maks_panggilan={a.maks_panggilan} jeda={a.jeda_llm} ulang_llm={a.ulang_llm} maks_token_hari={a.maks_token_hari}"
    )
    with terpasang(komp):
        for urut, b in enumerate(baris, start=1):
            for m in modes:
                if m == "loo" and not b.id_artikel_sumber:
                    continue
                await jalankan_gambar(komp, b, m)  # hasil tidak dipakai: yang dikumpulkan adalah cache
            if "llm" in tahap and a.ulang_llm > 1:
                await komp.llm.lengkapi_jalan(a.ulang_llm)
            pencatat.tulis(
                f"kumpul {urut}/{len(baris)} id={b.id} ocr_baru={komp.pembaca.baru} cari_baru={komp.pencarian.baru} "
                f"llm_baru={komp.llm.baru} panggilan_sesi={komp.llm.transport.sesi if komp.llm.transport else 0}"
            )
            if komp.llm.berhenti:
                tulis_json(J.checkpoint, {
                    "waktu": sekarang(), "alasan": komp.llm.berhenti, "selesai": urut, "total": len(baris),
                    "id_terakhir": b.id,
                })
                pencatat.tulis(
                    f"kumpul BERHENTI alasan={komp.llm.berhenti} setelah {urut}/{len(baris)}; cache adalah checkpoint, "
                    "jalankan ulang perintah yang sama untuk melanjutkan"
                )
                _cetak_ringkasan_token(komp, pencatat)
                return 3
    _cetak_ringkasan_token(komp, pencatat)
    p = komp.pencarian.asli
    ringkas_e5 = p.ringkasan() if getattr(p, "status", "") == cocok.STATUS_SIAP and hasattr(p, "detik_muat") else "tidak dimuat"
    pencatat.tulis(
        f"kumpul selesai: ocr_baru={komp.pembaca.baru} cari_baru={komp.pencarian.baru} llm_baru={komp.llm.baru} "
        f"llm_gagal={komp.llm.gagal} panggilan_sesi={komp.llm.transport.sesi if komp.llm.transport else 0} "
        f"panggilan_total={jumlah_panggilan_total()}; e5: {ringkas_e5}; RAM proses {cocok.ram_proses_mb() or 0:.0f} MB"
    )
    return 0


def _simpan_awal_dari(hasil: dict) -> dict:
    return {m: {i: {"hasil": r["hasil"], "varian": r["varian"]} for i, r in per.items()} for m, per in hasil.items()}


def _pastikan_lengkap(hasil: dict[str, dict[str, dict]]) -> None:
    kurang = sorted({i for per in hasil.values() for i, r in per.items() if r["hasil"] in ("cache_kosong", "galat")})
    if kurang:
        raise GalatAlat(f"cache set uji belum lengkap atau galat untuk {len(kurang)} gambar: {', '.join(kurang[:20])}; jalankan kumpul")


async def perintah_nilai(a, pencatat: Pencatat) -> int:
    _periksa_konfigurasi()
    profil = urai_ambang(a.ambang)
    semua = baca_metadata()
    baris = pilih_set(semua, a.set)
    _gambar_ada(baris)
    if a.set == "uji":
        if not a.final:
            raise GalatAlat("set uji hanya boleh dinilai dengan --final (sekali)")
        if a.sapu:
            raise GalatAlat("--sapu tidak boleh dipakai pada set uji")
        if J.penanda_uji.exists() and not a.paksa:
            raise GalatAlat(f"set uji sudah dinilai ({J.penanda_uji.name}); ulangi hanya dengan --paksa")
        verifikasi_beku(baris)
    elif a.final:
        raise GalatAlat("--final hanya untuk --set uji")
    komp = buat_komponen(tanpa_llm=a.tanpa_llm, jalan=a.jalan)
    pencatat.tulis(
        f"nilai mulai pid={os.getpid()} set={a.set} gambar={len(baris)} profil_ambang={a.profil} "
        f"ambang={json.dumps(profil, sort_keys=True)}"
    )
    hasil = await nilai_baris(komp, baris, profil, a.mode, pencatat)
    if a.set == "uji":
        _pastikan_lengkap(hasil)
        tulis_json(J.penanda_uji, {"waktu": sekarang(), "profil_ambang": a.profil, "profil": profil, "nama": a.nama,
                                   "mode": a.mode})
    sapuan = None
    if a.sapu:
        grid = kombinasi(urai_sapu(a.sapu))
        pencatat.tulis(f"sapu {len(grid)} profil")
        sapuan = []
        for urut, p in enumerate(grid, start=1):
            gabung = {**profil, **p}
            periksa_profil(gabung)
            sapuan.append((p, await nilai_baris(komp, baris, gabung, a.mode)))
            pencatat.tulis(f"sapu {urut}/{len(grid)}")
    awal = baca_json(J.hasil_awal) if a.set == "uji" else None
    jalur = laporan(a.nama, a.set, profil, baris, hasil, sapuan, awal, a.jalan)
    if a.set == "uji":
        pencatat.tulis(f"laporan uji final ditulis: {jalur}")
    else:
        for mode, per in hasil.items():
            m = metrik([(b, per[b.id]) for b in baris])
            pencatat.tulis(
                f"mode {mode}: negatif kuat={m['neg_kuat']} hati_hati={m['neg_hh']} dari {m['n_neg']}; "
                f"positif kuat={m['pos_kuat']} hati_hati={m['pos_hh']} dari {m['n_pos']}; belum={m['belum']}"
            )
        pencatat.tulis(f"laporan ditulis: {jalur}")
    return 0


async def perintah_segel_awal(a, pencatat: Pencatat) -> int:
    _periksa_konfigurasi()
    baris = pilih_set(baca_metadata(), "uji")
    _gambar_ada(baris)
    verifikasi_beku(baris)
    if J.hasil_awal.exists() and not a.paksa:
        raise GalatAlat(f"{J.hasil_awal.name} sudah ada; ulangi hanya dengan --paksa")
    profil = urai_ambang(a.ambang)
    komp = buat_komponen(tanpa_llm=a.tanpa_llm, jalan=a.jalan)
    hasil = await nilai_baris(komp, baris, profil, "keduanya")
    _pastikan_lengkap(hasil)
    tulis_json(J.hasil_awal, {"waktu": sekarang(), "profil_ambang": a.profil, "profil": profil, "jalan": a.jalan,
                              "hasil": _simpan_awal_dari(hasil)})
    pencatat.tulis(f"segel-awal: {len(baris)} gambar uji disimpan ke {J.hasil_awal.name}")
    return 0


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--log", default=str(LOG_BAWAAN), help="berkas log progres (PID, n/total)")
    p.add_argument("--akar", default=None, help="folder evaluasi (bawaan: folder data_lokal/evaluasi di server); untuk uji asap")
    p.add_argument("--profil", choices=tuple(konfigurasi.PROFIL_AMBANG), default="lama",
                   help="profil ambang dari konfigurasi.PROFIL_AMBANG (sama dengan server; bawaan alat: lama = kode "
                        "awal, server memakai akhir); CEKHOAKS_PROFIL_AMBANG diabaikan alat")
    p.add_argument("--maks-token-kueri", type=int, default=None, dest="maks_token_kueri",
                   help="panjang token kueri e5 (bawaan: nilai profil; maks 512)")
    p.add_argument("--varian-e5", choices=("fp32", "int8"), default=None, dest="varian_e5",
                   help="varian e5 (bawaan: Pengaturan); fp32/int8 punya cache pencarian terpisah")
    p.add_argument("--model-e5", default=None, dest="model_e5", help="path model ONNX khusus (mis. hasil kuantisasi lokal)")
    p.add_argument("--vektor-e5", default=None, dest="vektor_e5", help="path vektor .npy khusus (.json di sebelahnya)")
    sub = p.add_subparsers(dest="perintah", required=True)

    k = sub.add_parser("kumpul", help="mengisi cache OCR, pencarian, dan LLM")
    k.add_argument("--set", choices=("dev", "uji", "semua"), default="semua")
    k.add_argument("--tahap", default="ocr,cari,llm", help="bagian dari ocr,cari,llm")
    k.add_argument("--tanpa-llm", action="store_true", dest="tanpa_llm", help="melewati tahap llm (tanpa jaringan)")
    k.add_argument("--maks-panggilan", type=int, default=None, dest="maks_panggilan",
                   help="batas keras percobaan HTTP LLM pada sesi ini (wajib untuk tahap llm)")
    k.add_argument("--ulang-llm", type=int, default=1, dest="ulang_llm", help="jumlah jalan LLM per gambar (stabilitas)")
    k.add_argument("--jeda-llm", type=float, default=JEDA_LLM_MINIMUM, dest="jeda_llm", help="detik antar percobaan, minimal 8")
    k.add_argument("--sisa-min", type=int, default=SISA_PERMINTAAN_MINIMUM, dest="sisa_min",
                   help="berhenti bila sisa permintaan harian di bawah ini")
    k.add_argument("--mode", choices=("biasa", "loo", "keduanya"), default="keduanya")
    k.add_argument("--id", default=None, help="batasi ke id ini, dipisah koma (mis. ev001,ev005); id uji ditolak pada --set dev")
    k.add_argument("--id-berkas", default=None, dest="id_berkas", help="berkas berisi satu id per baris")
    k.add_argument("--maks-token-hari", type=int, default=None, dest="maks_token_hari",
                   help="berhenti (kode 3) bila token hari ini + perkiraan per panggilan melebihi N")

    n = sub.add_parser("nilai", help="menilai tingkat dari cache, tanpa OCR dan LLM")
    n.add_argument("--set", choices=("dev", "uji"), required=True)
    n.add_argument("--final", action="store_true", help="wajib untuk set uji")
    n.add_argument("--paksa", action="store_true", help="mengulang penilaian uji yang sudah pernah dilakukan")
    n.add_argument("--nama", default=None, help="nama laporan (bawaan evaluasi_<set>)")
    n.add_argument("--mode", choices=("biasa", "loo", "keduanya"), default="keduanya")
    n.add_argument("--ambang", default=None, help="mis. skor_kuat=0.88,relevansi=0.40")
    n.add_argument("--sapu", default=None, help="mis. skor_kuat=0.86:0.92:0.02,relevansi=0.3/0.4/0.5 (hanya dev)")
    n.add_argument("--jalan", type=int, default=1, help="jalan LLM yang dipakai (1..ulang-llm)")
    n.add_argument("--tanpa-llm", action="store_true", dest="tanpa_llm", help="abaikan cache LLM (ciri hanya dari regex)")

    sub.add_parser("ringkas-token", help="mencetak penghitung panggilan dan token tanpa memanggil apa pun")

    s = sub.add_parser("segel-awal", help="menyimpan hasil kode awal untuk set uji tanpa mencetak ringkasan")
    s.add_argument("--paksa", action="store_true")
    s.add_argument("--ambang", default=None)
    s.add_argument("--jalan", type=int, default=1)
    s.add_argument("--tanpa-llm", action="store_true", dest="tanpa_llm")
    return p


def terapkan_opsi_e5(a, cfg=None) -> None:
    """Menimpa Pengaturan global untuk e5 (berlaku seluruh proses alat; kunci cache pencarian ikut berubah)."""
    cfg = cfg or konfigurasi.pengaturan
    if a.maks_token_kueri is not None:
        if not 1 <= a.maks_token_kueri <= 512:
            raise GalatAlat("--maks-token-kueri harus 1..512 (batas posisi e5-base)")
        cfg.e5_maks_token_kueri = a.maks_token_kueri
    if a.varian_e5:
        cfg.cek_fakta_varian = a.varian_e5
    if a.model_e5:
        cfg.e5_model_berkas = Path(a.model_e5)
    if a.vektor_e5:
        cfg.e5_vektor_berkas = Path(a.vektor_e5)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    a = buat_parser().parse_args(argv)
    if a.akar:
        global J
        J = jalur_dari(Path(a.akar))
    konfigurasi.terapkan_profil_ambang(konfigurasi.pengaturan, a.profil)
    try:
        terapkan_opsi_e5(a)
    except GalatAlat as e:
        print(f"DITOLAK: {e}", file=sys.stderr)
        return 2
    if a.perintah == "nilai" and a.nama is None:
        a.nama = f"evaluasi_{a.set}"
    pencatat = Pencatat(Path(a.log) if a.log else None)
    fungsi = {"kumpul": perintah_kumpul, "nilai": perintah_nilai, "segel-awal": perintah_segel_awal,
              "ringkas-token": perintah_ringkas_token}[a.perintah]
    try:
        return asyncio.run(fungsi(a, pencatat))
    except GalatAlat as e:
        print(f"DITOLAK: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
