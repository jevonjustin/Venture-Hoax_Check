"""Tahap 5: mendeteksi ciri hoaks (detektor regex dan penggabungan dengan kandidat LLM).

Dua jalur:
- `deteksi_regex(teks)`: detektor regex/heuristik sederhana per ciri, dengan dua kekuatan pola. Pola "kuat" adalah
  frasa yang hampir pasti menandai ciri; pola "lemah" adalah kata yang juga sering muncul di teks biasa.
- `gabung_ciri(...)`: fungsi murni yang menggabungkan hasil regex dengan kandidat dari LLM. LLM hanya menandai
  kandidat; ciri diterima kalau kutipannya terverifikasi ada di teks. Penjelasan tidak dibuat di sini
  (selalu dari template.py).

`pernah_dibantah` tidak punya detektor: ciri itu ditentukan hasil pencarian database cek fakta (Sesi 5.5).

`deteksi_ciri` di bawah adalah dummy yang masih dipakai /analisis sampai Sesi 5.5.
"""

import re
from collections.abc import Iterable

from .. import contoh
from ..konfigurasi import Pengaturan, pengaturan as pengaturan_global
from ..skema import ArtikelCekFakta, ID_CIRI_TERKUNCI
from .tipe import CiriRegex, CiriTerdeteksi, KandidatLLM, Konteks

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
    (KUAT, _p(r"\bsebelum\s+(?:(?:segera|keburu)\s+)?(?:di\s?)?(?:hapus|blokir|tutup|hilang|tarik|terlambat|kedaluwarsa|kadaluarsa)")),
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

_POLA = {
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


def _cocok_tautan(datar: str) -> list[tuple[int, int, str]]:
    hasil = _cocok_pola(_LINK_KUAT, datar)
    for m in _URL_UMUM.finditer(datar):
        url = m.group().rstrip(".,;:!?)")
        if _DOMAIN_DIKECUALIKAN.match(url) or any(m.start() < a and s < m.end() for s, a, _ in hasil):
            continue
        hasil.append((m.start(), m.start() + len(url), LEMAH))
    return hasil


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


def _jendela(datar: str, s: int, e: int, cfg: Pengaturan) -> tuple[int, int, bool]:
    """Potongan teks di sekitar kecocokan [s, e), dipotong di batas kata. Mengembalikan (awal, akhir, terpotong)."""
    maks = cfg.ciri_bukti_maks_karakter
    if e - s >= maks:
        akhir = s + maks
        while akhir > s and akhir < len(datar) and datar[akhir] != " ":
            akhir -= 1
        return s, (akhir if akhir > s else s + maks), True
    konteks = min(cfg.ciri_bukti_konteks, (maks - (e - s)) // 2)
    awal, akhir = max(0, s - konteks), min(len(datar), e + konteks)
    while awal < s and awal > 0 and datar[awal - 1] != " ":
        awal += 1
    while akhir > e and akhir < len(datar) and datar[akhir] != " ":
        akhir -= 1
    return awal, akhir, False


def _kumpulkan_bukti(datar: str, cocok: list[tuple[int, int, str]], cfg: Pengaturan) -> list[str]:
    """Bukti: pola kuat lebih dulu, lalu lemah; urutan kemunculan di dalam tiap kelompok. Jendela yang
    saling tumpang tindih hanya dihitung sekali. Maksimal `ciri_bukti_maks`."""
    urut = sorted(cocok, key=lambda c: (c[2] != KUAT, c[0]))
    bukti, terpakai = [], []
    for s, e, _ in urut:
        awal, akhir, terpotong = _jendela(datar, s, e, cfg)
        if any(awal < b and a < akhir for a, b in terpakai):
            continue
        terpakai.append((awal, akhir))
        potongan = datar[awal:akhir].strip()
        if potongan:
            bukti.append(potongan + ("…" if terpotong else ""))
        if len(bukti) >= cfg.ciri_bukti_maks:
            break
    return bukti


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
        elif id_ciri == "kapital_tanda_seru":
            cocok = _cocok_kapital(datar, cfg)
        else:
            cocok = _cocok_pola(_POLA[id_ciri], datar)
        if not cocok:
            continue
        bukti = _kumpulkan_bukti(datar, cocok, cfg)
        if bukti:
            hasil.append(CiriRegex(id_ciri, KUAT if any(c[2] == KUAT for c in cocok) else LEMAH, bukti))
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
    return potong.rstrip() + "…"


def _tumpang_tindih(a: str, b: str) -> bool:
    na, nb = _norm(a).rstrip("…"), _norm(b).rstrip("…")
    return bool(na) and bool(nb) and (na in nb or nb in na)


def _gabung_bukti(kutipan_llm: list[str], bukti_regex: list[str], cfg: Pengaturan) -> list[str]:
    """Urutan: yang sama dari kedua sumber, lalu hanya-LLM, lalu hanya-regex. Duplikat dibuang."""
    bersama = [(k, r) for k in kutipan_llm for r in bukti_regex if _tumpang_tindih(k, r)]
    kandidat: list[str] = []
    for k, r in bersama:
        kandidat.append(min(k, r, key=len))  # yang lebih ringkas lebih terfokus
    kandidat += kutipan_llm + bukti_regex
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
) -> list[CiriTerdeteksi]:
    """Fungsi murni: menggabungkan regex dan kandidat LLM menjadi ciri final (tanpa nama dan penjelasan).

    - `kandidat_llm` None berarti LLM gagal: ciri hanya dari regex (kuat → tinggi, lemah → sedang).
    - Kandidat LLM dengan id di luar ID_BISA_DITANDAI dibuang (termasuk pernah_dibantah, yang ditentukan
      pencarian database). Kutipan yang tidak terverifikasi di `teks` dibuang; ciri tanpa sisa kutipan dibuang.
    - LLM berhasil: tinggi kalau LLM dan regex sama-sama menemukan, atau regex menemukan pola kuat;
      sedang kalau hanya LLM. Ciri yang hanya ditemukan regex dengan pola lemah dibuang.
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
        for id_ciri in ID_BISA_DITANDAI:
            dari_llm = terverifikasi.get(id_ciri, [])
            c = regex.get(id_ciri)
            if not dari_llm and not (c and c.kekuatan == KUAT):
                continue  # tidak ada kutipan LLM yang sah, dan regex tidak kuat (lemah dibuang)
            bukti = _gabung_bukti(dari_llm, c.bukti if c else [], cfg)
            if not bukti:
                continue
            tinggi = bool(dari_llm and c) or bool(c and c.kekuatan == KUAT)
            hasil.append(CiriTerdeteksi(id_ciri, bukti, TINGGI if tinggi else SEDANG))

    hasil.sort(key=lambda c: c.keyakinan != TINGGI)  # sort stabil: urutan id tetap di dalam kelompok
    return hasil


# ---------------------------------------------------------------------------
# Dummy yang masih dipakai /analisis sampai Sesi 5.5
# ---------------------------------------------------------------------------

def deteksi_ciri(teks_bersih: str, artikel: list[ArtikelCekFakta], ctx: Konteks) -> list[CiriTerdeteksi]:
    """Dummy. Masukan: teks bersih dan artikel yang cocok. Keluaran: ciri contoh sesuai skenario."""
    return contoh.CONTOH[ctx.skenario].ciri
