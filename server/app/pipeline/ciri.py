"""Tahap 5: mendeteksi ciri hoaks (detektor regex dan penggabungan dengan kandidat LLM).

Dua jalur:
- `deteksi_regex(teks)`: detektor regex/heuristik sederhana per ciri, dengan dua kekuatan pola. Pola "kuat" adalah
  frasa yang hampir pasti menandai ciri; pola "lemah" adalah kata yang juga sering muncul di teks biasa.
- `gabung_ciri(...)`: fungsi murni yang menggabungkan hasil regex dengan kandidat dari LLM. LLM hanya menandai
  kandidat; ciri diterima kalau kutipannya terverifikasi ada di teks. Penjelasan tidak dibuat di sini
  (selalu dari template.py).

`pernah_dibantah` tidak punya detektor: ciri itu ditentukan hasil pencarian database cek fakta
(pipeline/tingkat.py).
"""

import re
from collections.abc import Iterable

from ..konfigurasi import Pengaturan, pengaturan as pengaturan_global
from ..skema import ID_CIRI_TERKUNCI
from .tipe import CiriRegex, CiriTerdeteksi, KandidatLLM

KUAT = "kuat"
LEMAH = "lemah"
TINGGI = "tinggi"
SEDANG = "sedang"

ID_PERNAH_DIBANTAH = "pernah_dibantah"
# LLM hanya ditawari id yang bukan pernah_dibantah (selaras alat/ukur_llm/prompt.py).
ID_BISA_DITANDAI = tuple(i for i in ID_CIRI_TERKUNCI if i != ID_PERNAH_DIBANTAH)

_I = re.IGNORECASE


def _p(pola: str, bendera: int = _I) -> re.Pattern:
    return re.compile(pola, bendera)


# ---------------------------------------------------------------------------
# Pola per ciri: daftar (kekuatan, pola). Teks sudah dirapikan (spasi tunggal) sebelum dicocokkan.
# ---------------------------------------------------------------------------

_KATA_AJAKAN = r"(?:bagikan|teruskan|forward|share)"
_OBJEK_AJAKAN = r"(?:semua|seluruh|banyak|grup|group|keluarga|teman|kerabat|kontak|orang|sahabat|saudara)"

# Menu berbagi situs ("Bagikan ke Facebook", "Share: WhatsApp") bukan ajakan menyebarkan.
_MENU_BERBAGI = _p(
    r"\b(?:bagikan|share|teruskan|kirim)\w*\s*:?\s*(?:(?:ke|via|lewat|di|on|to|dengan)\s+)?"
    r"(?:facebook|fb|whatsapp|wa|twitter|x|telegram|line|instagram|ig|e-?mail|pinterest|linkedin|tiktok"
    r"|salin\s+tau?tan|copy\s+link)\b"
)

_AJAKAN = [
    # Tanpa batas kata di ujung: OCR sering menempelkan kata berikutnya ("VIRALKANINI").
    (KUAT, _p(r"\b(?:sebar\s?luaskan|sebarkan|viralkan)")),
    (KUAT, _p(rf"\b{_KATA_AJAKAN}\b(?:\s+\S+){{0,3}}?\s+(?:ke|kepada)\s+{_OBJEK_AJAKAN}\b")),
    (KUAT, _p(rf"\b{_KATA_AJAKAN}\s+(?:pesan|info|informasi|berita|postingan|video)\s+ini\b")),
    (KUAT, _p(r"\b(?:share|bagikan)\s+(?:sebanyak|seluas)")),
    (KUAT, _p(r"\bbantu\s+(?:share|bagikan|sebarkan|viralkan)\b")),
    (KUAT, _p(r"\bkirim(?:kan)?\s+(?:pesan\s+ini\s+)?ke\s+\d+\s+(?:grup|group|orang|teman)\b")),
    (LEMAH, _p(rf"\b{_KATA_AJAKAN}\b")),
]

