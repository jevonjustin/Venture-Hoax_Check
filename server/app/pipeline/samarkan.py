"""Penyamaran data pribadi pada teks bersih sebelum dikirim ke API LLM. Hanya fungsi murni.

Yang disamarkan dengan token tetap: nomor telepon ([NOMOR]), alamat email ([EMAIL]), dan nama akun ([AKUN],
termasuk baris yang hanya berisi deret nama akun tanpa tanda @). Nama orang, isi pesan, tautan, dan angka biasa
(tanggal, jam, nominal Rp, jumlah korban) tidak diubah.

Teks yang disamarkan hanya dipakai untuk LLM dan verifikasi kutipannya. Regex ciri dan pencarian cek fakta tetap
memakai teks bersih asli, sehingga `bukti` di respons selalu potongan teks asli (lihat `kutipan_ke_asli`).
"""

import re
from difflib import SequenceMatcher

TOKEN_NOMOR = "[NOMOR]"
TOKEN_EMAIL = "[EMAIL]"
TOKEN_AKUN = "[AKUN]"

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Tautan dilindungi dari aturan telepon dan akun (tautan sendiri bisa menjadi bukti ciri link_mencurigakan).
TAUTAN = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|id|co|net|org|me|ly|link|info|xyz|site|online|click|top|app)\b\S*",
    re.IGNORECASE,
)
# Kandidat nomor: awalan 62/+62/0 lalu 8; pemisah hanya spasi, tanda hubung, atau titik (bukan baris baru).
# Jumlah digit diperiksa terpisah supaya jam (08.30) atau tanggal (08-08-2026) tidak ikut disamarkan.
_TELEPON_ID = re.compile(r"(?<![\w])(?:\+?62|0)[ ]?8[\d \-.]{6,14}\d(?!\d)")
_TELEPON_INTERNASIONAL = re.compile(r"(?<![\w])\+\d{1,3}[ \-]?\d[\d \-]{7,12}\d(?!\d)")
_AWALAN_NOMOR_TERPOTONG = re.compile(r"(?<![\w])\+62[ ]?8\d")  # "+62 82" yang terpotong di tepi tangkapan layar
AKUN = re.compile(r"(?<![\w/@])@[A-Za-z0-9_.]{2,}")

_PENANDA = "\x00{}\x00"
_TOKEN_AKUN = re.compile(r"[A-Za-z0-9._]{4,}")
_TLD_TAUTAN = re.compile(r"\.(?:com|id|me|co|net|org|ly|link|xyz|top|app|site|info|online|click)$", re.IGNORECASE)
_NOMINAL = re.compile(r"(?i)(?:rp|usd|idr)?[\d.,]+\w{0,3}")
BATAS_POTONGAN_BERSAMA = 6  # huruf
PANJANG_MIN_AKUN_BERSAMA = 10  # karakter; nama akun yang berbagi potongan biasanya panjang


def _jumlah_digit(teks: str) -> int:
    return sum(c.isdigit() for c in teks)


def _ganti_telepon_id(m: re.Match) -> str:
    return TOKEN_NOMOR if 10 <= _jumlah_digit(m.group()) <= 14 else m.group()


def _ganti_telepon_internasional(m: re.Match) -> str:
    return TOKEN_NOMOR if 9 <= _jumlah_digit(m.group()) <= 15 else m.group()


def _huruf_berbagi(a: str, b: str) -> int:
    """Panjang potongan huruf terpanjang yang sama pada dua token (angka, titik, garis bawah memisahkan potongan)."""
    terbaik = 0
    for x in re.findall(r"[a-z]+", a):
        for y in re.findall(r"[a-z]+", b):
            cocok = SequenceMatcher(None, x, y, autojunk=False).find_longest_match(0, len(x), 0, len(y))
            terbaik = max(terbaik, cocok.size)
    return terbaik


def _deret_akun(token: list[str]) -> bool:
    """Deret token (huruf kecil) yang berbagi potongan huruf >= 6 antara dua token berbeda yang sama-sama panjang
    (>= 10 karakter), dan tidak ada token lain yang bukan bagian dari pasangan itu, duplikatnya, atau bertanda
    angka/titik/garis bawah. Kata-kata biasa yang kebetulan berbagi akar ("senggang", "mengganggu") tidak lolos."""
    bersama: set[int] = set()
    for i in range(len(token)):
        for j in range(i + 1, len(token)):
            if token[i] != token[j] and len(token[i]) >= PANJANG_MIN_AKUN_BERSAMA and len(token[j]) >= PANJANG_MIN_AKUN_BERSAMA:
                if _huruf_berbagi(token[i], token[j]) >= BATAS_POTONGAN_BERSAMA:
                    bersama.update((i, j))
    if len(bersama) < 2:
        return False
    dikenal = {token[i] for i in bersama}
    return all(i in bersama or token[i] in dikenal or re.search(r"[0-9._]", token[i]) for i in range(len(token)))


def _token_baris(baris: str) -> list[str]:
    """Token baris tanpa tanda baca akhir kalimat/koma di ujungnya ("vocazine." bukan nama akun bertitik)."""
    return [t.rstrip(".,;:!?") for t in baris.split()]


