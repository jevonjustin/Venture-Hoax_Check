"""Skema artikel cek fakta, normalisasi label, dan pengambilan narasi. Hanya fungsi murni (tanpa jaringan)."""

import datetime
import hashlib
import json
import os
import re
from pathlib import Path

# server/data_lokal/ (masuk .gitignore)
DATA_LOKAL = Path(__file__).resolve().parents[2] / "data_lokal"
FOLDER_DB = Path(os.environ.get("CEKFAKTA_FOLDER", DATA_LOKAL / "cek_fakta"))
MENTAH = DATA_LOKAL / "dataset_mentah"

KOLOM = ["id", "judul", "narasi", "label_asli", "label", "sumber", "url", "tanggal", "asal_data"]
LABEL = ["salah", "penipuan", "belum_terbukti", "benar", "klarifikasi", "satir", "lainnya"]
MAKS_NARASI = 500

_SALAH = {"SALAH", "FALSE", "HOAX", "HOAKS", "FITNAH", "HASUT", "DISINFORMASI", "MISINFORMASI",
          "DISINFOMASI", "DISINFORMAS", "DISINFORMATION"}  # termasuk ejaan miring yang muncul di situs
_BUKAN_CEK_FAKTA = {"BERITA", "EDUKASI", "TOP", "ACARA", "ADMIN", "UPDATE", "DOKUMENTASI", "CEK FAKTA"}

_BULAN = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


# Kata label yang boleh muncul tanpa kurung ("HOAX: ...") atau dengan kurung tutup hilang ("[SALAH Anies ...")
_KATA_LABEL = r"(?:SALAH|HOAX|HOAKS|HASUT|FITNAH|DISINFORMASI|MISINFORMASI|PENIPUAN|BENAR|FAKTA|FALSE)"
_AWALAN_BERKURUNG = r"\s*[\[(]\s*([^\])]+?)\s*[\])]\s*:?\s*"
_AWALAN_TANPA_TUTUP = rf"\s*\[\s*({_KATA_LABEL})\s+(?=\S)"
_AWALAN_TITIK_DUA = rf"\s*({_KATA_LABEL})\s*:\s*"
_AWALAN_TANPA_BUKA = rf"\s*({_KATA_LABEL})\s*\]\s*"


def _awalan_label(judul: str):
    """Mengembalikan (label_asli, panjang awalan) untuk awalan label di judul, atau ('', 0)."""
    judul = judul or ""
    for pola in (_AWALAN_BERKURUNG, _AWALAN_TANPA_TUTUP, _AWALAN_TITIK_DUA, _AWALAN_TANPA_BUKA):
        m = re.match(pola, judul, flags=re.I if pola != _AWALAN_BERKURUNG else 0)
        if m:
            return m.group(1).strip(), m.end()
    return "", 0


def label_asli_dari_judul(judul: str) -> str:
    """Label di awal judul: '[SALAH] ...', '(ISU) : ...', 'HOAX: ...', atau '[SALAH ...' (kurung tutup hilang)."""
    return _awalan_label(judul)[0]


def normalisasi_label(label_asli: str) -> str:
    """Memetakan label asli ke himpunan kecil. 'bukan_cek_fakta' berarti artikel tidak masuk database."""
    teks = re.sub(r"\s+", " ", (label_asli or "").upper()).strip()
    if not teks:
        return "lainnya"
    kata = set(re.findall(r"[A-Z]+", teks))
    if "PENIPUAN" in kata or "SCAM" in kata:
        return "penipuan"
    if "BELUM TERBUKTI" in teks:
        return "belum_terbukti"
    if kata & _SALAH or "DIMANIPULASI" in kata:
        return "salah"
    if kata & {"KLARIFIKASI", "CLARIFICATION"}:
        return "klarifikasi"
    if kata & {"PARODI", "SATIR", "SATIRE", "KOMEDI"}:
        return "satir"
    if "BENAR" in kata or teks == "FAKTA":
        return "benar"
    if teks in _BUKAN_CEK_FAKTA or kata & _BUKAN_CEK_FAKTA or "CEK FAKTA" in teks:
        return "bukan_cek_fakta"
    return "lainnya"


_HASIL_PERIKSA = {"salah": "salah", "false": "salah", "klarifikasi": "klarifikasi", "clarification": "klarifikasi",
                  "benar": "klarifikasi", "true": "klarifikasi"}


def label_dengan_hasil_periksa(label_asli: str, hasil_periksa: str) -> str:
    """Label akhir. Judul tanpa label atau berlabel ISU dilengkapi dari 'Hasil Periksa Fakta' di halaman artikel
    (Salah atau False: salah; Klarifikasi, Clarification, Benar, atau True: klarifikasi, karena 'Benar' pada artikel
    klarifikasi berarti klarifikasinya benar, bukan klaimnya). Berita, Edukasi, dan Dalam Proses tetap lainnya.
    Label yang sudah dikenali tidak pernah diubah."""
    label = normalisasi_label(label_asli)
    if label != "lainnya" or (label_asli or "").strip().upper() not in ("", "ISU"):
        return label
    return _HASIL_PERIKSA.get((hasil_periksa or "").strip().lower(), "lainnya")


