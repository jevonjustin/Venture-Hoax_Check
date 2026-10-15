"""Fungsi bantu alat uji_analisis/tahap_b.py: kapan gambar diulang karena Groq kena 429, dan hitungan token."""

import importlib.util
from pathlib import Path

jalur = Path(__file__).resolve().parents[1] / "alat" / "uji_analisis" / "tahap_b.py"
spec = importlib.util.spec_from_file_location("tahap_b_alat", jalur)
alat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alat)


def j(penyedia, status, tunggu=None, token=None):
    return {"penyedia": penyedia, "status": status, "ms": 1, "kode": None, "token": token, "tunggu": tunggu, "kuota": None}


def test_diulang_bila_groq_429_dan_hasil_bukan_dari_groq():
    info = {"penyedia": None, "jejak": [j("groq", 429, 30.0)]}
    assert alat.groq_kena_429(info) == 31.0
    assert alat.groq_kena_429({"penyedia": None, "jejak": [j("groq", 429)]}) == 11.0  # tanpa saran: minimal 10 + 1


def test_tidak_diulang_bila_groq_akhirnya_berhasil_atau_bukan_429():
    assert alat.groq_kena_429({"penyedia": "groq", "jejak": [j("groq", 429, 1.0), j("groq", 200)]}) is None
    assert alat.groq_kena_429({"penyedia": None, "jejak": [j("groq", 500)]}) is None
    assert alat.groq_kena_429({}) is None


def test_tunggu_dibatasi_90_detik():
    assert alat.groq_kena_429({"penyedia": None, "jejak": [j("groq", 429, 600.0)]}) == 91.0


def test_token_gambar_menjumlah_semua_percobaan_sukses():
    info = {"jejak": [
        j("groq", 200, token={"prompt": 900, "completion": 200}),
        j("groq", 429),
        j("groq", 200, token={"prompt": 910, "completion": 50}),
    ]}
    assert alat.token_gambar(info) == (1810, 250)
    assert alat.token_gambar({}) == (0, 0)
