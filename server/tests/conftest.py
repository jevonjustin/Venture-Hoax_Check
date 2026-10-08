"""Fixture bersama. Pembaca teks diganti pembaca palsu supaya uji cepat dan tidak bergantung pada model.

Uji yang diberi marker `rapidocr` memakai RapidOCR sungguhan. Lewati dengan: pytest -m "not rapidocr"
"""

import pytest

from app.pipeline import baca
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
