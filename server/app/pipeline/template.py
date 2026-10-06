"""Tahap 7: menyusun nama dan penjelasan ciri dari template.

Teks penjelasan ditulis sendiri (bukan buatan LLM) dan tanpa kata ganti orang kedua karena tampil
di aplikasi. Isinya baru sebagian dari daftar ciri; Sesi 5.4 melengkapinya.
"""

from ..skema import Ciri
from .tipe import CiriTerdeteksi

_NAMA = {
    "ajakan_menyebarkan": "Ajakan menyebarkan",
    "desakan_waktu": "Desakan waktu",
    "kapital_tanda_seru": "Huruf kapital dan tanda seru berlebihan",
    "link_mencurigakan": "Tautan mencurigakan",
    "sumber_tidak_jelas": "Sumber tidak jelas",
    "pernah_dibantah": "Pernah dibantah media cek fakta",
}

_PENJELASAN = {
    "ajakan_menyebarkan": (
        "Pesan yang mendesak untuk segera disebarkan sering dibuat agar orang ikut menyebarkan "
        "sebelum sempat mengecek kebenarannya."
    ),
    "desakan_waktu": (
        "Kalimat seperti \"sebelum dihapus\" atau \"mulai besok\" membuat pembaca terburu-buru. "
        "Informasi resmi biasanya tetap bisa dicek kapan saja."
    ),
    "kapital_tanda_seru": (
        "Huruf kapital dan tanda seru berlebihan dipakai untuk memancing emosi, "
        "bukan untuk menyampaikan fakta."
    ),
    "link_mencurigakan": (
        "Tautan pemendek menyembunyikan alamat tujuan yang sebenarnya. "
        "Sumber resmi biasanya memakai alamat situs yang jelas."
    ),
    "sumber_tidak_jelas": (
        "Tidak ada nama lembaga, tanggal, atau tautan yang bisa dicek. "
        "Informasi yang benar biasanya menyebut sumbernya dengan jelas."
    ),
    "pernah_dibantah": (
        "Klaim yang mirip sudah pernah diperiksa dan dinyatakan salah oleh media cek fakta."
    ),
}


def susun_penjelasan(ciri: list[CiriTerdeteksi]) -> list[Ciri]:
    """Masukan: ciri terdeteksi. Keluaran: ciri lengkap dengan nama dan penjelasan, urutan tetap."""
    return [
        Ciri(id=c.id, nama=_NAMA[c.id], bukti=c.bukti, penjelasan=_PENJELASAN[c.id], keyakinan=c.keyakinan)
        for c in ciri
    ]
