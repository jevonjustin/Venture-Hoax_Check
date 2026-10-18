"""Orkestrator: satu-satunya tempat yang memanggil seluruh tahap pipeline berurutan.

Dipakai oleh endpoint /analisis dan skrip app.cek, sehingga keduanya menjalankan logika yang sama.
Log hanya mencatat ukuran, dimensi, tingkat, dan durasi tiap tahap, tanpa teks maupun isi gambar.

Urutan: baca -> bersih -> ambang teks -> regex -> LLM dan cocok (database cek fakta, berjalan bersamaan) ->
penggabungan ciri dan klaim -> tingkat -> template. PAKSA_TINGKAT (mode demo) mengganti hasilnya dengan data contoh setelah baca dan bersih.
"""

import asyncio
import logging
import time

from .. import contoh
from ..galat import DibatalkanKlien, GalatApi
from ..gambar import periksa_gambar
from ..konfigurasi import pengaturan
from ..skema import PEMERIKSAAN_AI, PEMERIKSAAN_CEK_FAKTA, ArtikelCekFakta, HasilAnalisis, Tingkat
from . import baca, bersih, ciri, cocok, klaim, llm, samarkan, tautan, template, tingkat
from .tipe import Kandidat, Konteks

# Anak logger "uvicorn.error" supaya tercetak dengan format uvicorn tanpa konfigurasi tambahan.
log = logging.getLogger("uvicorn.error").getChild("cekhoaks")


def _ms(awal: float, akhir: float) -> int:
    return int((akhir - awal) * 1000)


