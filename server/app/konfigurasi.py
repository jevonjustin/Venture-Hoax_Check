"""Satu tempat untuk semua pengaturan server.

Nilai bawaan bisa ditimpa variabel lingkungan. Pengaturan dibaca sekali saat server mulai, dan
nilai yang tidak sah membuat server menolak jalan (lihat __main__.py).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .skema import Tingkat

PAKSA_TEKS_TIDAK_TERBACA = "teks_tidak_terbaca"
# Satu-satunya sumber daftar nilai sah PAKSA_TINGKAT dan query ?paksa= (selaras dengan docs/API.md).
NILAI_PAKSA = tuple(t.value for t in Tingkat) + (PAKSA_TEKS_TIDAK_TERBACA,)


class KonfigurasiTidakValid(ValueError):
    """Pengaturan dari variabel lingkungan tidak sah. Pesannya siap dicetak ke pengguna."""


@dataclass
class Pengaturan:
    host: str = "0.0.0.0"  # semua antarmuka jaringan, supaya HP di jaringan yang sama bisa masuk
    port: int = 8000
    batas_gambar_byte: int = 8 * 1024 * 1024
    # Jeda buatan hanya untuk menguji pembatalan; waktu proses sungguhan sudah ada sejak Sesi 5.2b.
    jeda_min_detik: float = 0.0
    jeda_maks_detik: float = 0.0
    # Jumlah minimum karakter huruf-angka hasil baca; di bawahnya galat teks_tidak_terbaca.
    ambang_teks_karakter: int = 20
    paksa_tingkat: str | None = None
    # Pembersihan teks UI (pipeline/bersih.py). Semua dibuat konservatif: lebih baik ada sisa teks UI
    # daripada membuang kalimat isi.
    # Bilah status hanya dicari di pita ini (fraksi tinggi gambar, dihitung dari tengah baris).
    bersih_pita_atas: float = 0.06
    # Baris tombol, menu, dan penanda waktu hanya dibuang kalau tidak lebih dari ini kata.
    bersih_maks_kata_ui: int = 3
    # Deret menu: minimal jumlah baris pendek sejajar (satu menu situs) agar semuanya dibuang.
    bersih_menu_min_baris: int = 3
    # Dua baris dianggap sejajar kalau selisih tengah vertikalnya tidak lebih dari fraksi tinggi gambar ini.
    bersih_toleransi_sejajar: float = 0.02
    # Baris menu: tiap baris tidak lebih dari ini kata.
    bersih_menu_maks_kata: int = 3
    # Detektor ciri (pipeline/ciri.py).
    ciri_bukti_maks: int = 3  # bukti per ciri
    ciri_bukti_maks_karakter: int = 140  # panjang tiap bukti
    ciri_bukti_konteks: int = 30  # karakter di kiri dan kanan kecocokan yang ikut dikutip
    ciri_kapital_rasio: float = 0.4  # rasio huruf kapital yang dianggap berlebihan (pola lemah)
    ciri_kapital_min_huruf: int = 30  # rasio hanya dinilai kalau teks punya sedikitnya sekian huruf
    ciri_kalimat_kapital_kuat: int = 2  # jumlah kalimat kapital penuh bertanda seru untuk pola kuat
    ciri_seru_beruntun_kuat: int = 3  # jumlah tanda seru beruntun untuk pola kuat
    # Klaim utama heuristik (pipeline/klaim.py).
    klaim_min_kata: int = 5
    klaim_maks_karakter: int = 200
    klaim_skor_minimum: float = 2.0
    # Baris OCR yang tidak berakhir tanda baca disambung ke baris berikutnya kalau panjangnya sedikitnya
    # sekian kali baris terpanjang (kalimat yang terbelah karena lebar layar).
    klaim_rasio_baris_panjang: float = 0.8


def _angka(env: Mapping[str, str], nama: str, tipe: type, bawaan):
    mentah = env.get(nama, "").strip()
    if not mentah:
        return bawaan
    try:
        nilai = tipe(mentah)
    except ValueError:
        raise KonfigurasiTidakValid(f"{nama} harus berupa angka, diterima: {mentah!r}") from None
    if nilai < 0:
        raise KonfigurasiTidakValid(f"{nama} tidak boleh negatif, diterima: {mentah!r}")
    return nilai


def muat(env: Mapping[str, str] = os.environ) -> Pengaturan:
    bawaan = Pengaturan()
    paksa = env.get("PAKSA_TINGKAT", "").strip()
    if paksa and paksa not in NILAI_PAKSA:
        raise KonfigurasiTidakValid(
            f"PAKSA_TINGKAT berisi nilai yang tidak dikenal: {paksa!r}. "
            f"Nilai yang sah: {', '.join(NILAI_PAKSA)} (atau kosong agar hasil bergiliran)."
        )
    pengaturan = Pengaturan(
        host=env.get("CEKHOAKS_HOST", "").strip() or bawaan.host,
        port=_angka(env, "CEKHOAKS_PORT", int, bawaan.port),
        batas_gambar_byte=_angka(env, "CEKHOAKS_BATAS_GAMBAR_BYTE", int, bawaan.batas_gambar_byte),
        jeda_min_detik=_angka(env, "CEKHOAKS_JEDA_MIN", float, bawaan.jeda_min_detik),
        jeda_maks_detik=_angka(env, "CEKHOAKS_JEDA_MAKS", float, bawaan.jeda_maks_detik),
        ambang_teks_karakter=_angka(env, "CEKHOAKS_AMBANG_TEKS", int, bawaan.ambang_teks_karakter),
        paksa_tingkat=paksa or None,
    )
    if pengaturan.jeda_min_detik > pengaturan.jeda_maks_detik:
        raise KonfigurasiTidakValid("CEKHOAKS_JEDA_MIN tidak boleh lebih besar dari CEKHOAKS_JEDA_MAKS")
    return pengaturan


# Dimuat saat modul pertama kali diimpor. Test mengubah field objek ini langsung.
# Pengaturan tidak sah tidak melempar saat impor: galatnya disimpan di `kesalahan`, dan pemanggil
# (python -m app, app.cek, lifespan server) wajib memeriksanya lebih dulu lalu menolak jalan.
kesalahan: KonfigurasiTidakValid | None = None
try:
    pengaturan = muat()
except KonfigurasiTidakValid as _e:
    kesalahan = _e
    pengaturan = Pengaturan()
