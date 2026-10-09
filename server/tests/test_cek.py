import asyncio
import io
import json

from PIL import Image

from app import cek, contoh
from app.konfigurasi import pengaturan


def gambar() -> bytes:
    keluaran = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 10)).save(keluaran, format="PNG")
    return keluaran.getvalue()


def analisis(data: bytes, paksa=None) -> dict:
    return asyncio.run(cek.analisis_gambar(data, paksa))


def test_sukses_berformat_respons_api():
    contoh.atur_ulang_giliran()
    hasil = analisis(gambar(), "hati_hati")
    assert set(hasil) == {"id_permintaan", "tingkat", "klaim_utama", "ciri", "cek_fakta", "teks_terbaca", "durasi_ms"}
    assert hasil["tingkat"] == "hati_hati"
    json.dumps(hasil)  # harus bisa dijadikan JSON (tanggal sudah berupa teks)


def test_tanpa_jeda_buatan():
    hasil = analisis(gambar(), "kuat")
    assert hasil["durasi_ms"] < 500  # jeda buatan bawaan 1-3 detik tidak berlaku


def test_galat_berformat_seragam():
    hasil = analisis(b"bukan gambar")
    assert set(hasil) == {"galat"} and set(hasil["galat"]) == {"kode", "pesan"}
    assert hasil["galat"]["kode"] == "bukan_gambar"


def test_teks_tidak_terbaca():
    assert analisis(gambar(), "teks_tidak_terbaca")["galat"]["kode"] == "teks_tidak_terbaca"


def test_main_berkas_tidak_ada_dan_argumen_salah():
    assert cek.main(["folder-tidak-ada/tidak-ada.jpg"]) == 2
    assert cek.main([]) == 2


def test_main_dengan_gambar_dari_memori(monkeypatch, capsys):
    """Path.read_bytes diganti agar gambar uji tetap di memori dan tidak ditulis ke disk."""
    monkeypatch.setattr(cek.Path, "read_bytes", lambda self: gambar())
    monkeypatch.setattr(pengaturan, "paksa_tingkat", "tidak_ditemukan")
    assert cek.main(["gambar-contoh.jpg"]) == 0
    assert json.loads(capsys.readouterr().out)["tingkat"] == "tidak_ditemukan"

    monkeypatch.setattr(pengaturan, "paksa_tingkat", "teks_tidak_terbaca")
    assert cek.main(["gambar-contoh.jpg"]) == 1
    assert json.loads(capsys.readouterr().out)["galat"]["kode"] == "teks_tidak_terbaca"


def test_diagnostik_dicetak_ke_stderr_dan_stdout_tetap_json(monkeypatch, capsys):
    monkeypatch.setattr(cek.Path, "read_bytes", lambda self: gambar())
    monkeypatch.setattr(pengaturan, "paksa_tingkat", "kuat")
    assert cek.main(["gambar-contoh.jpg"]) == 0
    keluar = capsys.readouterr()
    assert json.loads(keluar.out)["tingkat"] == "kuat"
    assert "=== Teks mentah ===" in keluar.err and "=== Teks bersih ===" in keluar.err
    assert "=== Baris dibuang (0) ===" in keluar.err
