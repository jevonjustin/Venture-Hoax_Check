"""Tahap 4: mencocokkan klaim dengan database cek fakta. (Dummy; parameter ctx hanya dipakai dummy.)"""

from .. import contoh
from ..skema import ArtikelCekFakta
from .tipe import Konteks


def cari_kecocokan(klaim: str | None, ctx: Konteks) -> list[ArtikelCekFakta]:
    """Masukan: klaim utama. Keluaran: artikel mirip, diurutkan dari skor tertinggi (boleh kosong)."""
    return contoh.CONTOH[ctx.skenario].cek_fakta
