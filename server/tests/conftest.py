"""Fixture bersama. Pembaca teks diganti pembaca palsu supaya uji cepat dan tidak bergantung pada model.

Uji yang diberi marker `rapidocr` memakai RapidOCR sungguhan. Lewati dengan: pytest -m "not rapidocr"
"""

import pytest

from app.pipeline import baca, cocok, llm
from app.pipeline.tipe import BarisTeks, HasilBaca

TEKS_PALSU = "Pesan berantai: segera sebarkan informasi ini ke semua keluarga dan teman"


def hasil_palsu(teks: str) -> HasilBaca:
    kotak = ((0.0, 0.0), (100.0, 0.0), (100.0, 20.0), (0.0, 20.0))
    return HasilBaca(teks, [BarisTeks(t, kotak, 0.99) for t in teks.split("\n")] if teks else [])


class PembacaPalsu:
    def __init__(self, teks: str = TEKS_PALSU):
        self.teks = teks
        self.dipanggil = 0
        self.siap = False

    async def siapkan(self) -> float:
        self.siap = True
        return 0.5

    async def baca(self, data: bytes) -> HasilBaca:
        self.dipanggil += 1
        return hasil_palsu(self.teks)


@pytest.fixture(autouse=True)
def pembaca_palsu(request, monkeypatch):
    if request.node.get_closest_marker("rapidocr"):
        yield None
        return
    palsu = PembacaPalsu()
    monkeypatch.setattr(baca, "pembaca", palsu)
    yield palsu


class PencarianPalsu:
    """Pencarian cek fakta palsu: mengembalikan kandidat yang diberikan test, tanpa model e5 atau data_lokal."""

    status = cocok.STATUS_SIAP
    alasan = ""

    def __init__(self, kandidat=None):
        self.kandidat = list(kandidat or [])
        self.kueri: list[str] = []

    async def siapkan(self) -> float:
        return 0.0

    def ringkasan(self) -> str:
        return "siap, 0 artikel (palsu)"

    def cari(self, teks: str, k: int):
        self.kueri.append(teks)
        return self.kandidat[:k]


@pytest.fixture(autouse=True)
def pencarian_palsu(monkeypatch):
    """Tidak ada test yang boleh memuat model e5 asli atau membaca server/data_lokal."""
    palsu = PencarianPalsu()
    monkeypatch.setattr(cocok, "pencarian", palsu)
    yield palsu


class LLMPalsu:
    """Pengganti llm.analisis: tidak ada panggilan jaringan. Bawaannya LLM yang berhasil tetapi tidak menandai
    apa pun dan tidak memberi klaim; test mengisi `hasil` (atau None untuk LLM gagal)."""

    def __init__(self):
        self.hasil = llm.HasilLLM("", [], "palsu", 1)
        self.teks_dikirim: list[str] = []

    async def analisis(self, teks_samar, cfg=None, transport=None, jejak=None):
        from app.konfigurasi import pengaturan

        if not (cfg or pengaturan).llm_aktif:
            return None
        self.teks_dikirim.append(teks_samar)
        if isinstance(self.hasil, Exception):
            raise self.hasil
        return self.hasil


@pytest.fixture(autouse=True)
def kunci_api_terisolasi(monkeypatch, tmp_path):
    """Tidak ada test yang boleh membaca kunci asli: variabel lingkungan dikosongkan dan server/.env dialihkan."""
    for nama in ("GROQ_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(nama, raising=False)
    monkeypatch.setattr(llm, "FILE_ENV", tmp_path / "tidak-ada.env")


@pytest.fixture(autouse=True)
def llm_palsu(request, monkeypatch):
    """pytest tidak boleh memanggil jaringan. Test yang menguji klien LLM sungguhan memakai marker llm_nyata
    dan memberi transport palsu sendiri."""
    palsu = LLMPalsu()
    if not request.node.get_closest_marker("llm_nyata"):
        monkeypatch.setattr(llm, "analisis", palsu.analisis)
    yield palsu