_DESAKAN = [
    (KUAT, _p(r"\bsebelum\s+(?:(?:segera|keburu)\s+)?(?:di\s?)?(?:hapus|blokir|tutup|hilang|tarik|terlambat|kedaluwarsa|kadaluarsa|non\s?aktif\w*|suspend\w*|cabut|bekukan|banned?)")),
    (KUAT, _p(r"\bhari\s+ini\s+(?:terakhir|saja|batas)\b")),
    (KUAT, _p(r"\b(?:kesempatan|waktu|penawaran)\s+(?:terakhir|terbatas)\b")),
    (KUAT, _p(r"\bsegera\b(?:\s+\S+){0,6}?\s+sebelum\b")),
    (KUAT, _p(r"\bakan\s+(?:segera\s+)?(?:di\s?)?(?:nonaktifkan|blokir|hapus|tutup|suspend|cabut)\w*")),
    (LEMAH, _p(r"\bsegera\b")),
    (LEMAH, _p(r"\bmulai\s+(?:besok|hari\s+ini|minggu\s+depan|senin|selasa|rabu|kamis|jumat|sabtu)\b")),
    (LEMAH, _p(r"\bsekarang\s+juga\b")),
    (LEMAH, _p(r"\b(?:secepatnya|buruan)\b")),
    (LEMAH, _p(r"\bdalam\s+(?:waktu\s+)?\d+\s*(?:jam|menit)\b")),
    (LEMAH, _p(r"\bbatas\s+waktu\b")),
]

_PEMENDEK = (
    r"bit\.ly|tinyurl\.com|s\.id|cutt\.ly|t\.co|shorturl\.at|rebrand\.ly|is\.gd|ow\.ly|goo\.gl|t\.ly|tiny\.cc|rb\.gy"
    r"|lnkd\.in|bit\.do"
)
_TLD_MURAH = r"xyz|top|click|icu|buzz|cfd|sbs|monster|rest"
_LAYANAN_GRATIS = r"weebly\.com|weeblysite\.com|wixsite\.com|000webhostapp\.com|webcindario\.com"
_LINK_KUAT = [
    (KUAT, _p(rf"(?<![\w.@-])(?:{_PEMENDEK})/\S+")),
    (KUAT, _p(r"(?<![\w.@-])chat\.whatsapp\.com/\S+")),
    (KUAT, _p(rf"(?<![\w.@-])(?:[\w-]+\.)+(?:{_TLD_MURAH})(?:/\S*)?(?![\w-])")),
    (KUAT, _p(rf"(?<![\w@-])(?:[\w-]+\.)*(?:{_LAYANAN_GRATIS})(?:/\S*)?")),
]
_URL_UMUM = _p(r"(?:https?://|www\.)\S+")
# Domain berikut hanya berfungsi untuk TIDAK menandai tautan lemah; tidak menjamin isi tautan.
_DOMAIN_DIKECUALIKAN = _p(
    r"^(?:https?://)?(?:www\.)?(?:[\w-]+\.)*"
    r"(?:go\.id|ac\.id|sch\.id|mil\.id|kompas\.com|detik\.com|tempo\.co|cnnindonesia\.com|antaranews\.com"
    r"|liputan6\.com|tribunnews\.com|kumparan\.com|cnbcindonesia\.com|bbc\.com|turnbackhoax\.id|republika\.co\.id"
    r"|merahputih\.com|medcom\.id)(?:[/:?#]|$)"
)

_SUMBER = [
    (LEMAH, _p(r"\b(?:katanya|konon|kabarnya|dikabarkan)\b")),
    (LEMAH, _p(r"\binfo\s+(?:dari|dr)\s+(?:grup|group|teman|sebelah|wa|whatsapp)\b")),
    (LEMAH, _p(r"\b(?:dapat|dapet|dpt)\s+(?:(?:info|kiriman|pesan|berita)\s+)?(?:dari|dr)\s+(?:grup|group|teman)\b")),
    (LEMAH, _p(r"\bcopas\b|\bcopy\s*paste\b")),
    (LEMAH, _p(r"\b(?:diteruskan|forwarded)(?:\s+many\s+times|\s+berkali-kali)?\b")),
    (LEMAH, _p(r"\bberedar\s+(?:di|luas)\b")),
    (LEMAH, _p(r"\bsumber\s*:?\s*(?:grup|group|wa|whatsapp)\b")),
]

