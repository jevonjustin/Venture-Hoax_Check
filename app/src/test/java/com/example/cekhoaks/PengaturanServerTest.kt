package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PengaturanServerTest {

    private fun normal(masukan: String) = PengaturanServer.normalisasiUrl(masukan)

    @Test
    fun alamatBakuTidakBerubah() {
        assertEquals("http://192.168.1.5:8000", normal("http://192.168.1.5:8000"))
        assertEquals(PengaturanServer.URL_USB, normal(PengaturanServer.URL_USB))
    }

    @Test
    fun spasiDanGarisMiringAkhirDibuang() {
        assertEquals("http://192.168.1.5:8000", normal("  http://192.168.1.5:8000/  "))
    }

    @Test
    fun tanpaSkemaDianggapHttp() {
        assertEquals("http://192.168.1.5:8000", normal("192.168.1.5:8000"))
    }

    @Test
    fun httpsDanNamaHostDiterima() {
        assertEquals("https://contoh.trycloudflare.com", normal("https://contoh.trycloudflare.com"))
        assertEquals("http://laptop.local:8000", normal("HTTP://Laptop.Local:8000"))
    }

    @Test
    fun jalurQueryDanLoginDitolak() {
        assertNull(normal("http://192.168.1.5:8000/analisis"))
        assertNull(normal("http://192.168.1.5:8000/?paksa=kuat"))
        assertNull(normal("http://192.168.1.5:8000/#bagian"))
        assertNull(normal("http://user:rahasia@192.168.1.5:8000"))
    }

    @Test
    fun formatSalahDitolak() {
        assertNull(normal(""))
        assertNull(normal("   "))
        assertNull(normal("http://"))
        assertNull(normal("ftp://192.168.1.5"))
        assertNull(normal("http://192.168.1.5:99999"))
        assertNull(normal("http://192.168 .1.5:8000"))
    }
}
