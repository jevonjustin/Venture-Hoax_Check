"""Tahap 3: mengambil klaim utama dari teks.

`klaim_heuristik` adalah cadangan heuristik yang ekstraktif: kalimat diambil apa adanya dari teks (boleh dipotong
di batas kata dengan elipsis), tidak pernah dirangkai ulang, sehingga selalu setia pada teks. Dipakai sebagai
cadangan kalau LLM gagal atau mengosongkan klaim (Sesi 5.5 yang memasangnya). `ekstrak_klaim` di bawah adalah dummy
yang masih dipakai /analisis.
"""

import re

from .. import contoh
from ..konfigurasi import Pengaturan, pengaturan as pengaturan_global
from . import bersih
from .tipe import Konteks

SINGKATAN = frozenset({
    "dr", "drs", "prof", "no", "hlm", "dll", "dsb", "dst", "tsb", "yth", "bpk", "sdr", "jl", "pt", "cv", "rp", "ir",
    "hj", "mr", "mrs", "vs", "st", "kec", "kab", "kel", "ka", "tgl", "tlp", "al", "sd", "an", "dkk", "dsj", "mis",
})
KATA_SAMBUNG = frozenset({
    "agar", "yang", "dan", "atau", "di", "ke", "untuk", "dengan", "karena", "bahwa", "dari", "pada", "serta",
    "sebagai", "dalam", "oleh", "akan", "jika", "kalau", "tetapi", "namun", "sehingga",
})
# Baris yang menjadi batas paragraf (tanggal, hari, sumber), bukan sambungan kalimat sebelumnya.
_BARIS_METADATA = re.compile(
    r"^(?:(?:senin|selasa|rabu|kamis|jumat|jum'at|sabtu|minggu)\b.*\d{4}|sumber\s*:|\d{1,2}\s+\w+\s+\d{4}\b.*(?:wib|wita|wit)?$)",
    re.IGNORECASE,
)
_AKHIR_KALIMAT = re.compile(r"[.!?]+[\"”’')\]]*$")
_KATA_KERJA = re.compile(
    r"\b(?:mengumumkan|menyatakan|mengatakan|menyebut|mengaku|akan|wajib|dilarang|diwajibkan|ditutup|dibuka|"
    r"mengandung|menyebabkan|dinyatakan|terbukti|resmi|berubah|disita|didenda|dikenakan|dirawat|ditangkap|diberlakukan|"
    r"usul|mengusulkan|tutup|menutup|melarang|mewajibkan|membatalkan|menghapus|menaikkan|menurunkan|gratis|terlibat|terungkap|ditemukan|meninggal|menewaskan|dikabarkan|beredar|mengajak|meminta|harus|dapat|bisa|"
    r"mendapat|menerima|memberikan|menghubungi|melanggar|dinonaktifkan|diblokir|dihapus)\b",
    re.IGNORECASE,
)
_ANGKA = re.compile(r"\d")
_URL = re.compile(r"https?://|www\.|\b\w+\.(?:com|id|net|org|co|xyz|top)\b", re.IGNORECASE)


def _paragraf(teks: str, cfg: Pengaturan) -> list[str]:
    """Menggabungkan baris OCR berurutan, karena kalimat sering terbelah lintas baris.

    Baris tidak disambung bila sudah berakhir tanda akhir kalimat atau berupa metadata (tanggal, "Sumber:").
    Selain itu baris disambung ke baris berikutnya bila: berakhir kata sambung (agar, yang, dan, ...), baris
    berikutnya diawali huruf kecil, atau baris itu hampir sepanjang baris terpanjang (tanda terbelah oleh lebar
    layar). Judul pendek dan nama akun dengan begitu tetap berdiri sendiri."""
    # Baris UI yang lolos ke sini (misalnya dari teks mentah) dianggap pemisah, bukan bagian kalimat.
    baris_semua = [("" if bersih.apakah_ui(b, cfg) else b.strip()) for b in teks.splitlines()]
    terpanjang = max((len(b) for b in baris_semua), default=0)
    hasil: list[str] = []
    sambung = False
    for i, baris in enumerate(baris_semua):
        if not baris:
            sambung = False
            continue
        if sambung and not _BARIS_METADATA.match(baris):
            hasil[-1] += " " + baris
        else:
            hasil.append(baris)
        berakhir = _AKHIR_KALIMAT.search(baris) or _BARIS_METADATA.match(baris)
        kata_terakhir = re.sub(r"\W+$", "", baris.split()[-1]).lower() if baris.split() else ""
        sambung = not berakhir and (
            kata_terakhir in KATA_SAMBUNG or len(baris) >= cfg.klaim_rasio_baris_panjang * terpanjang or _berikutnya_huruf_kecil(baris_semua, i)
        )
    return hasil


def _berikutnya_huruf_kecil(baris_semua: list[str], i: int) -> bool:
    """Apakah baris tepat sesudah baris ke-i diawali huruf kecil (sambungan kalimat). Baris kosong adalah pemisah."""
    return i + 1 < len(baris_semua) and bool(baris_semua[i + 1]) and baris_semua[i + 1][0].islower()


