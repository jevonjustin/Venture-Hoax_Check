"""Data contoh untuk modul pipeline dummy. Semua narasi dan artikel di sini fiktif.

Hanya dipakai selama pipeline masih dummy; tiap sesi tahap 5 menggantikan satu modul pipeline
dengan implementasi sungguhan, dan data ini ikut menyusut.
"""

from dataclasses import dataclass
from datetime import date
from itertools import cycle

from .pipeline.tipe import CiriTerdeteksi
from .skema import ArtikelCekFakta, Tingkat


@dataclass(frozen=True)
class Contoh:
    teks_terbaca: str
    klaim_utama: str
    ciri: list[CiriTerdeteksi]
    cek_fakta: list[ArtikelCekFakta]


CONTOH: dict[Tingkat, Contoh] = {
    Tingkat.KUAT: Contoh(
        teks_terbaca=(
            "VIRAL!! Air keran di Jakarta mengandung zat berbahaya yang menyebabkan penyakit "
            "misterius dalam semalam. Sudah 12 orang dirawat! SEBARKAN ke keluarga sebelum dihapus!!!"
        ),
        klaim_utama="Air keran di Jakarta mengandung zat berbahaya yang menyebabkan penyakit misterius",
        ciri=[
            CiriTerdeteksi("pernah_dibantah", ["Air keran di Jakarta mengandung zat berbahaya"], "tinggi"),
            CiriTerdeteksi("ajakan_menyebarkan", ["SEBARKAN ke keluarga"], "tinggi"),
            CiriTerdeteksi("desakan_waktu", ["sebelum dihapus"], "tinggi"),
            CiriTerdeteksi("kapital_tanda_seru", ["VIRAL!!", "dihapus!!!"], "tinggi"),
            CiriTerdeteksi("sumber_tidak_jelas", ["Sudah 12 orang dirawat!"], "sedang"),
        ],
        cek_fakta=[
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
    ),
    Tingkat.HATI_HATI: Contoh(
        teks_terbaca=(
            "Info dari grup sebelah: mulai besok semua pengendara motor wajib bayar denda Rp500.000 "
            "kalau tidak pakai sarung tangan. Cek di sini bit.ly/info-tilang-baru. Segera bagikan!"
        ),
        klaim_utama="Pengendara motor tanpa sarung tangan didenda Rp500.000 mulai besok",
        ciri=[
            CiriTerdeteksi("link_mencurigakan", ["bit.ly/info-tilang-baru"], "tinggi"),
            CiriTerdeteksi("ajakan_menyebarkan", ["Segera bagikan!"], "tinggi"),
            CiriTerdeteksi("sumber_tidak_jelas", ["Info dari grup sebelah"], "tinggi"),
            CiriTerdeteksi("desakan_waktu", ["mulai besok"], "sedang"),
        ],
        cek_fakta=[],
    ),
    Tingkat.TIDAK_DITEMUKAN: Contoh(
        teks_terbaca=(
            "Pemerintah kota mengumumkan perbaikan jalan di Jalan Merdeka pada 12-14 Oktober. "
            "Pengendara diimbau memakai jalur alternatif. Informasi lengkap tersedia di situs "
            "resmi dinas pekerjaan umum setempat."
        ),
        klaim_utama="Jalan Merdeka diperbaiki pada 12-14 Oktober",
        ciri=[],
        cek_fakta=[],
    ),
}

_giliran = cycle(list(Tingkat))


def tingkat_berikutnya() -> Tingkat:
    """Tingkat bergiliran kuat → hati_hati → tidak_ditemukan → kuat → ..."""
    return next(_giliran)


def atur_ulang_giliran() -> None:
    """Dipakai test agar urutan giliran selalu mulai dari awal."""
    global _giliran
    _giliran = cycle(list(Tingkat))
