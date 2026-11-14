"""Pembatas beban /analisis (Sesi 8.1): batas bersamaan, antrean habis -> 503 server_sibuk, /health tetap cepat.

Permintaan dikirim bersamaan lewat httpx.AsyncClient + ASGITransport (satu event loop, tanpa jaringan).
"""

import asyncio
import io
import time

import httpx
import pytest
from PIL import Image

from app import beban, main
from app.konfigurasi import muat, pengaturan, KonfigurasiTidakValid
from app.pipeline import baca, cocok
from conftest import hasil_palsu, TEKS_PALSU


def _jpeg() -> bytes:
    keluaran = io.BytesIO()
    Image.new("RGB", (120, 80), (200, 30, 30)).save(keluaran, format="JPEG")
    return keluaran.getvalue()


GAMBAR = _jpeg()


@pytest.fixture(autouse=True)
def tanpa_jeda(monkeypatch):
    monkeypatch.setattr(pengaturan, "jeda_min_detik", 0.0)
    monkeypatch.setattr(pengaturan, "jeda_maks_detik", 0.0)
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)


def _pasang_pembatas(monkeypatch, maks: int, antre: float) -> beban.PembatasBeban:
    pembatas = beban.PembatasBeban(maks, antre)
    monkeypatch.setattr(beban, "pembatas", pembatas)
    return pembatas


class PembacaTertahan:
    """Pembaca palsu yang menahan setiap pembacaan sampai `lepas` di-set; mencatat puncak pembacaan bersamaan."""

    def __init__(self):
        self.lepas = asyncio.Event()
        self.berjalan = 0
        self.puncak = 0
        self.masuk = 0

    async def siapkan(self) -> float:
        return 0.0

    async def baca(self, data: bytes):
        self.berjalan += 1
        self.masuk += 1
        self.puncak = max(self.puncak, self.berjalan)
        try:
            await self.lepas.wait()
            return hasil_palsu(TEKS_PALSU)
        finally:
            self.berjalan -= 1


def _klien() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app, raise_app_exceptions=False), base_url="http://uji", timeout=30)


async def _kirim(klien: httpx.AsyncClient) -> httpx.Response:
    return await klien.post("/analisis", files={"gambar": ("potongan.jpg", GAMBAR, "image/jpeg")})


async def _tunggu(kondisi, batas: float = 5.0) -> None:
    akhir = time.monotonic() + batas
    while not kondisi():
        assert time.monotonic() < akhir, "kondisi tidak tercapai"
        await asyncio.sleep(0.01)


def test_paling_banyak_dua_bersamaan_sisanya_mengantre_lalu_berhasil(monkeypatch):
    pembatas = _pasang_pembatas(monkeypatch, maks=2, antre=10)
    pembaca = PembacaTertahan()
    monkeypatch.setattr(baca, "pembaca", pembaca)

    async def skenario():
        async with _klien() as klien:
            tugas = [asyncio.create_task(_kirim(klien)) for _ in range(4)]
            await _tunggu(lambda: pembaca.masuk == 2 and pembatas.menunggu == 2)
            await asyncio.sleep(0.1)
            assert (pembaca.berjalan, pembatas.berjalan, pembatas.menunggu) == (2, 2, 2)
            pembaca.lepas.set()
            return await asyncio.gather(*tugas)

    hasil = asyncio.run(skenario())
    assert [r.status_code for r in hasil] == [200] * 4
    assert pembaca.puncak == 2 and pembaca.masuk == 4
    assert (pembatas.berjalan, pembatas.menunggu) == (0, 0)


def test_antrean_habis_dijawab_503_server_sibuk(monkeypatch):
    pembatas = _pasang_pembatas(monkeypatch, maks=1, antre=0.2)
    pembaca = PembacaTertahan()
    monkeypatch.setattr(baca, "pembaca", pembaca)

    async def skenario():
        async with _klien() as klien:
            pertama = asyncio.create_task(_kirim(klien))
            await _tunggu(lambda: pembaca.masuk == 1)
            mulai = time.monotonic()
            kedua = await _kirim(klien)
            lama = time.monotonic() - mulai
            pembaca.lepas.set()
            return await pertama, kedua, lama

    pertama, kedua, lama = asyncio.run(skenario())
    assert pertama.status_code == 200
    assert kedua.status_code == 503
    assert kedua.json()["galat"]["kode"] == "server_sibuk"
    assert set(kedua.json()) == {"galat"} and isinstance(kedua.json()["galat"]["pesan"], str)
    assert 0.15 <= lama < 2.0
    assert pembaca.masuk == 1  # permintaan yang ditolak tidak pernah dibaca
    assert (pembatas.berjalan, pembatas.menunggu) == (0, 0)


def test_antrean_nol_langsung_503_bila_penuh_tetapi_jalan_bila_kosong(monkeypatch):
    _pasang_pembatas(monkeypatch, maks=1, antre=0)
    pembaca = PembacaTertahan()
    monkeypatch.setattr(baca, "pembaca", pembaca)

    async def skenario():
        async with _klien() as klien:
            pertama = asyncio.create_task(_kirim(klien))
            await _tunggu(lambda: pembaca.masuk == 1)
            kedua = await _kirim(klien)
            pembaca.lepas.set()
            pertama = await pertama
            ketiga = await _kirim(klien)  # slot kosong lagi
            return pertama, kedua, ketiga

    pertama, kedua, ketiga = asyncio.run(skenario())
    assert (pertama.status_code, kedua.status_code, ketiga.status_code) == (200, 503, 200)