def _batas_kalimat(paragraf: str, posisi: int) -> bool:
    """Apakah tanda baca pada `paragraf[posisi]` (sudah diikuti spasi) benar-benar akhir kalimat."""
    tanda = paragraf[posisi]
    sebelum = paragraf[:posisi]
    kata = re.search(r"(\S+)$", sebelum)
    kata = kata.group(1) if kata else ""
    if tanda == ".":
        if re.search(r"\d$", sebelum) and re.match(r"\s*\d", paragraf[posisi + 1:]):
            return False  # angka diapit titik: 12. 16 atau 1.000. 000
        if "/" in kata or "www" in kata.lower() or _URL.search(kata):
            return False  # titik di dalam tautan
        bersih_kata = kata.strip("([\"'").rstrip(".").lower()
        if bersih_kata in SINGKATAN or re.fullmatch(r"(?:[a-z]\.)+[a-z]", kata.strip("([\"'").lower()):
            return False  # singkatan umum, termasuk a.n dan s.d
        if len(bersih_kata) == 1 and bersih_kata.isalpha():
            return False  # inisial
    lanjut = paragraf[posisi + 1:].lstrip(" \"“‘'([")
    return not lanjut or not lanjut[0].islower()


def pisah_kalimat(teks: str, cfg: Pengaturan | None = None) -> list[str]:
    """Memecah teks menjadi kalimat. Titik tidak dianggap batas bila diapit angka, ada di dalam tautan, atau
    mengikuti singkatan umum; tanda baca yang diikuti huruf kecil juga bukan batas."""
    cfg = cfg or pengaturan_global
    kalimat: list[str] = []
    for p in _paragraf(teks, cfg):
        awal = 0
        for m in re.finditer(r"[.!?]+(?=\s|$)", p):
            akhir = m.end()
            if _batas_kalimat(p, akhir - 1):
                potongan = p[awal:akhir].strip()
                if potongan:
                    kalimat.append(potongan)
                awal = akhir
        sisa = p[awal:].strip()
        if sisa:
            kalimat.append(sisa)
    return kalimat


def _kata(kalimat: str) -> list[str]:
    return kalimat.split()


def _rasio_huruf(kalimat: str) -> float:
    tanpa_spasi = re.sub(r"\s", "", kalimat)
    return sum(c.isalpha() for c in tanpa_spasi) / len(tanpa_spasi) if tanpa_spasi else 0.0


def skor_kalimat(kalimat: str, bukti_norm: list[str], cfg: Pengaturan) -> float | None:
    """Skor pemilihan kalimat, atau None bila kalimat tidak layak jadi klaim (pertanyaan, UI, terlalu pendek,
    terlalu banyak non-huruf, atau tautan)."""
    kata = _kata(kalimat)
    if len(kata) < cfg.klaim_min_kata or kalimat.rstrip("\"”’') ").endswith("?"):
        return None
    if bersih.apakah_ui(kalimat, cfg) or _rasio_huruf(kalimat) < 0.6 or _URL.search(kalimat):
        return None
    skor = 0.0
    n = len(kata)
    skor += 2 if 8 <= n <= 35 else (1 if n <= 60 else 0)
    if kalimat.rstrip("\"”’') ").endswith("."):
        skor += 1
    if re.search(r"!\s*$", kalimat):
        skor -= 1
    if _KATA_KERJA.search(kalimat):
        skor += 1
    nama = [k for k in kata[1:] if k[:1].isupper() and not k.isupper()]
    if _ANGKA.search(kalimat) or len(nama) >= 2:
        skor += 1
    norm = kalimat.lower()
    if any(b and (b in norm or norm in b) for b in bukti_norm):
        skor += 1
    return skor


def _potong(kalimat: str, maks: int) -> str:
    if len(kalimat) <= maks:
        return kalimat
    potong = kalimat[:maks]
    if kalimat[maks] != " " and " " in potong:
        potong = potong.rsplit(" ", 1)[0]
    return potong.rstrip(" ,;:-") + "…"


def klaim_heuristik(teks_bersih: str, bukti: list[str] | None = None, cfg: Pengaturan | None = None) -> str:
    """Masukan: teks bersih dan (opsional) bukti ciri regex. Keluaran: satu kalimat klaim yang diambil apa adanya
    dari teks, atau string kosong bila tidak ada pernyataan yang layak.

    Skor: panjang wajar (+2 untuk 8-35 kata, +1 sampai 60), berakhir titik (+1), kata kerja pernyataan (+1),
    angka atau dua nama berhuruf kapital (+1), tumpang tindih dengan bukti ciri (+1), seruan murni (-1). Kalimat
    pertanyaan, baris UI, tautan, dan kalimat yang kebanyakan non-huruf tidak dipertimbangkan. Skor terbaik harus
    mencapai `klaim_skor_minimum`; kalau seri, kalimat yang lebih awal menang.
    """
    cfg = cfg or pengaturan_global
    bukti_norm = [re.sub(r"\s+", " ", b).strip().lower().rstrip("…") for b in (bukti or []) if b]
    terbaik, skor_terbaik = "", None
    for kalimat in pisah_kalimat(teks_bersih, cfg):
        skor = skor_kalimat(kalimat, bukti_norm, cfg)
        if skor is not None and (skor_terbaik is None or skor > skor_terbaik):
            terbaik, skor_terbaik = kalimat, skor
    if skor_terbaik is None or skor_terbaik < cfg.klaim_skor_minimum:
        return ""
    return _potong(terbaik, cfg.klaim_maks_karakter)


def ekstrak_klaim(teks_bersih: str, ctx: Konteks) -> str | None:
    """Dummy. Masukan: teks bersih. Keluaran: ringkasan satu kalimat, atau None jika tidak ada klaim jelas."""
    return contoh.CONTOH[ctx.skenario].klaim_utama
