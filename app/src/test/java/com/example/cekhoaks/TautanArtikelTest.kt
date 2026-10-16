package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TautanArtikelTest {

    private val bulan = listOf(
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    )

    private fun artikel(url: String, lama: Boolean = false, judul: String = "Judul Artikel") = ArtikelCekFakta(
        judul = judul, sumber = "Sumber", url = url, skorKemiripan = 0.8, label = "salah", urlFormatLama = lama,
    )

    @Test
    fun urlPencarianMengodekanSpasi() {
        assertEquals("https://www.google.com/search?q=air+keran+bahaya", urlPencarian("air keran bahaya"))
    }

    @Test
    fun urlPencarianMengodekanKarakterKhusus() {
        assertEquals("https://www.google.com/search?q=a%26b", urlPencarian("a&b"))
        assertEquals("https://www.google.com/search?q=apa%3F", urlPencarian("apa?"))
        assertEquals("https://www.google.com/search?q=%23viral", urlPencarian("#viral"))
        assertEquals("https://www.google.com/search?q=%5BSALAH%5D+x", urlPencarian("[SALAH] x"))
        assertEquals("https://www.google.com/search?q=%22kutip%22", urlPencarian("\"kutip\""))
    }

    @Test
    fun urlPencarianMengodekanHurufNonAscii() {
        // é = C3 A9 dalam UTF-8; tanda petik melengkung = E2 80 9C / E2 80 9D
        assertEquals("https://www.google.com/search?q=caf%C3%A9", urlPencarian("café"))
        assertEquals("https://www.google.com/search?q=%E2%80%9Cx%E2%80%9D", urlPencarian("“x”"))
    }

    @Test
    fun urlPencarianMemangkasSpasiTepi() {
        assertEquals("https://www.google.com/search?q=abc", urlPencarian("  abc \n"))
    }

    @Test
    fun urlFormatLamaMemakaiPencarian() {
        val a = artikel("https://turnbackhoax.id/lama", lama = true, judul = "Judul & Lain")
        assertEquals("https://www.google.com/search?q=Judul+%26+Lain", tautanArtikel(a))
        assertFalse(tautanAsliAktif(a))
    }

    @Test
    fun urlKosongMemakaiPencarian() {
        assertEquals("https://www.google.com/search?q=Judul+Artikel", tautanArtikel(artikel("")))
        assertEquals("https://www.google.com/search?q=Judul+Artikel", tautanArtikel(artikel("   ")))
    }

    @Test
    fun urlNormalDipakaiApaAdanya() {
        val a = artikel("https://example.com/cek")
        assertEquals("https://example.com/cek", tautanArtikel(a))
        assertTrue(tautanAsliAktif(a))
    }

    @Test
    fun formatTanggalValid() {
        assertEquals("4 November 2025", formatTanggal("2025-11-04", bulan))
        assertEquals("1 Januari 2024", formatTanggal("2024-01-01", bulan))
        assertEquals("29 Februari 2024", formatTanggal("2024-02-29", bulan))
        assertEquals("31 Desember 2023", formatTanggal("2023-12-31", bulan))
    }

    @Test
    fun formatTanggalDenganWaktu() {
        assertEquals("4 November 2025", formatTanggal("2025-11-04T10:15:00Z", bulan))
    }

    @Test
    fun formatTanggalTidakValid() {
        assertNull(formatTanggal(null, bulan))
        assertNull(formatTanggal("", bulan))
        assertNull(formatTanggal("bukan tanggal", bulan))
        assertNull(formatTanggal("2025-13-01", bulan))
        assertNull(formatTanggal("2025-02-30", bulan))
        assertNull(formatTanggal("2023-02-29", bulan))
        assertNull(formatTanggal("04-11-2025", bulan))
    }

    @Test
    fun formatTanggalDenganNamaBulanTidakLengkap() {
        assertNull(formatTanggal("2025-11-04", bulan.take(11)))
    }
}