# "viral" hanya dipakai di sini (bukan di sumber_tidak_jelas).
_CLICKBAIT = [
    (LEMAH, _p(r"\b(?:viral|heboh|geger|mengejutkan|menggemparkan)\b")),
    (LEMAH, _p(r"\b(?:tidak|nggak|gak|ga)\s+(?:akan|bakal)\s+percaya\b")),
    (LEMAH, _p(r"\bternyata\s+(?:ini|inilah|begini)\b")),
    (LEMAH, _p(r"\bwajib\s+(?:baca|tahu|nonton|simak)\b")),
    (LEMAH, _p(r"\bbikin\s+(?:kaget|geleng|merinding|syok|melongo)\w*")),
    (LEMAH, _p(r"\bterungkap\b")),
    (LEMAH, _p(r"\b(?:ini|inilah)\s+(?:alasan|penyebab|rahasia)\w*")),
]

# Pola kuat hanya untuk ajakan kekerasan yang jelas menyasar kelompok (kata kerja ajakan + kelompok).
# Kata tunggal seperti "kafir" atau "antek" hanya lemah, karena muncul juga di berita dan bantahan.
_KEKERASAN = r"(?:bantai|ganyang|basmi|gorok|habisi|musnahkan)\w*"
_KELOMPOK = (
    r"(?:cina|china|tionghoa|kafir|komunis|pki|syiah|ahmadiyah|yahudi|aseng|antek|pribumi|etnis|kaum|umat|penganut|golongan)"
)
_PROVOKATIF = [
    (KUAT, _p(rf"\b{_KEKERASAN}\s+(?:\w+\s+){{0,2}}?{_KELOMPOK}\b")),
    (LEMAH, _p(r"\b(?:kafir|antek|pengkhianat|laknat|bantai|ganyang|biadab|keji|bejat|zalim|jahanam|hancurkan|panik|mengerikan|kejam|murka|geram)\b")),
]

# Permintaan kode, data rahasia, atau uang. Pola kuat saja: kata seperti "OTP" tanpa kata permintaan sering
# muncul di berita dan edukasi, jadi tidak dipakai. Kalimat larangan ("JANGAN BERIKAN kode OTP ...") dibuang
# oleh `_cocok_permintaan`.
_KATA_MINTA = r"(?:kirim(?:kan|in)?|sebut(?:kan)?|beri(?:kan)?|kasih(?:kan)?|bacakan|masukkan|input|ketik(?:kan)?)"
_RAHASIA = r"(?:kode(?:nya)?|otp|pin(?!\s+(?:lokasi|maps?|peta))|sandi|password|kata\s+sandi|cvv|token)"
_LAYANAN_DOMPET = r"(?:ovo|dana|gopay|go-pay|shopeepay|linkaja|link\s+aja)"
_PERMINTAAN = [
    (KUAT, _p(rf"\b(?:di)?{_KATA_MINTA}\b(?:\s+\S+){{0,3}}?\s+{_RAHASIA}\b")),
    (KUAT, _p(r"\b(?:minta|meminta|tanya|menanyakan)\w*\s+(?:\S+\s+){0,2}?(?:kode(?:nya)?|otp|pin(?!\s+(?:lokasi|maps?|peta))|sandi|password)\b")),
    (KUAT, _p(r"\bkode\s+\d\s*(?:angka|digit)\b|\b\d\s*(?:angka|digit)\b(?:\s+\S+){0,3}?\s+kode\b")),
    (KUAT, _p(r"\b(?:bisa|tolong|tlng|mohon|minta)\s+(?:di)?(?:kirim|forward|teruskan)\w*\s+(?:sms|kode|pesan)\b")),
    (KUAT, _p(r"\bkode\b(?:\s+\S+){0,6}?\s+(?:kirim|kirimkan|sebutkan|kasih|bacakan)\w*")),
    (KUAT, _p(r"\b(?:butuh|butu|perlu|harus|wajib|untuk|minta)\s+(?:\w+\s+){0,2}?verifikasi\s+(?:2|dua)\s+(?:langkah|tahap|faktor)\b")),
    (KUAT, _p(rf"\bunlock\b(?:\s+\S+){{0,2}}?\s+(?:ke|via|lewat)\s+{_LAYANAN_DOMPET}\b")),
    (KUAT, _p(r"\bqris\b(?:\s+\S+){0,5}?\s+(?:bermsalah|bermasalah|error|eror|gagal|bermasalah)\b")),
    (KUAT, _p(
        rf"\b(?:refund|reffund|refun|pengembalian\s+dana|pencairan)\b(?:\s+\S+){{0,6}}?\s+(?:dialihkan\s+)?"
        rf"(?:ke|via|lewat)\s+{_LAYANAN_DOMPET}\b"
    )),
    (KUAT, _p(r"\bwajib\s+(?:di)?(?:setor|bayar|transfer)\w*(?:\s+\S+){0,4}?\s+(?:di\s+awal|dulu|terlebih\s+dahulu|sebelum)\b")),
    (KUAT, _p(
        r"\b(?:transfer|bayar|setor|top\s*up)\w*\b(?:\s+\S+){0,3}?\s+(?:biaya|denda|admin|administrasi|pajak|dp|deposit|jaminan|"
        r"aktivasi|pencairan)\b"
    )),
]

