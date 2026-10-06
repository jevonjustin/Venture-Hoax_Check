"""Pemeriksaan gambar di memori. Gambar tidak pernah ditulis ke disk."""

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from .galat import GalatApi

FORMAT_DITERIMA = {"JPEG", "PNG"}


@dataclass(frozen=True)
class InfoGambar:
    format: str
    lebar: int
    tinggi: int
    ukuran_byte: int

    def ringkasan(self) -> str:
        return f"{self.ukuran_byte} byte, {self.lebar}x{self.tinggi} {self.format}"


def periksa_gambar(data: bytes, batas_byte: int) -> InfoGambar:
    """Memastikan data adalah JPEG/PNG utuh dalam batas ukuran. Melempar GalatApi jika tidak."""
    if len(data) == 0:
        raise GalatApi(400, "gambar_kosong", "Gambar 0 byte")
    if len(data) > batas_byte:
        raise GalatApi(413, "terlalu_besar", f"Gambar {len(data)} byte melebihi batas")
    try:
        with Image.open(io.BytesIO(data)) as gambar:
            format_, (lebar, tinggi) = gambar.format, gambar.size
            gambar.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        raise GalatApi(415, "bukan_gambar", f"Isi bukan gambar yang valid: {type(e).__name__}") from e
    if format_ not in FORMAT_DITERIMA:
        raise GalatApi(415, "bukan_gambar", f"Format {format_} tidak diterima")
    return InfoGambar(format_, lebar, tinggi, len(data))
