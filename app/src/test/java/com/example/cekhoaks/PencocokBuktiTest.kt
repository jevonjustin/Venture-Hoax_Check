package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PencocokBuktiTest {

    private fun teksDari(teks: String, r: IntRange) = teks.substring(r.first, r.last + 1)

    @Test
    fun cocokPersis() {
        val teks = "Halo VIRAL!! dunia"
        val hasil = cariSorotan(teks, listOf("VIRAL!!"))
        assertEquals(listOf(5..11), hasil)
        assertEquals("VIRAL!!", teksDari(teks, hasil[0]))
    }

    @Test
    fun spasiDanBarisBaruDiTeksTidakDipermasalahkan() {
        val teks = "Sebarkan\n   sebelum\tdihapus!!"
        val hasil = cariSorotan(teks, listOf("Sebarkan sebelum dihapus!!"))
        assertEquals(listOf(0..teks.length - 1), hasil)
    }

    @Test
    fun spasiDiBuktiTidakDipermasalahkan() {
        val teks = "Segera sebarkan sebelum dihapus"
        val hasil = cariSorotan(teks, listOf("sebarkan   sebelum"))
        assertEquals("sebarkan sebelum", teksDari(teks, hasil[0]))
    }

    @Test
    fun rentangMulaiDariKarakterPertamaDanBerakhirDiTerakhir() {
        val teks = "  abc \n def  "
        val hasil = cariSorotan(teks, listOf("abc def"))
        assertEquals("abc \n def", teksDari(teks, hasil.single()))
    }

    @Test
    fun tidakKetemuBukanGalat() {
        assertTrue(cariSorotan("teks biasa", listOf("tidak ada")).isEmpty())
    }

    @Test
    fun hurufBesarKecilDibedakan() {
        assertTrue(cariSorotan("viral!!", listOf("VIRAL!!")).isEmpty())
    }

    @Test
    fun kemunculanBerulangSemuanyaDitemukan() {
        val teks = "awas! lalu awas! lagi, awas!"
        val hasil = cariSorotan(teks, listOf("awas!"))
        assertEquals(listOf(0..4, 11..15, 23..27), hasil)
    }

    @Test
    fun kemunculanBertumpukanDitemukanDanDigabung() {
        // "aa" muncul di indeks 0, 1, dan 2 pada "aaaa": semuanya bertumpuk, jadi satu rentang.
        assertEquals(listOf(0..3), cariSorotan("aaaa", listOf("aa")))
    }

    @Test
    fun buktiBertumpukanDigabung() {
        val teks = "satu dua tiga empat"
        val hasil = cariSorotan(teks, listOf("satu dua", "dua tiga"))
        assertEquals(listOf(0..12), hasil)
    }

    @Test
    fun buktiBersebelahanDigabung() {
        val hasil = cariSorotan("abcdef", listOf("abc", "def"))
        assertEquals(listOf(0..5), hasil)
    }

    @Test
    fun buktiTerpisahSpasiTidakDigabung() {
        val hasil = cariSorotan("abc def", listOf("abc", "def"))
        assertEquals(listOf(0..2, 4..6), hasil)
    }

    @Test
    fun buktiDiDalamBuktiLainMenyatu() {
        val hasil = cariSorotan("sebarkan sekarang", listOf("sebarkan sekarang", "sekarang"))
        assertEquals(listOf(0..16), hasil)
    }

    @Test
    fun hasilTerurutMeskipunBuktiTidakTerurut() {
        val hasil = cariSorotan("pertama kedua ketiga", listOf("ketiga", "pertama"))
        assertEquals(listOf(0..6, 14..19), hasil)
    }

    @Test
    fun buktiKosongDanSpasiSajaDiabaikan() {
        assertTrue(cariSorotan("teks", listOf("", "   ", "\n\t")).isEmpty())
    }

    @Test
    fun buktiLebihPanjangDariTeks() {
        assertTrue(cariSorotan("ab", listOf("abcdef")).isEmpty())
    }

    @Test
    fun teksKosongDanDaftarKosong() {
        assertTrue(cariSorotan("", listOf("a")).isEmpty())
        assertTrue(cariSorotan("abc", emptyList()).isEmpty())
    }

    @Test
    fun unicodeDanHurufIndonesia() {
        val teks = "Rp 50.000 → “gratis” 😀 sekarang"
        val hasil = cariSorotan(teks, listOf("“gratis” 😀"))
        assertEquals("“gratis” 😀", teksDari(teks, hasil.single()))
    }

    @Test
    fun teksPanjangTetapCepat() {
        val teks = "kata lain yang biasa saja ".repeat(200) + "SEBARKAN sekarang juga"
        val bukti = List(30) { "kata lain yang biasa saja" } + "SEBARKAN sekarang"
        val hasil = cariSorotan(teks, bukti)
        assertTrue(hasil.isNotEmpty())
        assertEquals("SEBARKAN sekarang", teksDari(teks, hasil.last()))
    }
}