def apakah_baris_akun(baris: str) -> bool:
    """Baris yang hanya berisi nama akun atau deretan nama akun tanpa tanda @ (infografis, kredit).

    Semua token harus berbentuk nama akun (huruf, angka, titik, garis bawah; sedikitnya 4 karakter dan satu huruf;
    bukan nama domain; bukan huruf kapital semua seperti "1.OPERATOR" atau "15DESEMBER2020"), dan salah satu dari:
    - sedikitnya dua token panjang berbagi potongan yang sama >= 6 huruf ("humaspolresmerangin",
      "polresmerangin6") dan token lainnya hanya pasangan atau duplikatnya, atau
    - sedikitnya setengah token memuat angka, titik di dalam token, atau garis bawah (dan punya >= 4 huruf, bukan
      nominal).
    Kalimat isi berhuruf kecil, betapapun panjang kata-katanya, tidak memenuhi syarat."""
    token = _token_baris(baris)
    if not token or len(token) > 8:
        return False
    for t in token:
        huruf = "".join(c for c in t if c.isalpha())
        if not _TOKEN_AKUN.fullmatch(t) or not huruf or _TLD_TAUTAN.search(t) or (len(huruf) >= 4 and huruf.isupper()):
            return False
    if len(token) >= 2 and _deret_akun([t.lower() for t in token]):
        return True
    bertanda = [
        t for t in token
        if re.search(r"[0-9_]|[A-Za-z0-9]\.[A-Za-z0-9]", t) and sum(c.isalpha() for c in t) >= 4 and not _NOMINAL.fullmatch(t)
    ]
    return bool(bertanda) and len(bertanda) * 2 >= len(token)


def tandai_baris_akun(baris: list[str]) -> list[bool]:
    """Menandai baris yang hanya berisi nama akun. Selain `apakah_baris_akun` per baris, deretan baris berurutan
    yang masing-masing satu token berbentuk nama akun (OCR sering memecah infografis satu akun per baris) ditandai
    semuanya bila dua di antaranya berbagi potongan >= 6 huruf ("humaspolresmerangin", "fpolresmerangin")."""
    tanda = [apakah_baris_akun(b) for b in baris]
    i = 0
    while i < len(baris):
        j = i
        while j < len(baris) and len(baris[j].split()) == 1 and _TOKEN_AKUN.fullmatch(baris[j].strip())                 and re.search(r"[A-Za-z]", baris[j]) and not _TLD_TAUTAN.search(baris[j].strip()):
            j += 1
        if j - i >= 2 and _deret_akun([b.strip().lower() for b in baris[i:j]]):
            for k in range(i, j):
                tanda[k] = True
        i = max(j, i + 1)
    return tanda


def samarkan(teks: str) -> str:
    """Mengganti email, nomor telepon, dan nama akun dengan token tetap. Panjang teks boleh berubah."""
    # Baris deret akun (tanpa @) diganti per token sebelum aturan lain.
    asli = teks.split("\n")
    baris = [" ".join(TOKEN_AKUN for _ in b.split()) if akun else b for b, akun in zip(asli, tandai_baris_akun(asli))]
    teks = "\n".join(baris)
    teks = EMAIL.sub(TOKEN_EMAIL, teks)

    simpanan: list[str] = []

    def simpan(m: re.Match) -> str:
        simpanan.append(m.group(0))
        return _PENANDA.format(len(simpanan) - 1)

    teks = TAUTAN.sub(simpan, teks)
    teks = _TELEPON_ID.sub(_ganti_telepon_id, teks)
    teks = _TELEPON_INTERNASIONAL.sub(_ganti_telepon_internasional, teks)
    teks = _AWALAN_NOMOR_TERPOTONG.sub(TOKEN_NOMOR, teks)
    teks = AKUN.sub(TOKEN_AKUN, teks)
    for i, asli in enumerate(simpanan):
        teks = teks.replace(_PENANDA.format(i), asli)
    return teks


_POLA_TOKEN = {
    TOKEN_NOMOR: r"(?:\+?62|0)[ ]?8[\d \-.]{6,14}\d|\+\d{1,3}[ \-]?\d[\d \-]{7,12}\d|\+62[ ]?8\d",
    TOKEN_EMAIL: r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    TOKEN_AKUN: r"@?[A-Za-z0-9_.]{2,}",
}
_TOKEN_DI_KUTIPAN = re.compile("(" + "|".join(re.escape(t) for t in _POLA_TOKEN) + ")", re.IGNORECASE)


def _normal(teks: str) -> str:
    return re.sub(r"\s+", " ", teks).strip().lower()


def kutipan_ke_asli(kutipan: str, teks_samar: str, teks_asli: str) -> str | None:
    """Memetakan kutipan LLM ke potongan `teks_asli`, atau None bila kutipan tidak sah.

    1. Kutipan harus ada di `teks_samar` (teks yang benar-benar dikirim ke LLM); kutipan palsu ditolak.
    2. Kutipan tanpa token penyamaran dicari apa adanya di `teks_asli` (isi keduanya sama di luar token).
    3. Kutipan yang memuat [NOMOR], [EMAIL], atau [AKUN] dicari di `teks_asli` dengan token diganti pola data
       yang disamarkan, sehingga yang dikembalikan tetap potongan persis dari teks asli.
    Spasi dan baris baru dirapikan menjadi satu spasi; huruf besar-kecil tidak dibedakan saat mencari."""
    k = _normal(kutipan)
    if not k or k not in _normal(teks_samar):
        return None
    bagian = _TOKEN_DI_KUTIPAN.split(k)
    pola = []
    for b in bagian:
        if not b:
            continue
        token = next((t for t in _POLA_TOKEN if b == t.lower()), None)
        pola.append(f"(?:{_POLA_TOKEN[token]})" if token else re.escape(b).replace(chr(92) + " ", chr(92) + "s+"))
    try:
        m = re.search("".join(pola), teks_asli, flags=re.IGNORECASE)
    except re.error:
        return None
    return re.sub(r"\s+", " ", m.group()).strip() if m else None
