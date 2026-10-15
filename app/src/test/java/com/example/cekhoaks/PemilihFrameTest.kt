package com.example.cekhoaks

import com.example.cekhoaks.PemilihFrame.Keputusan
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class PemilihFrameTest {

    private class FramePalsu(val nama: String) : AutoCloseable {
        var ditutup = false
        override fun close() {
            ditutup = true
        }
    }

    private var waktu = 1_000L
    private val pemilih = PemilihFrame<FramePalsu>(jam = { waktu })

    private fun majuKe(msSetelahMulai: Long) {
        waktu = 1_000L + msSetelahMulai
    }

    private fun pakai(keputusan: Keputusan<FramePalsu>?): Keputusan.Pakai<FramePalsu> {
        assertTrue("diharapkan Pakai, diterima $keputusan", keputusan is Keputusan.Pakai)
        return keputusan as Keputusan.Pakai<FramePalsu>
    }

    // --- idle ---

    @Test
    fun idle_frameMasukLangsungDitutup() {
        val f = FramePalsu("idle")
        assertNull(pemilih.frameMasuk(f))
        assertTrue(f.ditutup)
        assertFalse(pemilih.sedangMenunggu)
    }

    @Test
    fun idle_periksaTidakMenunggu() {
        assertEquals(Keputusan.TidakMenunggu, pemilih.periksa())
    }

    @Test
    fun mulai_memintaPeriksaSetelahJedaMinimum() {
        assertEquals(Keputusan.PeriksaLagi(PemilihFrame.JEDA_MIN_MS), pemilih.mulai())
        assertTrue(pemilih.sedangMenunggu)
    }

    // --- frame sebelum dan sesudah jeda minimum ---

    @Test
    fun frameSebelumJeda_dipakaiSaatJedaSelesai() {
        pemilih.mulai()
        majuKe(40)
        val f = FramePalsu("a")
        assertNull(pemilih.frameMasuk(f))
        majuKe(150)
        val hasil = pakai(pemilih.periksa())
        assertSame(f, hasil.frame)
        assertFalse("frame dipakai ditutup oleh pemanggil, bukan oleh pemilih", f.ditutup)
        assertEquals(40L, hasil.info.tibaMs)
        assertEquals(150L, hasil.info.selesaiMs)
        assertEquals(1, hasil.info.jumlahFrame)
        assertFalse(hasil.info.cadanganDipakai)
        assertFalse(pemilih.sedangMenunggu)
    }

    @Test
    fun beberapaFrameSebelumJeda_yangDipakaiTerbaruDanYangLamaDitutup() {
        // Frame transisi saat tombol menghilang tidak boleh terpakai.
        pemilih.mulai()
        majuKe(10)
        val transisi = FramePalsu("transisi")
        pemilih.frameMasuk(transisi)
        majuKe(30)
        val akhir = FramePalsu("akhir")
        pemilih.frameMasuk(akhir)
        assertTrue(transisi.ditutup)
        majuKe(150)
        val hasil = pakai(pemilih.periksa())
        assertSame(akhir, hasil.frame)
        assertEquals(2, hasil.info.jumlahFrame)
    }

    @Test
    fun periksaSebelumJeda_memintaPeriksaLagiSisaJeda() {
        pemilih.mulai()
        majuKe(100)
        pemilih.frameMasuk(FramePalsu("a"))
        assertEquals(Keputusan.PeriksaLagi(50), pemilih.periksa())
        assertTrue(pemilih.sedangMenunggu)
    }

    @Test
    fun frameSetelahJeda_langsungDipakai() {
        pemilih.mulai()
        majuKe(150)
        assertEquals(Keputusan.PeriksaLagi(850), pemilih.periksa())
        majuKe(400)
        val f = FramePalsu("lambat")
        val hasil = pakai(pemilih.frameMasuk(f))
        assertSame(f, hasil.frame)
        assertEquals(400L, hasil.info.tibaMs)
        assertEquals("timer yang masih tertunda tidak berbuat apa-apa", Keputusan.TidakMenunggu, pemilih.periksa())
    }

    @Test
    fun setelahSelesai_frameBerikutnyaDitutupLagi() {
        pemilih.mulai()
        majuKe(150)
        pakai(pemilih.frameMasuk(FramePalsu("a")))
        val sesudah = FramePalsu("sesudah")
        assertNull(pemilih.frameMasuk(sesudah))
        assertTrue(sesudah.ditutup)
    }

    // --- pendengar dipanggil dengan null ---

    @Test
    fun nullSetelahFrameBagus_frameBagusTetapDipertahankan() {
        pemilih.mulai()
        majuKe(20)
        val bagus = FramePalsu("bagus")
        pemilih.frameMasuk(bagus)
        majuKe(25)
        assertNull(pemilih.frameMasuk(null))
        assertFalse(bagus.ditutup)
        majuKe(150)
        assertSame(bagus, pakai(pemilih.periksa()).frame)
    }

    @Test
    fun nullSetelahJeda_tidakMengakhiriPermintaan() {
        pemilih.mulai()
        majuKe(200)
        assertNull(pemilih.frameMasuk(null))
        assertTrue(pemilih.sedangMenunggu)
    }

    // --- tidak ada frame sampai batas waktu ---

    @Test
    fun tanpaFrame_paksaFrameBaruLaluGagal() {
        pemilih.mulai()
        majuKe(150)
        assertEquals(Keputusan.PeriksaLagi(850), pemilih.periksa())
        majuKe(1_000)
        assertEquals(Keputusan.PaksaFrameBaru(PemilihFrame.BATAS_CADANGAN_MS), pemilih.periksa())
        majuKe(1_300)
        val hasil = pemilih.periksa()
        assertTrue(hasil is Keputusan.Gagal)
        val info = (hasil as Keputusan.Gagal).info
        assertNull(info.tibaMs)
        assertEquals(1_300L, info.selesaiMs)
        assertEquals(0, info.jumlahFrame)
        assertTrue(info.cadanganDipakai)
        assertFalse(pemilih.sedangMenunggu)
    }

    @Test
    fun cadanganBerhasil_frameSetelahPaksaDipakai() {
        pemilih.mulai()
        majuKe(1_000)
        assertTrue(pemilih.periksa() is Keputusan.PaksaFrameBaru)
        majuKe(1_040)
        val hasil = pakai(pemilih.frameMasuk(FramePalsu("paksa")))
        assertTrue(hasil.info.cadanganDipakai)
        assertEquals(1_040L, hasil.info.tibaMs)
    }

    @Test
    fun timerTerlambat_periksaMemintaSisaBatasTunggu() {
        pemilih.mulai()
        majuKe(600)
        assertEquals(Keputusan.PeriksaLagi(400), pemilih.periksa())
    }

    // --- pembatalan (hentikan atau putar layar) ---

    @Test
    fun batalkan_menutupFrameTersimpanDanKembaliIdle() {
        pemilih.mulai()
        majuKe(50)
        val f = FramePalsu("a")
        pemilih.frameMasuk(f)
        assertTrue(pemilih.batalkan())
        assertTrue(f.ditutup)
        assertFalse(pemilih.sedangMenunggu)
        majuKe(150)
        assertEquals(Keputusan.TidakMenunggu, pemilih.periksa())
    }

    @Test
    fun batalkan_tanpaFrame() {
        pemilih.mulai()
        assertTrue(pemilih.batalkan())
        val sesudah = FramePalsu("sesudah")
        pemilih.frameMasuk(sesudah)
        assertTrue(sesudah.ditutup)
    }

    @Test
    fun batalkan_saatIdleMengembalikanFalse() {
        assertFalse(pemilih.batalkan())
    }

    @Test
    fun mulaiUlang_frameSisaDitutupDanWaktuDihitungUlang() {
        pemilih.mulai()
        majuKe(50)
        val sisa = FramePalsu("sisa")
        pemilih.frameMasuk(sisa)
        majuKe(80)
        pemilih.mulai()
        assertTrue(sisa.ditutup)
        majuKe(200)
        assertEquals(Keputusan.PeriksaLagi(30), pemilih.periksa())
    }
}
