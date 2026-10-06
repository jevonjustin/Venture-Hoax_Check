"""Tahap 5: mendeteksi ciri hoaks. (Dummy; parameter ctx hanya dipakai dummy.)"""

from .. import contoh
from ..skema import ArtikelCekFakta
from .tipe import CiriTerdeteksi, Konteks


def deteksi_ciri(teks_bersih: str, artikel: list[ArtikelCekFakta], ctx: Konteks) -> list[CiriTerdeteksi]:
    """Masukan: teks bersih dan artikel yang cocok. Keluaran: ciri terdeteksi, paling penting lebih dulu."""
    return contoh.CONTOH[ctx.skenario].ciri
