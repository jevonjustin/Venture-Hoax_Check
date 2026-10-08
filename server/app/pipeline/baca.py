"""Tahap 1: membaca teks dari gambar dengan RapidOCR bawaan (Sesi 5.2b).

Konfigurasi dan cara menggabungkan baris sama dengan kandidat "rapidocr" di
server/alat/ukur_baca/ukur.py, supaya hasil pengukuran Sesi 5.2 berlaku. Tidak ada pembesaran gambar.

Mesin dimuat sekali dan hanya dipakai dari satu thread pekerja. Thread itu sekaligus antrean:
pembacaan berjalan satu per satu, tanpa memblokir event loop.
Teks hasil baca tidak pernah dicatat di log; hanya durasi dan jumlah karakter.
"""

import asyncio
import io
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version

from ..galat import DibatalkanKlien, GalatApi
from ..konfigurasi import PAKSA_TEKS_TIDAK_TERBACA, pengaturan
from .tipe import BarisTeks, HasilBaca, Konteks

SELANG_CEK_PUTUS_DETIK = 0.1

log = logging.getLogger("uvicorn.error").getChild("cekhoaks")


def versi_mesin() -> str:
    return f"RapidOCR {version('rapidocr')}"


def _gambar_pemanasan():
    from PIL import Image, ImageDraw, ImageFont

    gambar = Image.new("RGB", (480, 96), "white")
    ImageDraw.Draw(gambar).text((16, 24), "Cek Hoaks 2025", fill="black", font=ImageFont.load_default(size=40))
    return gambar


def _larik_bgr(gambar):
    import numpy as np

    return np.array(gambar.convert("RGB"))[:, :, ::-1]  # RapidOCR memakai urutan BGR


class Pembaca:
    def __init__(self, buat_mesin=None):
        self._buat_mesin = buat_mesin or self._mesin_rapidocr
        self._mesin = None
        # Satu thread: mesin dibuat dan dipakai di thread yang sama, dan pembacaan tidak tumpang tindih.
        self._pekerja = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")

    @staticmethod
    def _mesin_rapidocr():
        from rapidocr import RapidOCR

        return RapidOCR(params={"Global.log_level": "warning"})

    def _muat(self) -> float:
        """Berjalan di thread pekerja. Idempoten. Mengembalikan lama pemuatan plus pemanasan (detik)."""
        if self._mesin is not None:
            return 0.0
        mulai = time.perf_counter()
        self._mesin = self._buat_mesin()
        self._baca_larik(_larik_bgr(_gambar_pemanasan()))
        return time.perf_counter() - mulai

    def _baca_larik(self, larik) -> HasilBaca:
        hasil = self._mesin(larik)
        if not hasil.txts:
            return HasilBaca("", [])
        baris = [
            BarisTeks(
                teks=str(t),
                kotak=tuple((round(float(x), 1), round(float(y), 1)) for x, y in k),
                skor=round(float(s), 4),
            )
            for t, k, s in zip(hasil.txts, hasil.boxes, hasil.scores)
        ]
        return HasilBaca("\n".join(hasil.txts), baris)

    def _baca(self, data: bytes) -> HasilBaca:
        from PIL import Image

        self._muat()
        with Image.open(io.BytesIO(data)) as gambar:
            return self._baca_larik(_larik_bgr(gambar))

    async def siapkan(self) -> float:
        """Memuat mesin dan memanaskannya. Dipanggil saat server menyala."""
        return await asyncio.get_running_loop().run_in_executor(self._pekerja, self._muat)

    async def baca(self, data: bytes) -> HasilBaca:
        return await asyncio.get_running_loop().run_in_executor(self._pekerja, self._baca, data)


# Diganti pembaca palsu oleh uji.
pembaca = Pembaca()


async def _jeda_buatan(ctx: Konteks) -> bool:
    """Menunggu sesuai rentang jeda. Mengembalikan False jika klien memutus koneksi di tengah jalan."""
    batas = time.monotonic() + random.uniform(*ctx.jeda_detik)
    while time.monotonic() < batas:
        if await ctx.klien_putus():
            return False
        await asyncio.sleep(SELANG_CEK_PUTUS_DETIK)
    return not await ctx.klien_putus()


async def baca_teks(gambar: bytes, ctx: Konteks) -> HasilBaca:
    """Masukan: bytes JPEG/PNG yang sudah divalidasi. Keluaran: teks dan data baris dari gambar.

    Melempar DibatalkanKlien jika klien putus, dan GalatApi(teks_tidak_terbaca) jika teks terlalu sedikit.
    """
    if not await _jeda_buatan(ctx):
        raise DibatalkanKlien
    if ctx.paksa == PAKSA_TEKS_TIDAK_TERBACA:
        raise GalatApi(422, "teks_tidak_terbaca", "Tidak ada teks yang bisa dibaca di gambar")

    mulai = time.perf_counter()
    hasil = await pembaca.baca(gambar)
    log.info(
        "Permintaan %s: baca %d ms, %d baris, %d karakter huruf-angka",
        ctx.id_permintaan, int((time.perf_counter() - mulai) * 1000), len(hasil.baris), hasil.karakter_bermakna,
    )
    # Klien bisa saja memutus koneksi selama membaca (atau mengantre); jangan lanjut ke langkah berikutnya.
    if await ctx.klien_putus():
        raise DibatalkanKlien
    # Nilai paksa lain (kuat, dst.) adalah mode demo: teks sungguhan dibaca, tetapi ambang dilewati.
    if ctx.paksa is None and hasil.karakter_bermakna < pengaturan.ambang_teks_karakter:
        raise GalatApi(422, "teks_tidak_terbaca", "Teks yang terbaca terlalu sedikit")
    return hasil