# Kalimat larangan atau edukasi: kecocokan di dekat kata ini tidak ditandai sama sekali.
# "jangan lupa", "jangan ragu", dan sejenisnya adalah kata pendorong, bukan larangan.
_LARANGAN = _p(
    r"\b(?:jangan(?:lah)?(?!\s+(?:sampai\s+)?(?:lupa|ragu(?:-ragu)?|sungkan|segan|malu|telat|terlambat|lama|ketinggalan)\b)|dilarang|tidak\s+boleh|tak\s+boleh|hindari|waspada(?:i)?|"
    r"(?:tidak|tak|nggak|gak|ga|bukan)\s+(?:pernah\s+|akan\s+){0,2}(?:me)?minta\w*|"
    r"(?:tidak|tak|nggak|gak)\s+(?:pernah\s+|akan\s+){0,2}menanyakan|rahasiakan|bersifat\s+rahasia|"
    r"do\s+not|don'?t|never)\b"
)
# Kata larangan hanya membatalkan permintaan di klausanya sendiri (tanpa koma, titik, tanda seru/tanya, titik koma,
# atau kata "tapi/tetapi/namun/kecuali" di antaranya; titik dua bukan batas: "Waspada penipuan: pelaku meminta ...") dan hanya bila mendahului atau tumpang tindih
# dengan kata kerja permintaan, paling jauh sekian token. Baris baru bukan batas: OCR memecah kalimat per baris.
_PEMBATAS_KLAUSA = re.compile(r"[,;.!?]|\b(?:tapi|tetapi|namun|kecuali)\b", re.IGNORECASE)
_JARAK_LARANGAN_TOKEN = 3

_POLA = {
    "permintaan_data_rahasia": _PERMINTAAN,
    "ajakan_menyebarkan": _AJAKAN,
    "desakan_waktu": _DESAKAN,
    "sumber_tidak_jelas": _SUMBER,
    "judul_clickbait": _CLICKBAIT,
    "bahasa_provokatif": _PROVOKATIF,
}

_KALIMAT_KAPITAL = re.compile(r"(?<![\w])[A-Z][A-Z0-9'’,:\- ]{6,}!+")
_RUN_KAPITAL = re.compile(r"(?:\b[A-Z][A-Z0-9'’-]+\b[ ,:;&-]*){3,}")


# ---------------------------------------------------------------------------
# Detektor
# ---------------------------------------------------------------------------

def _rapikan(teks: str) -> str:
    """Spasi dan pergantian baris diseragamkan; spasi setelah "://" dibuang (OCR sering memecah tautan di sana)."""
    datar = re.sub(r"\s+", " ", teks).strip()
    return re.sub(r"(://) ", r"\1", datar)


def _cocok_pola(daftar, datar: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), kekuatan) for kekuatan, pola in daftar for m in pola.finditer(datar)]


def _cocok_ajakan(datar: str) -> list[tuple[int, int, str]]:
    menu = [(m.start(), m.end()) for m in _MENU_BERBAGI.finditer(datar)]
    return [
        c for c in _cocok_pola(_AJAKAN, datar)
        if not any(c[0] < akhir and awal < c[1] for awal, akhir in menu)
    ]


def _cocok_permintaan(datar: str) -> list[tuple[int, int, str]]:
    """Pola permintaan kode/data/uang, kecuali yang berada dalam kalimat larangan atau edukasi."""
    return [c for c in _cocok_pola(_PERMINTAAN, datar) if not _dibatalkan_larangan(datar, c[0], c[1])]


