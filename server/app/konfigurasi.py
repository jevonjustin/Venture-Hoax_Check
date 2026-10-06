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
    jeda_min_detik: float = 1.0
    jeda_maks_detik: float = 3.0
    paksa_tingkat: str | None = None


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
