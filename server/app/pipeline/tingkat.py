"""Tahap 6: menentukan tingkat indikasi. (Dummy; parameter ctx hanya dipakai dummy.)"""

from ..skema import ArtikelCekFakta, Tingkat
from .tipe import CiriTerdeteksi, Konteks


def tentukan_tingkat(ciri: list[CiriTerdeteksi], artikel: list[ArtikelCekFakta], ctx: Konteks) -> Tingkat:
    """Masukan: ciri dan artikel yang cocok. Keluaran: tingkat indikasi (RANCANGAN §9)."""
    return ctx.skenario