def _karakter_bermakna(teks: str) -> int:
    return sum(c.isalnum() for c in teks)


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
    ukuran_artikel = 0
    pemeriksaan_terbatas: list[str] = []
    penyedia_llm = "-"  # hanya nama penyedia (groq/gemini) yang boleh masuk log

    def catat(nama: str, awal: float) -> None:
        durasi_tahap[nama] = _ms(awal, time.perf_counter())

    def log_tahap() -> str:
        tahap = " ".join(f"{nama}={ms}ms" for nama, ms in durasi_tahap.items())
        return f"{tahap} teks={hasil_baca.karakter_bermakna} karakter artikel={ukuran_artikel} penyedia={penyedia_llm}"

    try:
        awal = time.perf_counter()
        hasil_baca = await baca.baca_teks(data, ctx)
        teks = hasil_baca.teks
        if ctx.diagnostik is not None:
            ctx.diagnostik["mentah"] = teks
        catat("baca", awal)

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
        # Tautan yang terpecah lintas baris digabung sekali di sini, sehingga regex, LLM, dan teks_terbaca
        # memakai teks yang sama dan setiap bukti tetap potongan persis darinya.
        teks_bersih = tautan.gabung_tautan_terpecah(teks_bersih)
        catat("bersih", awal)

        if ctx.paksa:
            # Mode demo: nilai paksa lain daripada teks_tidak_terbaca (yang sudah dilempar tahap baca).
            hasil_tingkat = Tingkat(ctx.paksa)
            asli = contoh.CONTOH[hasil_tingkat]
            klaim_utama, ciri_lengkap, artikel = asli.klaim_utama, template.susun_penjelasan(asli.ciri), asli.cek_fakta
        else:
            # Ambang dihitung dari teks bersih: potongan yang hanya berisi UI (jam, tombol) tidak dianggap teks.
            if _karakter_bermakna(teks_bersih) < pengaturan.ambang_teks_karakter:
                raise GalatApi(422, "teks_tidak_terbaca", "Teks yang terbaca terlalu sedikit")
            if await ctx.klien_putus():
                raise DibatalkanKlien

            awal = time.perf_counter()
            hasil_regex = ciri.deteksi_regex(teks_bersih)
            samar = samarkan.samarkan(teks_bersih)
            catat("regex", awal)

            jejak_llm: list | None = [] if ctx.diagnostik is not None else None

            async def jalankan_llm():
                mulai_llm = time.perf_counter()
                try:
                    return await llm.analisis(samar, jejak=jejak_llm)
                except Exception as e:  # LLM tidak boleh menggagalkan /analisis
                    log.warning("Permintaan %s: LLM gagal (%s)", ctx.id_permintaan, type(e).__name__)
                    return None
                finally:
                    catat("llm", mulai_llm)

            async def jalankan_cocok():
                mulai_cocok = time.perf_counter()
                try:
                    return await cocok.cari_kecocokan(teks_bersih)
                finally:
                    catat("cocok", mulai_cocok)

            hasil_llm, hasil_cari = await asyncio.gather(jalankan_llm(), jalankan_cocok())
            if await ctx.klien_putus():
                raise DibatalkanKlien
            kandidat = hasil_cari.kandidat
            terbatas = set()
            if not hasil_cari.lengkap:
                terbatas.add(PEMERIKSAAN_CEK_FAKTA)

            awal = time.perf_counter()
            kandidat_llm, ditolak = None, 0
            if hasil_llm is None:
                terbatas.add(PEMERIKSAAN_AI)
            else:
                penyedia_llm = hasil_llm.penyedia
                kandidat_llm, ditolak = llm.petakan_kandidat(hasil_llm.kandidat, samar, teks_bersih)
            catatan_ciri: list[dict] = []
            ciri_final = ciri.gabung_ciri(hasil_regex, kandidat_llm, teks_bersih, catatan=catatan_ciri)
            catat("ciri", awal)

            awal = time.perf_counter()
            putusan = tingkat.tentukan(ciri_final, kandidat, teks_bersih)
            hasil_tingkat = putusan.tingkat
            ciri_tampil = [c for c in ciri_final if c not in putusan.ciri_dibuang]
            catat("tingkat", awal)

            # Klaim utama, berurutan: klaim LLM (setia, tanpa kata ganti kedua) -> bukti pernah_dibantah ->
            # heuristik ekstraktif -> kosong. Heuristik lebih ketat bila LLM mengajukan klaim yang ditolak.
            awal = time.perf_counter()
            alasan_klaim = llm.alasan_klaim_ditolak(hasil_llm.klaim_utama, samar) if hasil_llm else None
            klaim_llm_sah = hasil_llm is not None and alasan_klaim is None
            klaim_llm_ditolak = hasil_llm is not None and bool(hasil_llm.klaim_utama.strip()) and not klaim_llm_sah
            catatan_klaim: dict = {}
            klaim_sumber = "kosong"
            klaim_utama = None
            if klaim_llm_sah:
                klaim_utama, klaim_sumber = hasil_llm.klaim_utama, "llm"
            else:
                dari_bukti = klaim.klaim_dari_bukti(putusan.ciri_dibantah.bukti[0]) if putusan.ciri_dibantah else ""
                if dari_bukti:
                    klaim_utama, klaim_sumber = dari_bukti, "bukti"
                else:
                    minimum = pengaturan.klaim_skor_setelah_tolak if klaim_llm_ditolak else None
                    heuristik = klaim.klaim_heuristik(
                        teks_bersih, klaim.bukti_untuk_klaim(ciri_final), skor_minimum=minimum, catatan=catatan_klaim
                    )
                    if heuristik:
                        klaim_utama, klaim_sumber = heuristik, "heuristik"
            pemeriksaan_terbatas = [x for x in (PEMERIKSAAN_CEK_FAKTA, PEMERIKSAAN_AI) if x in terbatas]
            catat("klaim", awal)

            awal = time.perf_counter()
            semua_ciri = ([putusan.ciri_dibantah] if putusan.ciri_dibantah else []) + ciri_tampil
            ciri_lengkap = template.susun_penjelasan(semua_ciri)
            artikel = [_artikel_respons(k) for k in putusan.cek_fakta]
            ukuran_artikel = len(artikel)
            catat("template", awal)
            if ctx.diagnostik is not None:
                ctx.diagnostik["llm"] = {
                    "penyedia": penyedia_llm if hasil_llm else None,
                    "durasi_ms": hasil_llm.durasi_ms if hasil_llm else None,
                    "percobaan": hasil_llm.percobaan if hasil_llm else None,
                    "klaim": hasil_llm.klaim_utama if hasil_llm else None,
                    "klaim_dipakai": klaim_sumber == "llm",
                    "kesetiaan": llm.kesetiaan_klaim(hasil_llm.klaim_utama, samar) if hasil_llm else None,
                    # Hanya kode alasan dan jumlah token; tidak ada teks (aturan privasi log).
                    "alasan_klaim_ditolak": (
                        {"kode": alasan_klaim[0], "jumlah": alasan_klaim[1]} if alasan_klaim else None
                    ),
                    "kutipan_ditolak": ditolak,
                    "kandidat": hasil_llm.kandidat if hasil_llm else None,
                    "jejak": jejak_llm,
                }
                ctx.diagnostik.update(
                    ciri_regex=hasil_regex, kandidat=kandidat, putusan=putusan, klaim_sumber=klaim_sumber,
                    klaim_gugur_percakapan=catatan_klaim.get("gugur_percakapan", 0),
                    ciri_dibuang=catatan_ciri + [
                        {"id": c.id, "bukti": "; ".join(c.bukti), "alasan": "sedang_tunggal_tanpa_indikasi"}
                        for c in putusan.ciri_dibuang
                    ],
                )
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
        teks_terbaca=teks_bersih,
        durasi_ms=durasi,
        pemeriksaan_terbatas=pemeriksaan_terbatas,
    )


def _artikel_respons(k: Kandidat) -> ArtikelCekFakta:
    return ArtikelCekFakta(
        judul=k.judul, sumber=k.sumber, url=k.url, skor_kemiripan=round(k.skor, 4), label=k.label,
        tanggal=k.tanggal, url_format_lama=k.url_format_lama,
    )