def _dibatalkan_larangan(datar: str, s: int, e: int) -> bool:
    """Apakah kecocokan permintaan di datar[s:e] berada di bawah kata larangan pada klausa yang sama."""
    awal_klausa = 0
    for m in _PEMBATAS_KLAUSA.finditer(datar, 0, s):
        awal_klausa = m.end()
    for larangan in _LARANGAN.finditer(datar, awal_klausa, e):
        if larangan.end() > s:  # tumpang tindih atau berada di dalam kecocokan
            return True
        if len(datar[larangan.end():s].split()) <= _JARAK_LARANGAN_TOKEN:
            return True
    return False


def _cocok_tautan(datar: str) -> list[tuple[int, int, str]]:
    hasil = _cocok_pola(_LINK_KUAT, datar)
    for m in _URL_UMUM.finditer(datar):
        url = m.group().rstrip(".,;:!?)")
        if _DOMAIN_DIKECUALIKAN.match(url) or any(m.start() < a and s < m.end() for s, a, _ in hasil):
            continue
        hasil.append((m.start(), m.start() + len(url), LEMAH))
    return hasil


TAUTAN_PEMENDEK = "pemendek"
TAUTAN_SITUS_GRATIS = "situs_gratis"
TAUTAN_UMUM = "umum"
_RE_PEMENDEK = _p(rf"(?<![\w.@-])(?:{_PEMENDEK})(?:/|\b)")
_RE_SITUS_GRATIS = _p(rf"(?:\.|//|^)(?:{_LAYANAN_GRATIS})\b|\.(?:{_TLD_MURAH})(?:/|\b|$)")


def jenis_tautan(bukti: list[str]) -> str:
    """Jenis tautan pada bukti ciri link_mencurigakan, untuk memilih teks penjelasan (id ciri tidak berubah):
    pemendek tautan (tujuan tidak terlihat), situs gratis atau domain tidak umum (siapa pun bisa membuat situs
    dengan nama apa pun), atau umum. Pemendek didahulukan kalau keduanya ada."""
    if any(_RE_PEMENDEK.search(b) for b in bukti):
        return TAUTAN_PEMENDEK
    if any(_RE_SITUS_GRATIS.search(b) for b in bukti):
        return TAUTAN_SITUS_GRATIS
    return TAUTAN_UMUM


def _cocok_kapital(datar: str, cfg: Pengaturan) -> list[tuple[int, int, str]]:
    hasil = []
    seru = [(m.start(), m.end()) for m in re.finditer(r"!(?:\s?!)+", datar)]
    for awal, akhir in seru:
        beruntun = datar[awal:akhir].count("!")
        hasil.append((awal, akhir, KUAT if beruntun >= cfg.ciri_seru_beruntun_kuat else LEMAH))
    kalimat = [(m.start(), m.end()) for m in _KALIMAT_KAPITAL.finditer(datar)]
    kuat = len(kalimat) >= cfg.ciri_kalimat_kapital_kuat
    hasil += [(a, b, KUAT if kuat else LEMAH) for a, b in kalimat]
    huruf = [c for c in datar if c.isalpha()]
    if len(huruf) >= cfg.ciri_kapital_min_huruf and sum(c.isupper() for c in huruf) / len(huruf) > cfg.ciri_kapital_rasio:
        run = _RUN_KAPITAL.search(datar)
        hasil.append((run.start(), run.end(), LEMAH) if run else (0, min(len(datar), 60), LEMAH))
    return hasil


