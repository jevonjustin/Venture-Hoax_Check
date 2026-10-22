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

    @Test
    fun contohTahap7() {
        assertEquals("http://192.168.1.5:8000", normal("192.168.1.5"))
        assertEquals("http://10.0.0.2:8000", normal("http://10.0.0.2"))
        assertEquals("http://192.168.1.5:9000", normal("http://192.168.1.5:9000"))
        assertEquals("http://localhost:8000", normal("localhost"))
        assertEquals("https://veritas.hf.space", normal("veritas.hf.space"))
        assertEquals("https://veritas.hf.space", normal("https://veritas.hf.space/"))
        assertEquals("http://contoh.com", normal("http://contoh.com"))
    }

    @Test
    fun usbTanpaSkemaDanPortMenjadiAlamatUsb() {
        assertEquals(PengaturanServer.URL_USB, normal("127.0.0.1"))
        assertEquals(PengaturanServer.URL_USB, normal("http://127.0.0.1"))
    }

    @Test
    fun rentangIpPrivat172() {
        assertEquals("http://172.16.0.1:8000", normal("172.16.0.1"))
        assertEquals("http://172.31.255.1:8000", normal("172.31.255.1"))
        assertEquals("https://172.32.0.1", normal("172.32.0.1"))
        assertEquals("https://172.15.0.1", normal("172.15.0.1"))
    }

    @Test
    fun domainPublikDanHttpsTidakDiberiPort() {
        assertEquals("https://8.8.8.8", normal("8.8.8.8"))
        assertEquals("https://192.168.1.5", normal("https://192.168.1.5"))
        assertEquals("https://veritas.hf.space", normal("  veritas.hf.space//  "))
    }

    @Test
    fun portYangDitulisDibiarkan() {
        assertEquals("http://192.168.1.5:80", normal("http://192.168.1.5:80"))
        assertEquals("http://localhost:9000", normal("localhost:9000"))
        assertEquals("https://veritas.hf.space:443", normal("https://veritas.hf.space:443"))
        assertEquals("https://contoh.com:8443", normal("contoh.com:8443"))
    }

    @Test
    fun hasilNormalisasiStabil() {
        listOf("192.168.1.5", "localhost", "veritas.hf.space", "http://192.168.1.5:80", "http://contoh.com")
            .forEach { val sekali = normal(it)!!; assertEquals(sekali, normal(sekali)) }
    }
}
