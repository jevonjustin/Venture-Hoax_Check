import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import konfigurasi
from app.konfigurasi import KonfigurasiTidakValid, muat

FOLDER_SERVER = Path(__file__).resolve().parent.parent


def test_nilai_bawaan():
    p = muat({})
    assert (p.host, p.port, p.batas_gambar_byte) == ("0.0.0.0", 8000, 8 * 1024 * 1024)
    assert (p.jeda_min_detik, p.jeda_maks_detik) == (0.0, 0.0)
    assert p.ambang_teks_karakter == 20
    assert p.paksa_tingkat is None


def test_ambang_teks_bisa_ditimpa():
    assert muat({"CEKHOAKS_AMBANG_TEKS": "50"}).ambang_teks_karakter == 50


def test_ditimpa_variabel_lingkungan():
    p = muat({
        "CEKHOAKS_HOST": "127.0.0.1", "CEKHOAKS_PORT": "9000", "CEKHOAKS_BATAS_GAMBAR_BYTE": "1024",
        "CEKHOAKS_JEDA_MIN": "0", "CEKHOAKS_JEDA_MAKS": "0.5", "PAKSA_TINGKAT": "hati_hati",
    })
    assert (p.host, p.port, p.batas_gambar_byte) == ("127.0.0.1", 9000, 1024)
    assert (p.jeda_min_detik, p.jeda_maks_detik) == (0.0, 0.5)
    assert p.paksa_tingkat == "hati_hati"


@pytest.mark.parametrize("nilai", ["", "   "])
def test_paksa_kosong_berarti_tidak_dipaksa(nilai):
    assert muat({"PAKSA_TINGKAT": nilai}).paksa_tingkat is None


@pytest.mark.parametrize("nilai", ["kuat", "hati_hati", "tidak_ditemukan", "teks_tidak_terbaca"])
def test_paksa_sah(nilai):
    assert muat({"PAKSA_TINGKAT": f" {nilai} "}).paksa_tingkat == nilai


def test_paksa_tidak_dikenal_ditolak_dengan_pesan_jelas():
    with pytest.raises(KonfigurasiTidakValid) as e:
        muat({"PAKSA_TINGKAT": "aman"})
    pesan = str(e.value)
    assert "'aman'" in pesan
    for sah in konfigurasi.NILAI_PAKSA:
        assert sah in pesan


@pytest.mark.parametrize("env", [
    {"CEKHOAKS_PORT": "abc"},
    {"CEKHOAKS_AMBANG_TEKS": "-5"},
    {"CEKHOAKS_AMBANG_TEKS": "banyak"},
    {"CEKHOAKS_BATAS_GAMBAR_BYTE": "-1"},
    {"CEKHOAKS_JEDA_MIN": "5", "CEKHOAKS_JEDA_MAKS": "1"},
])
def test_angka_tidak_sah_ditolak(env):
    with pytest.raises(KonfigurasiTidakValid):
        muat(env)


def test_server_menolak_jalan_jika_paksa_tidak_sah():
    """python -m app berhenti sebelum server menyala: kode keluar bukan nol dan pesan jelas."""
    env = {**os.environ, "PAKSA_TINGKAT": "aman"}
    hasil = subprocess.run(
        [sys.executable, "-m", "app"], cwd=FOLDER_SERVER, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert hasil.returncode != 0
    assert "'aman'" in hasil.stderr
    assert "kuat, hati_hati, tidak_ditemukan, teks_tidak_terbaca" in hasil.stderr