def test_galat_di_tengah_analisis_melepas_slot(monkeypatch):
    pembatas = _pasang_pembatas(monkeypatch, maks=1, antre=0)

    class PembacaRusak:
        async def baca(self, data):
            raise RuntimeError("rusak")

    monkeypatch.setattr(baca, "pembaca", PembacaRusak())

    async def skenario():
        async with _klien() as klien:
            return [await _kirim(klien) for _ in range(2)]

    hasil = asyncio.run(skenario())
    assert [r.status_code for r in hasil] == [500, 500]  # bukan 503: slot dilepas setelah galat
    assert pembatas.berjalan == 0


def test_health_tidak_terkena_pembatas_saat_slot_penuh(monkeypatch):
    _pasang_pembatas(monkeypatch, maks=1, antre=10)
    pembaca = PembacaTertahan()
    monkeypatch.setattr(baca, "pembaca", pembaca)

    async def skenario():
        async with _klien() as klien:
            tugas = [asyncio.create_task(_kirim(klien)) for _ in range(3)]
            await _tunggu(lambda: pembaca.masuk == 1)
            mulai = time.monotonic()
            health = [await klien.get("/health") for _ in range(5)]
            lama = time.monotonic() - mulai
            pembaca.lepas.set()
            await asyncio.gather(*tugas)
            return health, lama

    health, lama = asyncio.run(skenario())
    assert all(r.status_code == 200 and r.json()["status"] == "ok" for r in health)
    assert lama < 1.0


class MesinOcrLambat:
    """Mesin RapidOCR palsu yang memblokir thread pemanggilnya (seperti onnxruntime)."""

    def __init__(self, detik: float):
        self.detik = detik

    def __call__(self, larik):
        time.sleep(self.detik)

        class Hasil:
            txts = (TEKS_PALSU,)
            boxes = (((0, 0), (100, 0), (100, 20), (0, 20)),)
            scores = (0.99,)

        return Hasil()


class PencarianLambat:
    status = cocok.STATUS_SIAP
    alasan = ""

    def __init__(self, detik: float):
        self.detik = detik

    def cari(self, teks, k):
        time.sleep(self.detik)  # perkalian vektor e5 yang memblokir
        return []


def test_ocr_dan_e5_tidak_memblokir_event_loop(monkeypatch):
    """Pembaca sungguhan (thread pekerja OCR) dan cari_kecocokan (asyncio.to_thread) dengan langkah CPU palsu yang
    memblokir 0,6 detik: /health harus tetap dijawab cepat selama analisis berjalan."""
    _pasang_pembatas(monkeypatch, maks=2, antre=10)
    pembaca = baca.Pembaca(buat_mesin=lambda: MesinOcrLambat(0.6))
    pembaca._mesin = MesinOcrLambat(0.6)  # lewati pemanasan
    monkeypatch.setattr(baca, "pembaca", pembaca)
    monkeypatch.setattr(cocok, "pencarian", PencarianLambat(0.6))

    async def skenario():
        async with _klien() as klien:
            analisis = asyncio.create_task(_kirim(klien))
            jeda, celah = [], []
            terakhir = time.monotonic()
            while not analisis.done():
                # Celah antar giliran loop: langkah yang memblokir event loop terlihat sebagai celah panjang,
                # kapan pun terjadinya (juga di antara dua /health).
                await asyncio.sleep(0.01)
                sekarang = time.monotonic()
                celah.append(sekarang - terakhir)
                mulai = sekarang
                r = await klien.get("/health")
                assert r.status_code == 200
                terakhir = time.monotonic()
                jeda.append(terakhir - mulai)
            return await analisis, jeda, celah

    hasil, jeda, celah = asyncio.run(skenario())
    assert hasil.status_code == 200
    assert len(jeda) >= 10  # analisis berjalan sedikitnya 1,2 detik (OCR lalu e5)
    assert max(jeda) < 0.3
    assert max(celah) < 0.3


def test_pengaturan_pembatas_dari_lingkungan():
    bawaan = muat({})
    assert (bawaan.maks_bersamaan, bawaan.antre_maks_detik) == (2, 20.0)
    p = muat({"CEKHOAKS_MAKS_BERSAMAAN": "3", "CEKHOAKS_ANTRE_MAKS_DETIK": "7.5"})
    assert (p.maks_bersamaan, p.antre_maks_detik) == (3, 7.5)
    assert beban.PembatasBeban.dari(p).maks_bersamaan == 3
    with pytest.raises(KonfigurasiTidakValid, match="CEKHOAKS_MAKS_BERSAMAAN"):
        muat({"CEKHOAKS_MAKS_BERSAMAAN": "0"})
    with pytest.raises(KonfigurasiTidakValid, match="CEKHOAKS_ANTRE_MAKS_DETIK"):
        muat({"CEKHOAKS_ANTRE_MAKS_DETIK": "lama"})
