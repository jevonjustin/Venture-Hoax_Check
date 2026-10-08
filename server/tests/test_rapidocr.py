"""Uji integrasi dengan RapidOCR sungguhan. Gambar dibuat di memori. Lewati: pytest -m "not rapidocr" """

import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app import contoh, main
from app.konfigurasi import pengaturan
from app.pipeline import baca

pytestmark = pytest.mark.rapidocr

KALIMAT = ["Waspada pesan berantai", "Segera sebarkan ke semua keluarga", "sebelum informasi ini dihapus"]


def png(teks: list[str] | None) -> bytes:
    gambar = Image.new("RGB", (900, 320), "white")
    if teks:
        pena = ImageDraw.Draw(gambar)
        huruf = ImageFont.load_default(size=44)
        for i, baris in enumerate(teks):
            pena.text((30, 25 + i * 90), baris, fill="black", font=huruf)
    keluaran = io.BytesIO()
    gambar.save(keluaran, format="PNG")
    return keluaran.getvalue()


@pytest.fixture(autouse=True)
def siap(monkeypatch):
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)
    monkeypatch.setattr(pengaturan, "ambang_teks_karakter", 20)
    contoh.atur_ulang_giliran()


@pytest.fixture(scope="module")
def klien():
    return TestClient(main.app)


def kirim(klien, data: bytes, params=None):
    return klien.post("/analisis", params=params, files={"gambar": ("p.png", data, "image/png")})


def test_kalimat_indonesia_terbaca(klien):
    r = kirim(klien, png(KALIMAT))
    assert r.status_code == 200, r.text
    teks = r.json()["teks_terbaca"].lower()
    for kata in ("waspada", "berantai", "sebarkan", "keluarga", "informasi", "dihapus"):
        assert kata in teks, teks


def test_gambar_polos_teks_tidak_terbaca(klien):
    r = kirim(klien, png(None))
    assert r.status_code == 422
    assert r.json()["galat"]["kode"] == "teks_tidak_terbaca"


def test_hasil_baca_berisi_kotak_dan_skor():
    hasil = asyncio.run(baca.pembaca.baca(png(KALIMAT)))
    assert "\n" in hasil.teks and len(hasil.baris) >= 2
    for b in hasil.baris:
        assert len(b.kotak) == 4 and all(len(titik) == 2 for titik in b.kotak)
        assert 0.0 <= b.skor <= 1.0
    assert hasil.teks == "\n".join(b.teks for b in hasil.baris)


def test_paksa_tingkat_tetap_membaca_teks_dan_melewati_ambang(klien):
    polos = kirim(klien, png(None), params={"paksa": "hati_hati"})
    assert polos.status_code == 200
    assert polos.json()["tingkat"] == "hati_hati" and polos.json()["teks_terbaca"] == ""
    isi = kirim(klien, png(KALIMAT), params={"paksa": "kuat"}).json()
    assert isi["tingkat"] == "kuat" and "sebarkan" in isi["teks_terbaca"].lower()


def test_paksa_teks_tidak_terbaca_tidak_menjalankan_ocr(klien, monkeypatch):
    dipanggil = []
    asli = baca.pembaca.baca

    async def pengintai(data):
        dipanggil.append(1)
        return await asli(data)

    monkeypatch.setattr(baca.pembaca, "baca", pengintai)
    r = kirim(klien, png(KALIMAT), params={"paksa": "teks_tidak_terbaca"})
    assert r.status_code == 422 and r.json()["galat"]["kode"] == "teks_tidak_terbaca"
    assert dipanggil == []