def judul_bersih(judul: str) -> str:
    """Judul tanpa awalan label, untuk embedding dan pencocokan duplikat."""
    return (judul or "")[_awalan_label(judul)[1]:].strip()


def kunci_judul(judul: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", judul_bersih(judul).lower())


def kunci_slug(url: str) -> str:
    """Slug artikel TurnBackHoax tanpa nomor depan, sama untuk format lama (/2024/10/30/slug/) dan baru (/articles/123-slug)."""
    if not url:
        return ""
    jalur = re.sub(r"^https?://[^/]+", "", url.strip().lower()).split("?")[0].rstrip("/")
    slug = jalur.rsplit("/", 1)[-1]
    return re.sub(r"^\d+-", "", slug)


def url_format_lama(url: str) -> bool:
    return bool(re.match(r"https?://(www\.)?turnbackhoax\.id/\d{4}/\d{2}/\d{2}/", url or ""))


def kunci_url(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", (url or "").strip().lower()).split("#")[0].rstrip("/")


def tanggal_iso(nilai) -> str | None:
    """Menerima 'Oktober 30, 2024', '08/10/2026', '2026-10-06 23:06:00', datetime, atau ISO. Gagal menghasilkan None."""
    if nilai is None:
        return None
    if isinstance(nilai, datetime.datetime):
        return nilai.date().isoformat()
    if isinstance(nilai, datetime.date):
        return nilai.isoformat()
    s = str(nilai).strip()
    if m := re.match(r"(\d{4})-(\d{2})-(\d{2})", s):
        try:
            return datetime.date(int(m[1]), int(m[2]), int(m[3])).isoformat()  # menolak 0000-00-00 dan tanggal mustahil
        except ValueError:
            return None
    if m := re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s):
        bulan = _BULAN.get(m[1].lower())
        if bulan:
            try:
                return datetime.date(int(m[3]), bulan, int(m[2])).isoformat()
            except ValueError:
                return None
    if m := re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s):
        try:
            return datetime.date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        except ValueError:
            return None
    return None


def id_stabil(kunci: str) -> str:
    return hashlib.sha1(kunci.encode("utf-8")).hexdigest()[:12]


def rapikan(teks: str, maks: int = MAKS_NARASI) -> str:
    """Merapikan spasi dan memotong di batas kata sampai maks karakter."""
    teks = re.sub(r"\s+", " ", teks or "").strip()
    teks = teks.strip(" =\"'“”‘’")
    if len(teks) <= maks:
        return teks
    potong = teks[:maks].rsplit(" ", 1)[0]
    return potong.rstrip(" ,;:") + "…"


_AWAL_NARASI = re.compile(r"\[?\s*(?:NARASI|NARRATIVE)\s*\]?\s*:?", re.I)
_AKHIR_NARASI = re.compile(
    r"(?:\[?\s*(?:PENJELASAN|EXPLANATION|PENELUSURAN|REFERENSI|REFERENCE|KATEGORI|CATEGORY|SUMBER|SOURCE)\s*\]?\s*:)"
    r"|(?:={3,})|(?:(?:\s=){3,})|(?:Hasil Periksa Fakta)",
    re.I,
)
_TANPA_NARASI = re.compile(r"narasi tidak ditampilkan|^\W*$", re.I)


def narasi_dari_teks_tbh(teks: str) -> str:
    """Mengambil bagian NARASI dari teks artikel TurnBackHoax versi Kaggle. Kosong jika tidak ada penandanya."""
    m = _AWAL_NARASI.search(teks or "")
    if not m:
        return ""
    sisa = teks[m.end():]
    akhir = _AKHIR_NARASI.search(sisa)
    potongan = sisa[: akhir.start()] if akhir else sisa
    potongan = rapikan(potongan)
    return "" if _TANPA_NARASI.search(potongan) else potongan


def narasi_dari_komdigi(body_text: str) -> str:
    """Komdigi: 'Penjelasan : Beredar ... Faktanya, ...'. Narasi = bagian sebelum 'Faktanya'."""
    t = re.sub(r"\s+", " ", body_text or "").strip()
    t = re.sub(r"^Penjelasan\s*:\s*", "", t, flags=re.I)
    t = re.split(r"\bFaktanya\b|\bLink Counter\b", t, maxsplit=1)[0]
    return rapikan(t)


def teks_passage(artikel: dict) -> str:
    """Teks yang di-embed: judul (tanpa awalan label) dan narasi, dengan awalan 'passage: '."""
    judul = judul_bersih(artikel.get("judul", ""))
    narasi = artikel.get("narasi", "") or ""
    return f"passage: {judul}. {narasi}".strip() if narasi else f"passage: {judul}"


def tulis_jsonl(jalur: Path, baris) -> int:
    jalur.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(jalur, "w", encoding="utf-8", newline="\n") as f:
        for b in baris:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
            n += 1
    return n


def baca_jsonl(jalur: Path) -> list[dict]:
    """Membaca JSONL. Baris yang tidak lengkap (misalnya baris terakhir saat berkas sedang ditulis pengumpul) dilewati."""
    if not Path(jalur).exists():
        return []
    hasil = []
    with open(jalur, encoding="utf-8") as f:
        for x in f:
            if not x.strip():
                continue
            try:
                hasil.append(json.loads(x))
            except json.JSONDecodeError:
                continue
    return hasil
