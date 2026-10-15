"""Merapikan tautan yang terpecah lintas baris oleh pembaca teks ("https://" di satu baris, nama domain di baris
berikutnya). Fungsi murni.

Penggabungan sengaja sempit supaya kalimat biasa tidak ikut tersambung: baris harus berakhir dengan potongan URL
yang jelas belum selesai (`://` atau `www.`), dan token pertama baris berikutnya harus berbentuk nama domain atau
jalur. Hasilnya dipakai untuk semua tahap sesudahnya (regex, LLM, dan `teks_terbaca`), sehingga setiap bukti
tetap potongan persis dari teks yang dikembalikan.
"""

import re

# Baris yang berakhir dengan potongan URL belum selesai.
_UJUNG_BELUM_SELESAI = re.compile(r"(?:https?://|ftp://|www\.)$", re.IGNORECASE)
# Token pertama baris berikutnya: nama domain (ada titik lalu huruf), atau jalur yang diawali / .
_DOMAIN = re.compile(r"^[A-Za-z0-9](?:[\w-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9][\w-]*)*\.[A-Za-z]{2,}(?:[/?#]\S*)?$")
_JALUR = re.compile(r"^/\S+$")


def _bentuk_domain_atau_jalur(token: str) -> bool:
    return bool(_DOMAIN.match(token) or _JALUR.match(token))


def gabung_tautan_terpecah(teks: str) -> str:
    """Menggabungkan baris yang berakhir `https://` (atau `www.`) dengan token pertama baris berikutnya bila token itu
    berbentuk domain atau jalur. Sisa baris berikutnya tetap menjadi baris sendiri.

    "https://" yang diikuti kalimat biasa ("https://" lalu "Silakan klik tautan") tidak digabung."""
    baris = teks.split("\n")
    hasil: list[str] = []
    i = 0
    while i < len(baris):
        sekarang = baris[i]
        if i + 1 < len(baris) and _UJUNG_BELUM_SELESAI.search(sekarang.rstrip()):
            berikutnya = baris[i + 1].strip()
            token, _, sisa = berikutnya.partition(" ")
            if token and _bentuk_domain_atau_jalur(token):
                hasil.append(sekarang.rstrip() + token)
                if sisa.strip():
                    hasil.append(sisa.strip())
                i += 2
                continue
        hasil.append(sekarang)
        i += 1
    return "\n".join(hasil)
