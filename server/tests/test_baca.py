"""Tahap baca dengan pembaca palsu: ambang teks, aturan PAKSA_TINGKAT, pembatalan, antrean, log."""

import asyncio
import io
import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import contoh, main
from app.galat import DibatalkanKlien, GalatApi
from app.konfigurasi import pengaturan
from app.pipeline import baca, orkestrator
from app.pipeline.baca import Pembaca
from app.pipeline.tipe import Konteks
from app.skema import Tingkat
from conftest import TEKS_PALSU, PembacaPalsu

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def bersih(monkeypatch):
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)
    monkeypatch.setattr(pengaturan, "ambang_teks_karakter", 20)
    contoh.atur_ulang_giliran()


def gambar() -> bytes:
    keluaran = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 10)).save(keluaran, format="JPEG")
    return keluaran.getvalue()


async def tidak_putus() -> bool:
    return False


def konteks(paksa=None, klien_putus=tidak_putus) -> Konteks:
    return Konteks(id_permintaan="abc123", jeda_detik=(0.0, 0.0), klien_putus=klien_putus, paksa=paksa)


def pakai(monkeypatch, teks: str) -> PembacaPalsu:
    palsu = PembacaPalsu(teks)
    monkeypatch.setattr(baca, "pembaca", palsu)
    return palsu


async def test_teks_di_bawah_ambang_menjadi_galat_dan_giliran_tidak_maju(monkeypatch):
    pakai(monkeypatch, "Halo dunia")  # 9 huruf
    with pytest.raises(GalatApi) as e:
        await orkestrator.jalankan(gambar(), konteks())
    assert (e.value.status, e.value.kode) == (422, "teks_tidak_terbaca")
    pakai(monkeypatch, TEKS_PALSU)
    assert (await orkestrator.jalankan(gambar(), konteks())).tingkat == Tingkat.KUAT


async def test_tepat_di_ambang_lolos_dan_tanda_baca_tidak_dihitung(monkeypatch):
    pakai(monkeypatch, "a" * 19 + " !!! ... ???\n---")
    with pytest.raises(GalatApi):
        await orkestrator.jalankan(gambar(), konteks())
    pakai(monkeypatch, "a" * 20)
    assert (await orkestrator.jalankan(gambar(), konteks())).teks_terbaca == "a" * 20


async def test_paksa_tingkat_menjalankan_ocr_dan_melewati_ambang(monkeypatch):
    palsu = pakai(monkeypatch, "")
    hasil = await orkestrator.jalankan(gambar(), konteks(paksa="hati_hati"))
    assert palsu.dipanggil == 1
    assert hasil.tingkat == Tingkat.HATI_HATI and hasil.teks_terbaca == ""
    pakai(monkeypatch, TEKS_PALSU)
    assert (await orkestrator.jalankan(gambar(), konteks(paksa="kuat"))).teks_terbaca == TEKS_PALSU


async def test_paksa_teks_tidak_terbaca_tanpa_ocr(monkeypatch):
    palsu = pakai(monkeypatch, TEKS_PALSU)
    with pytest.raises(GalatApi) as e:
        await orkestrator.jalankan(gambar(), konteks(paksa="teks_tidak_terbaca"))
    assert e.value.kode == "teks_tidak_terbaca"
    assert palsu.dipanggil == 0


async def test_klien_putus_setelah_baca_menghentikan_pipeline(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    palsu = pakai(monkeypatch, TEKS_PALSU)
    pemeriksaan = []

    async def putus_setelah_baca() -> bool:
        pemeriksaan.append(palsu.dipanggil)
        return palsu.dipanggil > 0

    with pytest.raises(DibatalkanKlien):
        await orkestrator.jalankan(gambar(), konteks(klien_putus=putus_setelah_baca))
    assert pemeriksaan[-1] == 1  # terdeteksi setelah pembacaan selesai
    assert not any("tahap:" in r.getMessage() for r in caplog.records)
    contoh.atur_ulang_giliran()
    assert (await orkestrator.jalankan(gambar(), konteks())).tingkat == Tingkat.KUAT


async def test_log_memuat_durasi_dan_jumlah_karakter_tanpa_teks(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    pakai(monkeypatch, "RAHASIA kata unik zxqv dalam gambar ini")
    await orkestrator.jalankan(gambar(), konteks())
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "zxqv" not in log and "RAHASIA" not in log
    assert "karakter huruf-angka" in log and "baca=" in log and "teks=" in log


async def test_pembacaan_berjalan_satu_per_satu_di_luar_event_loop():
    aktif, maks, thread = 0, 0, set()
    kunci = threading.Lock()

    class HasilKosong:
        txts, boxes, scores = (), (), ()

    class MesinPalsu:
        def __call__(self, larik):
            nonlocal aktif, maks
            with kunci:
                aktif += 1
                maks = max(maks, aktif)
                thread.add(threading.get_ident())
            time.sleep(0.05)
            with kunci:
                aktif -= 1
            return HasilKosong()

    pembaca = Pembaca(buat_mesin=MesinPalsu)
    await pembaca.siapkan()
    await asyncio.gather(*(pembaca.baca(gambar()) for _ in range(4)))
    assert maks == 1
    assert threading.get_ident() not in thread


def test_startup_memuat_pembaca_dan_mencetak_pesan(pembaca_palsu, capsys):
    with TestClient(main.app) as klien:
        assert klien.get("/health").json()["versi"] == "0.5.1"
    keluaran = capsys.readouterr().out
    assert pembaca_palsu.siap
    assert "Pembaca teks siap" in keluaran and "dimuat dalam 0,5 detik" in keluaran


def test_teks_terbaca_di_respons_api_dari_pembaca():
    klien = TestClient(main.app)
    r = klien.post("/analisis", files={"gambar": ("p.jpg", gambar(), "image/jpeg")})
    assert r.status_code == 200 and r.json()["teks_terbaca"] == TEKS_PALSU
