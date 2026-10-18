"""Alat uji salah tandai dataset Kaggle (alat/ukur_ciri/salah_tandai_kaggle.py). Tanpa membaca server/data_lokal."""

import importlib.util
import re
from pathlib import Path

from app.pipeline import ciri

jalur = Path(__file__).resolve().parents[1] / "alat" / "ukur_ciri" / "salah_tandai_kaggle.py"
spec = importlib.util.spec_from_file_location("salah_tandai_kaggle_alat", jalur)
alat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alat)

TEKS = "Tolong sebarkan ke semua grup. Katanya beredar di grup 12345!!!"


def test_tanpa_pengecualian_sama_dengan_deteksi_regex():
    assert alat.deteksi(TEKS) == ciri.deteksi_regex(TEKS)
    assert alat.deteksi(TEKS, {"ajakan_menyebarkan": []}) == ciri.deteksi_regex(TEKS)


def test_pengecualian_membuang_kecocokan_yang_tumpang_tindih():
    awal = {c.id for c in alat.deteksi(TEKS)}
    assert "ajakan_menyebarkan" in awal
    peng = {"ajakan_menyebarkan": [re.compile(r"sebarkan", re.IGNORECASE)]}
    assert "ajakan_menyebarkan" not in {c.id for c in alat.deteksi(TEKS, peng)}


def test_pemicu_dinormalisasi_dan_tanpa_kalimat_utuh():
    datar = ciri._rapikan("Segera lakukan tindakan 24 jam sebelum Hapus")
    kecocokan = [c for c in ciri._cocok_pola(ciri._DESAKAN, datar) if c[2] == ciri.KUAT]
    s, e, _ = kecocokan[0]
    hasil = alat.pemicu("desakan_waktu", datar, s, e)
    assert hasil == hasil.lower() and "24" not in hasil
    assert len(hasil.split()) <= 3 or "..." in hasil


def test_varian_ciri_saja_memakai_aturan_tingkat():
    teks = "Tolong sebarkan ke semua grup"  # satu ciri tinggi, tanpa artikel
    assert alat.varian_tanpa_artikel(ciri.deteksi_regex(teks), teks, kuat_saja=False) == "ciri_saja"
    assert alat.varian_tanpa_artikel([], "berita biasa", kuat_saja=False) == ""
