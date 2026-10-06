"""Galat yang dikenal API (kode dan status ada di docs/API.md)."""

from fastapi.responses import JSONResponse

from .skema import IsiGalat, ResponsGalat


class GalatApi(Exception):
    def __init__(self, status: int, kode: str, pesan: str):
        super().__init__(pesan)
        self.status = status
        self.kode = kode
        self.pesan = pesan

    def ke_respons(self) -> ResponsGalat:
        return ResponsGalat(galat=IsiGalat(kode=self.kode, pesan=self.pesan))


class DibatalkanKlien(Exception):
    """Klien memutus koneksi (tombol Batal) di tengah analisis."""


def respons_galat(status: int, kode: str, pesan: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=GalatApi(status, kode, pesan).ke_respons().model_dump())
