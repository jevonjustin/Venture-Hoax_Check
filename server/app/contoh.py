"""Data contoh untuk server dummy (tahap 4). Semua narasi dan artikel di sini fiktif.

Teks penjelasan ditulis tanpa kata ganti orang kedua karena nantinya tampil di aplikasi.
"""

from datetime import date
from itertools import cycle

from .skema import ArtikelCekFakta, Ciri, Tingkat

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


def _ciri(id: str, nama: str, bukti: list[str], keyakinan: str = "tinggi") -> Ciri:
    return Ciri(id=id, nama=nama, bukti=bukti, penjelasan=_PENJELASAN[id], keyakinan=keyakinan)


CONTOH: dict[Tingkat, dict] = {
    Tingkat.KUAT: {
        "teks_terbaca": (
            "VIRAL!! Air keran di Jakarta mengandung zat berbahaya yang menyebabkan penyakit "
            "misterius dalam semalam. Sudah 12 orang dirawat! SEBARKAN ke keluarga sebelum dihapus!!!"
        ),
        "klaim_utama": "Air keran di Jakarta mengandung zat berbahaya yang menyebabkan penyakit misterius",
        "ciri": [
            _ciri("pernah_dibantah", "Pernah dibantah media cek fakta",
                  ["Air keran di Jakarta mengandung zat berbahaya"]),
            _ciri("ajakan_menyebarkan", "Ajakan menyebarkan", ["SEBARKAN ke keluarga"]),
            _ciri("desakan_waktu", "Desakan waktu", ["sebelum dihapus"]),
            _ciri("kapital_tanda_seru", "Huruf kapital dan tanda seru berlebihan",
                  ["VIRAL!!", "dihapus!!!"]),
            _ciri("sumber_tidak_jelas", "Sumber tidak jelas", ["Sudah 12 orang dirawat!"], "sedang"),
        ],
        "cek_fakta": [
            ArtikelCekFakta(
                judul="[SALAH] Air Keran di Jakarta Sebabkan Penyakit Misterius dalam Semalam",
                sumber="Contoh Cek Fakta",
                url="https://example.com/cek-fakta/air-keran-penyakit-misterius",
                skor_kemiripan=0.87,
                label="salah",
                tanggal=date(2025, 11, 4),
            ),
            ArtikelCekFakta(
                judul="[HOAKS] Pesan Berantai Zat Berbahaya dalam Air PAM",
                sumber="Contoh Cek Fakta",
                url="https://example.com/cek-fakta/pesan-berantai-air-pam",
                skor_kemiripan=0.74,
                label="hoaks",
                tanggal=None,
            ),
        ],
    },
    Tingkat.HATI_HATI: {
        "teks_terbaca": (
            "Info dari grup sebelah: mulai besok semua pengendara motor wajib bayar denda Rp500.000 "
            "kalau tidak pakai sarung tangan. Cek di sini bit.ly/info-tilang-baru. Segera bagikan!"
        ),
        "klaim_utama": "Pengendara motor tanpa sarung tangan didenda Rp500.000 mulai besok",
        "ciri": [
            _ciri("link_mencurigakan", "Tautan mencurigakan", ["bit.ly/info-tilang-baru"]),
            _ciri("ajakan_menyebarkan", "Ajakan menyebarkan", ["Segera bagikan!"]),
            _ciri("sumber_tidak_jelas", "Sumber tidak jelas", ["Info dari grup sebelah"]),
            _ciri("desakan_waktu", "Desakan waktu", ["mulai besok"], "sedang"),
        ],
        "cek_fakta": [],
    },
    Tingkat.TIDAK_DITEMUKAN: {
        "teks_terbaca": (
            "Pemerintah kota mengumumkan perbaikan jalan di Jalan Merdeka pada 12-14 Oktober. "
            "Pengendara diimbau memakai jalur alternatif. Informasi lengkap tersedia di situs "
            "resmi dinas pekerjaan umum setempat."
        ),
        "klaim_utama": "Jalan Merdeka diperbaiki pada 12-14 Oktober",
        "ciri": [],
        "cek_fakta": [],
    },
}

_giliran = cycle(list(Tingkat))


def tingkat_berikutnya() -> Tingkat:
    """Tingkat bergiliran kuat → hati_hati → tidak_ditemukan → kuat → ..."""
    return next(_giliran)


def atur_ulang_giliran() -> None:
    """Dipakai test agar urutan giliran selalu mulai dari awal."""
    global _giliran
    _giliran = cycle(list(Tingkat))
