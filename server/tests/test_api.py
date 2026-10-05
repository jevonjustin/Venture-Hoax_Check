import builtins
import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import contoh, main

klien = TestClient(main.app)


@pytest.fixture(autouse=True)
def tanpa_jeda(monkeypatch):
    monkeypatch.setattr(main, "JEDA_DETIK", (0.0, 0.0))
    monkeypatch.delenv("PAKSA_TINGKAT", raising=False)
    contoh.atur_ulang_giliran()


def buat_gambar(format_="JPEG", ukuran=(120, 80)) -> bytes:
    keluaran = io.BytesIO()
    Image.new("RGB", ukuran, (200, 30, 30)).save(keluaran, format=format_)
    return keluaran.getvalue()


def kirim(data: bytes, params=None, nama_field="gambar"):
    return klien.post("/analisis", params=params, files={nama_field: ("potongan.jpg", data, "image/jpeg")})


def periksa_galat(respons, status: int, kode: str):
    assert respons.status_code == status, respons.text
    isi = respons.json()
    assert set(isi) == {"galat"}
    assert isi["galat"]["kode"] == kode
    assert isinstance(isi["galat"]["pesan"], str)


# --- Sukses ---


def test_health():
    r = klien.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "versi": main.VERSI}


def test_analisis_sukses_sesuai_kontrak():
    r = kirim(buat_gambar())
    assert r.status_code == 200
    isi = r.json()
    assert set(isi) == {"id_permintaan", "tingkat", "klaim_utama", "ciri", "cek_fakta", "teks_terbaca", "durasi_ms"}
    assert isi["tingkat"] == "kuat"
    assert len(isi["id_permintaan"]) == 32
    assert isinstance(isi["durasi_ms"], int)
    for ciri in isi["ciri"]:
        assert set(ciri) == {"id", "nama", "bukti", "penjelasan", "keyakinan"}
        assert isinstance(ciri["bukti"], list) and ciri["bukti"]
    for artikel in isi["cek_fakta"]:
        assert set(artikel) == {"judul", "sumber", "url", "skor_kemiripan", "label", "tanggal"}
    assert isi["cek_fakta"][0]["tanggal"] == "2025-11-04"
    assert isi["cek_fakta"][1]["tanggal"] is None


def test_png_juga_diterima():
    assert kirim(buat_gambar("PNG")).status_code == 200


def test_tanpa_paksa_bergiliran():
    hasil = [kirim(buat_gambar()).json()["tingkat"] for _ in range(4)]
    assert hasil == ["kuat", "hati_hati", "tidak_ditemukan", "kuat"]


@pytest.mark.parametrize("tingkat", ["kuat", "hati_hati", "tidak_ditemukan"])
def test_paksa_lewat_query(tingkat):
    r = kirim(buat_gambar(), params={"paksa": tingkat})
    assert r.status_code == 200
    assert r.json()["tingkat"] == tingkat


def test_tidak_ditemukan_tanpa_ciri():
    isi = kirim(buat_gambar(), params={"paksa": "tidak_ditemukan"}).json()
    assert isi["ciri"] == [] and isi["cek_fakta"] == []


def test_paksa_lewat_env(monkeypatch):
    monkeypatch.setenv("PAKSA_TINGKAT", "hati_hati")
    assert [kirim(buat_gambar()).json()["tingkat"] for _ in range(2)] == ["hati_hati", "hati_hati"]


def test_query_mengalahkan_env(monkeypatch):
    monkeypatch.setenv("PAKSA_TINGKAT", "hati_hati")
    assert kirim(buat_gambar(), params={"paksa": "kuat"}).json()["tingkat"] == "kuat"


# --- Galat ---


def test_teks_tidak_terbaca_lewat_query():
    periksa_galat(kirim(buat_gambar(), params={"paksa": "teks_tidak_terbaca"}), 422, "teks_tidak_terbaca")


def test_teks_tidak_terbaca_lewat_env(monkeypatch):
    monkeypatch.setenv("PAKSA_TINGKAT", "teks_tidak_terbaca")
    periksa_galat(kirim(buat_gambar()), 422, "teks_tidak_terbaca")


def test_paksa_query_tidak_dikenal():
    periksa_galat(kirim(buat_gambar(), params={"paksa": "aman"}), 422, "permintaan_tidak_valid")


def test_paksa_env_tidak_dikenal(monkeypatch):
    monkeypatch.setenv("PAKSA_TINGKAT", "aman")
    periksa_galat(kirim(buat_gambar()), 500, "galat_server")


def test_gambar_kosong():
    periksa_galat(kirim(b""), 400, "gambar_kosong")


def test_bukan_gambar():
    periksa_galat(kirim(b"ini teks biasa, bukan gambar"), 415, "bukan_gambar")


def test_format_gambar_lain_ditolak():
    periksa_galat(kirim(buat_gambar("GIF")), 415, "bukan_gambar")


def test_jpeg_terpotong_ditolak():
    periksa_galat(kirim(buat_gambar()[:200]), 415, "bukan_gambar")


def test_field_gambar_tidak_ada():
    periksa_galat(kirim(buat_gambar(), nama_field="foto"), 422, "permintaan_tidak_valid")


def test_bukan_multipart():
    r = klien.post("/analisis", content=buat_gambar(), headers={"content-type": "image/jpeg"})
    periksa_galat(r, 422, "permintaan_tidak_valid")


def test_terlalu_besar():
    periksa_galat(kirim(b"\xff" * (main.BATAS_GAMBAR_BYTE + 100 * 1024)), 413, "terlalu_besar")


def test_rute_tidak_ada():
    periksa_galat(klien.get("/tidak-ada"), 404, "tidak_ditemukan")


def test_metode_salah():
    periksa_galat(klien.get("/analisis"), 405, "metode_salah")


# --- Privasi ---


def test_unggahan_besar_tidak_ditulis_ke_disk(monkeypatch):
    """Gambar sekitar 6,7 MB diproses tanpa file sementara maupun file tulis apa pun."""
    data_acak = os.urandom(1500 * 1500 * 3)
    keluaran = io.BytesIO()
    Image.frombytes("RGB", (1500, 1500), data_acak).save(keluaran, format="PNG")
    data = keluaran.getvalue()
    assert 6 * 1024 * 1024 < len(data) < main.BATAS_GAMBAR_BYTE

    def dilarang(*_, **__):
        raise AssertionError("Server mencoba menulis ke disk")

    for nama in ("SpooledTemporaryFile", "TemporaryFile", "NamedTemporaryFile", "mkstemp"):
        monkeypatch.setattr(tempfile, nama, dilarang)
    buka_asli = builtins.open

    def buka_hanya_baca(file, mode="r", *args, **kwargs):
        if any(m in mode for m in "wax+"):
            dilarang()
        return buka_asli(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", buka_hanya_baca)

    assert kirim(data).status_code == 200
