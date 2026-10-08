import io
import logging

import pytest
from PIL import Image

from app import contoh
from conftest import TEKS_PALSU
from app.galat import DibatalkanKlien, GalatApi
from app.konfigurasi import pengaturan
from app.pipeline import orkestrator
from app.pipeline.tipe import Konteks
from app.skema import Tingkat

pytestmark = pytest.mark.anyio

NAMA_TAHAP = ["baca", "bersih", "klaim", "cocok", "ciri", "tingkat", "template"]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def tanpa_jeda(monkeypatch):
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)
    contoh.atur_ulang_giliran()


def gambar() -> bytes:
    keluaran = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 10)).save(keluaran, format="JPEG")
    return keluaran.getvalue()


async def tidak_putus() -> bool:
    return False


async def putus() -> bool:
    return True


def buat_konteks(paksa=None, klien_putus=tidak_putus, jeda=(0.0, 0.0)) -> Konteks:
    return Konteks(id_permintaan="abc123", jeda_detik=jeda, klien_putus=klien_putus, paksa=paksa)


async def test_durasi_setiap_tahap_dicatat_tanpa_teks_atau_gambar(caplog):
    caplog.set_level(logging.INFO)
    hasil = await orkestrator.jalankan(gambar(), buat_konteks(paksa="kuat"))
    baris = [r.getMessage() for r in caplog.records if "tahap:" in r.getMessage()]
    assert len(baris) == 1
    for nama in NAMA_TAHAP:
        assert f"{nama}=" in baris[0]
    log_semua = "\n".join(r.getMessage() for r in caplog.records)
    assert hasil.teks_terbaca not in log_semua
    assert hasil.klaim_utama not in log_semua
    assert "SEBARKAN" not in log_semua


async def test_dibatalkan_klien_menghentikan_pipeline(caplog):
    caplog.set_level(logging.INFO)
    with pytest.raises(DibatalkanKlien):
        await orkestrator.jalankan(gambar(), buat_konteks(klien_putus=putus, jeda=(1.0, 1.0)))
    assert any("dibatalkan klien" in r.getMessage() for r in caplog.records)
    assert not any("tahap:" in r.getMessage() for r in caplog.records)


async def test_batal_tidak_memajukan_giliran():
    with pytest.raises(DibatalkanKlien):
        await orkestrator.jalankan(gambar(), buat_konteks(klien_putus=putus, jeda=(1.0, 1.0)))
    hasil = await orkestrator.jalankan(gambar(), buat_konteks())
    assert hasil.tingkat == Tingkat.KUAT  # giliran pertama, belum ada yang terpakai


async def test_teks_tidak_terbaca_tidak_memajukan_giliran():
    with pytest.raises(GalatApi) as e:
        await orkestrator.jalankan(gambar(), buat_konteks(paksa="teks_tidak_terbaca"))
    assert (e.value.status, e.value.kode) == (422, "teks_tidak_terbaca")
    assert (await orkestrator.jalankan(gambar(), buat_konteks())).tingkat == Tingkat.KUAT


async def test_gambar_tidak_sah_ditolak_sebelum_tahap_apa_pun():
    with pytest.raises(GalatApi) as e:
        await orkestrator.jalankan(b"bukan gambar", buat_konteks())
    assert e.value.kode == "bukan_gambar"


@pytest.mark.parametrize("tingkat", list(Tingkat))
async def test_hasil_sama_dengan_contoh(tingkat):
    hasil = await orkestrator.jalankan(gambar(), buat_konteks(paksa=tingkat.value))
    asli = contoh.CONTOH[tingkat]
    assert hasil.tingkat == tingkat
    assert hasil.teks_terbaca == TEKS_PALSU  # teks dari pembaca, bukan dari contoh
    assert hasil.klaim_utama == asli.klaim_utama
    assert [c.id for c in hasil.ciri] == [c.id for c in asli.ciri]
    assert hasil.cek_fakta == asli.cek_fakta
