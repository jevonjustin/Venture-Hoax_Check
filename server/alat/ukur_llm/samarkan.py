"""Menyamarkan data pribadi pada teks OCR sebelum dikirim ke API LLM. Hanya fungsi murni.

Yang disamarkan: alamat email, nomor telepon, dan nama akun (@...). Tautan dibiarkan karena bisa menjadi bukti
ciri `link_mencurigakan`.
"""

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Tautan dengan skema, dengan www, atau domain polos berakhiran umum (OCR sering membuang skema)
TAUTAN = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|id|co|net|org|me|ly|link|info|xyz|site|online|click|top|app)\b\S*",
    re.IGNORECASE,
)
# Nomor seluler Indonesia (08..., 628..., +628...) dan nomor internasional dengan awalan +
TELEPON = re.compile(r"(?<![\w])(?:\+?62|0)\s?8[\d\s\-.]{7,13}\d(?!\d)|(?<![\w])\+\d{1,3}[\s-]?\d[\d\s-]{7,12}\d(?!\d)")
AKUN = re.compile(r"(?<![\w/@])@[A-Za-z0-9_.]{2,}")

_PENANDA = "\x00{}\x00"


def samarkan(teks: str) -> str:
    teks = EMAIL.sub("[EMAIL]", teks)
    # Lindungi tautan dari aturan telepon dan akun, lalu kembalikan
    simpanan: list[str] = []

    def simpan(m: re.Match) -> str:
        simpanan.append(m.group(0))
        return _PENANDA.format(len(simpanan) - 1)

    teks = TAUTAN.sub(simpan, teks)
    teks = TELEPON.sub("[NOMOR]", teks)
    teks = AKUN.sub("[AKUN]", teks)
    for i, asli in enumerate(simpanan):
        teks = teks.replace(_PENANDA.format(i), asli)
    return teks