def _jendela(datar: str, s: int, e: int, cfg: Pengaturan) -> tuple[int, int]:
    """Potongan teks di sekitar kecocokan [s, e), dipotong di batas kata. Bukti harus potongan persis dari teks,
    jadi tidak ada elipsis di sini; tampilan yang menambahkannya bila perlu."""
    maks = cfg.ciri_bukti_maks_karakter
    if e - s >= maks:
        akhir = s + maks
        while akhir > s and akhir < len(datar) and datar[akhir] != " ":
            akhir -= 1
        return s, (akhir if akhir > s else s + maks)
    konteks = min(cfg.ciri_bukti_konteks, (maks - (e - s)) // 2)
    awal, akhir = max(0, s - konteks), min(len(datar), e + konteks)
    while awal < s and awal > 0 and datar[awal - 1] != " ":
        awal += 1
    while akhir > e and akhir < len(datar) and datar[akhir] != " ":
        akhir -= 1
    return awal, akhir


def _kumpulkan_bukti(datar: str, cocok: list[tuple[int, int, str]], cfg: Pengaturan) -> tuple[list[str], int]:
    """Bukti: pola kuat lebih dulu, lalu lemah; urutan kemunculan di dalam tiap kelompok. Jendela yang saling
    tumpang tindih hanya dihitung sekali, dan kecocokan yang teksnya sama persis ("Segera" tiga kali) hanya satu
    bukti. Maksimal `ciri_bukti_maks`. Mengembalikan (bukti, jumlah bukti dari pola kuat di awal daftar)."""
    urut = sorted(cocok, key=lambda c: (c[2] != KUAT, c[0]))
    bukti, terpakai, teks_terlihat, n_kuat = [], [], set(), 0
    for s, e, kekuatan in urut:
        kunci = re.sub(r"\s+", " ", datar[s:e]).lower()
        if kunci in teks_terlihat:
            continue
        awal, akhir = _jendela(datar, s, e, cfg)
        if any(awal < b and a < akhir for a, b in terpakai):
            continue
        potongan = datar[awal:akhir].strip()
        if not potongan:
            continue
        teks_terlihat.add(kunci)
        terpakai.append((awal, akhir))
        bukti.append(potongan)
        if kekuatan == KUAT:
            n_kuat += 1
        if len(bukti) >= cfg.ciri_bukti_maks:
            break
    return bukti, n_kuat


def deteksi_regex(teks: str, cfg: Pengaturan | None = None) -> list[CiriRegex]:
    """Masukan: teks (bersih). Keluaran: ciri yang terdeteksi regex, urutan sesuai ID_CIRI_TERKUNCI.

    Kekuatan sebuah ciri adalah "kuat" kalau ada satu saja pola kuat yang cocok.
    """
    cfg = cfg or pengaturan_global
    datar = _rapikan(teks)
    hasil = []
    for id_ciri in ID_BISA_DITANDAI:
        if id_ciri == "ajakan_menyebarkan":
            cocok = _cocok_ajakan(datar)
        elif id_ciri == "link_mencurigakan":
            cocok = _cocok_tautan(datar)
        elif id_ciri == "permintaan_data_rahasia":
            cocok = _cocok_permintaan(datar)
        elif id_ciri == "kapital_tanda_seru":
            cocok = _cocok_kapital(datar, cfg)
        else:
            cocok = _cocok_pola(_POLA[id_ciri], datar)
        if not cocok:
            continue
        bukti, n_kuat = _kumpulkan_bukti(datar, cocok, cfg)
        if bukti:
            hasil.append(CiriRegex(id_ciri, KUAT if any(c[2] == KUAT for c in cocok) else LEMAH, bukti, n_kuat))
    return hasil


# ---------------------------------------------------------------------------
# Penggabungan dengan kandidat LLM
# ---------------------------------------------------------------------------

def _normalisasi_dengan_peta(teks: str) -> tuple[str, list[int]]:
    """Huruf kecil dan rentetan spasi/baris baru menjadi satu spasi. `peta[i]` = indeks karakter asli untuk
    karakter ke-i hasil normalisasi, supaya kutipan terverifikasi bisa diambil dari teks aslinya."""
    keluar, peta, spasi_terakhir = [], [], True  # True: buang spasi di awal
    for i, c in enumerate(teks):
        if c.isspace():
            if not spasi_terakhir:
                keluar.append(" ")
                peta.append(i)
            spasi_terakhir = True
        else:
            keluar.append(c.lower())
            peta.append(i)
            spasi_terakhir = False
    while keluar and keluar[-1] == " ":
        keluar.pop()
        peta.pop()
    return "".join(keluar), peta


def _norm(teks: str) -> str:
    return _normalisasi_dengan_peta(teks)[0]


def _kutipan_asli(teks: str, kutipan: str) -> str | None:
    """Kutipan sebagaimana tertulis di teks asli (spasi dirapikan), atau None kalau tidak ada di teks."""
    norm_teks, peta = _normalisasi_dengan_peta(teks)
    norm_kutip = _norm(kutipan)
    if not norm_kutip:
        return None
    awal = norm_teks.find(norm_kutip)
    if awal < 0:
        return None
    asli = teks[peta[awal]: peta[awal + len(norm_kutip) - 1] + 1]
    return re.sub(r"\s+", " ", asli).strip()


def _pangkas(bukti: str, cfg: Pengaturan) -> str:
    if len(bukti) <= cfg.ciri_bukti_maks_karakter:
        return bukti
    potong = bukti[: cfg.ciri_bukti_maks_karakter]
    if " " in potong and bukti[cfg.ciri_bukti_maks_karakter] != " ":
        potong = potong.rsplit(" ", 1)[0]
    return potong.rstrip(" ,;:-")  # tanpa elipsis: bukti harus potongan persis dari teks


def _tumpang_tindih(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    return bool(na) and bool(nb) and (na in nb or nb in na)


_TLD_BUKTI = (
    r"(?:com|id|net|org|co|xyz|top|click|icu|buzz|cfd|sbs|link|info|me|ly|gl|cc|site|online|store|shop|app|biz|vip|"
    r"live|club|io|tv|ws)"
)
_BENTUK_TAUTAN = _p(rf"(?:https?://|www\.)\S+|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.{_TLD_BUKTI}\b")


def _alasan_bukti_llm_ditolak(id_ciri: str, bukti: str, ditemukan_regex: bool, cfg: Pengaturan) -> str | None:
    """Pengaman struktural yang tidak bergantung pada model. Mengembalikan alasan penolakan, atau None bila sah.

    - link_mencurigakan: bukti harus berbentuk tautan (skema, www, domain ber-TLD, atau pemendek). Satu URL saja
      sudah cukup; syarat panjang minimal tidak berlaku.
    - kapital_tanda_seru: bukti harus didominasi huruf kapital atau memuat tanda seru berulang.
    - ciri yang hanya ditemukan LLM: bukti sedikitnya `ciri_llm_min_kata` kata.
    """
    if id_ciri == "link_mencurigakan":
        return None if _BENTUK_TAUTAN.search(bukti) or _RE_PEMENDEK.search(bukti) else "bukan_bentuk_tautan"
    if id_ciri == "kapital_tanda_seru":
        huruf = [c for c in bukti if c.isalpha()]
        rasio = sum(c.isupper() for c in huruf) / len(huruf) if huruf else 0.0
        if rasio < cfg.ciri_llm_kapital_rasio and bukti.count("!") < cfg.ciri_llm_seru_min:
            return "bukan_kapital_atau_seru"
    if not ditemukan_regex and len(re.findall(r"\w+", bukti)) < cfg.ciri_llm_min_kata:
        return "terlalu_pendek"
    return None


def _gabung_bukti(kutipan_llm: list[str], bukti_regex: list[str], n_kuat: int, cfg: Pengaturan) -> list[str]:
    """Urutan: kutipan yang sama dari LLM dan regex, lalu bukti regex dari pola kuat, lalu kutipan LLM saja, lalu
    bukti regex dari pola lemah. Duplikat (saling memuat) dibuang."""
    bersama = [(k, r) for k in kutipan_llm for r in bukti_regex if _tumpang_tindih(k, r)]
    kandidat: list[str] = []
    for k, r in bersama:
        kandidat.append(min(k, r, key=len))  # yang lebih ringkas lebih terfokus
    kandidat += bukti_regex[:n_kuat] + kutipan_llm + bukti_regex[n_kuat:]
    terpilih: list[str] = []
    for b in kandidat:
        if any(_tumpang_tindih(b, t) for t in terpilih):
            continue
        terpilih.append(_pangkas(b, cfg))
        if len(terpilih) >= cfg.ciri_bukti_maks:
            break
    return terpilih


def gabung_ciri(
    hasil_regex: Iterable[CiriRegex],
    kandidat_llm: list[KandidatLLM] | None,
    teks: str,
    cfg: Pengaturan | None = None,
    catatan: list | None = None,
) -> list[CiriTerdeteksi]:
    """Fungsi murni: menggabungkan regex dan kandidat LLM menjadi ciri final (tanpa nama dan penjelasan).

    - `kandidat_llm` None berarti LLM gagal: ciri hanya dari regex (kuat → tinggi, lemah → sedang).
    - Kandidat LLM dengan id di luar ID_BISA_DITANDAI dibuang (termasuk pernah_dibantah, yang ditentukan
      pencarian database). Kutipan yang tidak terverifikasi di `teks` dibuang; ciri tanpa sisa kutipan dibuang.
    - LLM berhasil: tinggi kalau LLM dan regex sama-sama menemukan, atau regex menemukan pola kuat;
      sedang kalau hanya LLM. Ciri yang hanya ditemukan regex dengan pola lemah dibuang.
    - Pengaman struktural (`_alasan_bukti_llm_ditolak`) membuang kutipan LLM yang tidak berbentuk sesuai cirinya;
      ciri hanya hilang kalau tidak ada bukti yang tersisa.
    - sumber_tidak_jelas yang hanya dari LLM dibuang: ketiadaan sumber tidak bisa dikutip. Ciri ini hanya tampil
      bila regex menemukan atribusi samar; LLM yang menandainya menaikkan keyakinannya ke tinggi, dan bukti yang
      dipakai hanya bukti regex.
    `catatan` (list, opsional) diisi {"id", "bukti", "alasan"} untuk tiap kutipan atau ciri yang dibuang.
    Urutan hasil: keyakinan tinggi dulu, lalu urutan ID_CIRI_TERKUNCI.
    """
    cfg = cfg or pengaturan_global
    regex = {c.id: c for c in hasil_regex}
    hasil: list[CiriTerdeteksi] = []

    if kandidat_llm is None:
        for id_ciri in ID_BISA_DITANDAI:
            c = regex.get(id_ciri)
            if c and c.bukti:
                hasil.append(CiriTerdeteksi(id_ciri, c.bukti[: cfg.ciri_bukti_maks], TINGGI if c.kekuatan == KUAT else SEDANG))
    else:
        terverifikasi: dict[str, list[str]] = {}
        for k in kandidat_llm:
            if k.id not in ID_BISA_DITANDAI:
                continue
            for kutipan in k.kutipan:
                asli = _kutipan_asli(teks, kutipan) if isinstance(kutipan, str) else None
                if asli and asli not in terverifikasi.setdefault(k.id, []):
                    terverifikasi[k.id].append(asli)
        def buang(id_ciri: str, bukti: str, alasan: str) -> None:
            if catatan is not None:
                catatan.append({"id": id_ciri, "bukti": bukti, "alasan": alasan})

        for id_ciri in ID_BISA_DITANDAI:
            c = regex.get(id_ciri)
            ditandai_llm = bool(terverifikasi.get(id_ciri))
            dari_llm = []
            for bukti_llm in terverifikasi.get(id_ciri, []):
                if id_ciri == "sumber_tidak_jelas":
                    buang(id_ciri, bukti_llm, "hanya_dari_llm")
                    continue
                alasan = _alasan_bukti_llm_ditolak(id_ciri, bukti_llm, c is not None, cfg)
                if alasan:
                    buang(id_ciri, bukti_llm, alasan)
                else:
                    dari_llm.append(bukti_llm)
            if id_ciri == "sumber_tidak_jelas":
                if not (c and c.bukti):
                    continue  # LLM saja: dibuang. Regex lemah tanpa persetujuan LLM juga dibuang di bawah.
                if not ditandai_llm and c.kekuatan != KUAT:
                    buang(id_ciri, c.bukti[0], "regex_lemah_tanpa_llm")
                    continue
                hasil.append(CiriTerdeteksi(id_ciri, c.bukti[: cfg.ciri_bukti_maks], TINGGI))
                continue
            if not dari_llm and not (c and c.kekuatan == KUAT):
                if c and c.bukti and c.kekuatan != KUAT:
                    buang(id_ciri, c.bukti[0], "regex_lemah_tanpa_llm")
                continue  # tidak ada kutipan LLM yang sah, dan regex tidak kuat (lemah dibuang)
            bukti = _gabung_bukti(dari_llm, c.bukti if c else [], c.n_kuat if c else 0, cfg)
            if not bukti:
                continue
            tinggi = bool(dari_llm and c) or bool(c and c.kekuatan == KUAT)
            hasil.append(CiriTerdeteksi(id_ciri, bukti, TINGGI if tinggi else SEDANG))

    hasil.sort(key=lambda c: c.keyakinan != TINGGI)  # sort stabil: urutan id tetap di dalam kelompok
    return hasil

