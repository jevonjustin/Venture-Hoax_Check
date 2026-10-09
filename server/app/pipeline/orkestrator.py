"""Orkestrator: satu-satunya tempat yang memanggil seluruh tahap pipeline berurutan.

Dipakai oleh endpoint /analisis dan skrip app.cek, sehingga keduanya menjalankan logika yang sama.
Log hanya mencatat ukuran, dimensi, tingkat, dan durasi tiap tahap, tanpa teks maupun isi gambar.
"""

import logging
import time

from .. import contoh
from ..galat import DibatalkanKlien, GalatApi
from ..gambar import periksa_gambar
from ..konfigurasi import pengaturan
from ..skema import HasilAnalisis, Tingkat
from . import baca, bersih, ciri, cocok, klaim, template, tingkat
from .tipe import Konteks

# Anak logger "uvicorn.error" supaya tercetak dengan format uvicorn tanpa konfigurasi tambahan.
log = logging.getLogger("uvicorn.error").getChild("cekhoaks")


def _ms(awal: float, akhir: float) -> int:
    return int((akhir - awal) * 1000)


async def jalankan(data: bytes, ctx: Konteks) -> HasilAnalisis:
    """Memvalidasi gambar lalu menjalankan semua tahap.

    Melempar GalatApi (gambar tidak sah, teks tidak terbaca) atau DibatalkanKlien.
    """
    try:
        info = periksa_gambar(data, pengaturan.batas_gambar_byte)
    except GalatApi as e:
        log.info("Permintaan %s ditolak: %s", ctx.id_permintaan, e.kode)
        raise
    ringkasan = info.ringkasan()
    durasi_tahap: dict[str, int] = {}

    def catat(nama: str, awal: float) -> None:
        durasi_tahap[nama] = _ms(awal, time.perf_counter())

    def log_tahap() -> str:
        tahap = " ".join(f"{nama}={ms}ms" for nama, ms in durasi_tahap.items())
        return f"{tahap} teks={hasil_baca.karakter_bermakna} karakter"

    try:
        awal = time.perf_counter()
        hasil_baca = await baca.baca_teks(data, ctx)
        teks = hasil_baca.teks
        if ctx.diagnostik is not None:
            ctx.diagnostik["mentah"] = teks
        catat("baca", awal)
        # Khusus dummy (hilang di Sesi 5.5): dipilih setelah baca berhasil supaya giliran
        # tidak maju untuk permintaan yang batal atau teksnya tidak terbaca.
        ctx.skenario = Tingkat(ctx.paksa) if ctx.paksa else contoh.tingkat_berikutnya()

        awal = time.perf_counter()
        try:
            hasil_bersih = bersih.bersihkan(hasil_baca.baris, info.lebar, info.tinggi)
            teks_bersih = hasil_bersih.teks
            if ctx.diagnostik is not None:
                ctx.diagnostik["bersih"] = hasil_bersih
        except Exception as e:  # bersih tidak boleh menggagalkan /analisis; pakai teks mentah
            teks_bersih = teks
            log.warning(
                "Permintaan %s: pembersihan teks gagal (%s), memakai teks mentah", ctx.id_permintaan, type(e).__name__
            )
        catat("bersih", awal)

        awal = time.perf_counter()
        klaim_utama = klaim.ekstrak_klaim(teks_bersih, ctx)
        catat("klaim", awal)

        awal = time.perf_counter()
        artikel = cocok.cari_kecocokan(klaim_utama, ctx)
        catat("cocok", awal)

        awal = time.perf_counter()
        terdeteksi = ciri.deteksi_ciri(teks_bersih, artikel, ctx)
        catat("ciri", awal)

        awal = time.perf_counter()
        hasil_tingkat = tingkat.tentukan_tingkat(terdeteksi, artikel, ctx)
        catat("tingkat", awal)

        awal = time.perf_counter()
        ciri_lengkap = template.susun_penjelasan(terdeteksi)
        catat("template", awal)
    except DibatalkanKlien:
        log.info("Permintaan %s dibatalkan klien setelah %d ms", ctx.id_permintaan, _ms(ctx.mulai, time.perf_counter()))
        raise
    except GalatApi as e:
        log.info(
            "Permintaan %s: %s, %s, %d ms", ctx.id_permintaan, ringkasan, e.kode.replace("_", " "),
            _ms(ctx.mulai, time.perf_counter()),
        )
        raise

    durasi = _ms(ctx.mulai, time.perf_counter())
    log.info("Permintaan %s: %s, tingkat %s, %d ms", ctx.id_permintaan, ringkasan, hasil_tingkat.value, durasi)
    log.info("Permintaan %s tahap: %s", ctx.id_permintaan, log_tahap())
    return HasilAnalisis(
        id_permintaan=ctx.id_permintaan,
        tingkat=hasil_tingkat,
        klaim_utama=klaim_utama,
        ciri=ciri_lengkap,
        cek_fakta=artikel,
        teks_terbaca=teks,
        durasi_ms=durasi,
    )
