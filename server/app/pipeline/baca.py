"""Tahap 1: membaca teks dari gambar. (Dummy; diganti di Sesi 5.2.)"""

import asyncio
import random
import time

from .. import contoh
from ..galat import DibatalkanKlien, GalatApi
from ..konfigurasi import PAKSA_TEKS_TIDAK_TERBACA
from ..skema import Tingkat
from .tipe import Konteks

SELANG_CEK_PUTUS_DETIK = 0.1


async def _jeda_buatan(ctx: Konteks) -> bool:
    """Menunggu sesuai rentang jeda. Mengembalikan False jika klien memutus koneksi di tengah jalan."""
    batas = time.monotonic() + random.uniform(*ctx.jeda_detik)
    while time.monotonic() < batas:
        if await ctx.klien_putus():
            return False
        await asyncio.sleep(SELANG_CEK_PUTUS_DETIK)
    return not await ctx.klien_putus()


async def baca_teks(gambar: bytes, ctx: Konteks) -> str:
    """Masukan: bytes JPEG/PNG yang sudah divalidasi. Keluaran: teks mentah dari gambar.

    Melempar DibatalkanKlien jika klien putus, dan GalatApi(teks_tidak_terbaca) jika tidak ada teks.
    """
    if not await _jeda_buatan(ctx):
        raise DibatalkanKlien
    if ctx.paksa == PAKSA_TEKS_TIDAK_TERBACA:
        raise GalatApi(422, "teks_tidak_terbaca", "Tidak ada teks yang bisa dibaca di gambar")
    # Dummy: skenario dipilih di sini (setelah jeda) supaya giliran tidak maju untuk permintaan yang batal.
    ctx.skenario = Tingkat(ctx.paksa) if ctx.paksa else contoh.tingkat_berikutnya()
    return contoh.CONTOH[ctx.skenario].teks_terbaca
