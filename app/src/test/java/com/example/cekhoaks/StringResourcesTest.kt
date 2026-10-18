package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Memeriksa aturan teks UI (CLAUDE.md) langsung pada strings.xml: tanpa kata ganti orang kedua,
 * tanpa persen, tanpa klaim "benar"/"fakta". Semua aturan berlaku untuk SEMUA string.
 */
class StringResourcesTest {

    // Kata berakhiran "mu" yang bukan kata ganti orang kedua.
    private val bukanKataGanti = setOf(
        "temu", "bertemu", "menemu", "ditemu", "ketemu", "pertemu", "ilmu", "jamu", "tamu",
        "ramu", "meramu", "diramu", "semu",
    )

    // Pengecualian eksplisit untuk "benar" (saat ini tidak ada).
    private val pengecualianBenar = emptyMap<String, String>()

    private val polaMuMandiri = Regex("""(?i)(?<![\p{L}])mu(?![\p{L}])""")
    private val polaStripMu = Regex("""(?i)-mu\b""")
    private val polaKata = Regex("""[\p{L}\p{N}_]+""")
    private val polaPlaceholder = Regex("""%(\d+\$)?[sd]|%%""")

    private fun fileStrings(): File =
        listOf("src/main/res/values/strings.xml", "app/src/main/res/values/strings.xml")
            .map(::File).firstOrNull { it.exists() }
            ?: error("strings.xml tidak ditemukan dari ${File(".").absolutePath}")

    /** Semua <string> dan <item> (dalam string-array) beserta namanya. */
    private fun semuaTeks(): Map<String, String> {
        val dokumen = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(fileStrings())
        val hasil = linkedMapOf<String, String>()
        val strings = dokumen.getElementsByTagName("string")
        for (i in 0 until strings.length) {
            val e = strings.item(i) as Element
            hasil[e.getAttribute("name")] = e.textContent
        }
        val arrays = dokumen.getElementsByTagName("string-array")
        for (i in 0 until arrays.length) {
            val arr = arrays.item(i) as Element
            val items = arr.getElementsByTagName("item")
            for (j in 0 until items.length) {
                hasil["${arr.getAttribute("name")}[$j]"] = items.item(j).textContent
            }
        }
        return hasil
    }

    // ---------- Fungsi pemeriksa (diuji juga dengan contoh yang harus ditandai) ----------

    /** Bagian teks yang berupa kata ganti orang kedua ("kamu", "Anda", "-mu", "mu", "pesanmu"). */
    private fun kataGantiOrangKedua(teks: String): List<String> {
        val temuan = mutableListOf<String>()
        for (kata in polaKata.findAll(teks).map { it.value }) {
            val k = kata.lowercase()
            if (k == "kamu" || k == "anda") temuan += kata
            else if (k.length > 2 && k.endsWith("mu") && k !in bukanKataGanti) temuan += kata
        }
        temuan += polaMuMandiri.findAll(teks).map { it.value }
        temuan += polaStripMu.findAll(teks).map { it.value }
        return temuan
    }

    /** True bila ada tanda % yang bukan placeholder format. */
    private fun persenLiteral(teks: String): Boolean = polaPlaceholder.replace(teks, "").contains('%')

    private fun menyebutPersen(teks: String): Boolean = Regex("""(?i)\bpersen""").containsMatchIn(teks)

    private fun faktaSelainCekFakta(teks: String): Boolean =
        teks.replace(Regex("cek fakta", RegexOption.IGNORE_CASE), "").contains("fakta", ignoreCase = true)

    /** True bila ada kata "benar" yang tidak disertai "bukan jaminan". */
    private fun benarTanpaBukanJaminan(teks: String): Boolean =
        Regex("""(?i)\bbenar\b""").containsMatchIn(teks) && !teks.contains("bukan jaminan", ignoreCase = true)

    // ---------- Tes pada strings.xml ----------

    @Test
    fun fileTerbacaDanTidakKosong() {
        assertTrue(semuaTeks().size > 100)
    }

    @Test
    fun tanpaKataGantiOrangKedua() {
        val pelanggaran = semuaTeks().flatMap { (nama, teks) -> kataGantiOrangKedua(teks).map { "$nama: $it" } }
        if (pelanggaran.isNotEmpty()) fail("Kata ganti orang kedua: $pelanggaran")
    }

    @Test
    fun tanpaTandaPersenSelainPlaceholder() {
        for ((nama, isi) in semuaTeks()) {
            assertFalse("$nama mengandung %", persenLiteral(isi))
            assertFalse("$nama menyebut persen", menyebutPersen(isi))
        }
    }

    @Test
    fun tanpaFaktaSelainCekFakta() {
        for ((nama, isi) in semuaTeks()) {
            assertFalse("$nama menyebut fakta", faktaSelainCekFakta(isi))
        }
    }

    @Test
    fun kataBenarHanyaDalamKalimatBukanJaminan() {
        for ((nama, isi) in semuaTeks()) {
            if (nama in pengecualianBenar) continue
            assertFalse("$nama memakai 'benar' tanpa 'bukan jaminan'", benarTanpaBukanJaminan(isi))
        }
    }

    @Test
    fun pengecualianBenarMasihBerlaku() {
        // Pengecualian tidak boleh kedaluwarsa: string-nya harus ada dan memang memakai "benar".
        val teks = semuaTeks()
        for (nama in pengecualianBenar.keys) {
            assertTrue("$nama tidak ada lagi", nama in teks)
            assertTrue("$nama tidak memakai 'benar' lagi", benarTanpaBukanJaminan(teks.getValue(nama)))
        }
    }

    @Test
    fun keteranganTidakDitemukanMemuatBukanJaminan() {
        val teks = semuaTeks()
        for (nama in listOf(
            "hasil_keterangan_tidak_ditemukan", "hasil_keterangan_tidak_dikenal",
            "banding_pesan_tidak_ditemukan_percaya", "banding_pesan_tidak_ditemukan_ragu",
            "banding_pesan_tidak_ditemukan_tidak_percaya",
            "hasil_tips_tidak_dikenal",
        )) {
            assertTrue(nama, teks.getValue(nama).contains("bukan jaminan", ignoreCase = true))
        }
    }

    @Test
    fun labelTingkatSesuaiKetentuan() {
        val teks = semuaTeks()
        assertEquals("Indikasi Kuat Hoaks", teks["hasil_tingkat_kuat"])
        assertEquals("Perlu Hati-hati", teks["hasil_tingkat_hati_hati"])
        assertEquals("Tidak Ditemukan Indikasi Hoaks", teks["hasil_tingkat_tidak_ditemukan"])
        assertEquals("Hasil Analisis", teks["hasil_tingkat_tidak_dikenal"])
    }

    @Test
    fun kataBenarHanyaDalamFrasaPersis() {
        for ((nama, isi) in semuaTeks()) {
            val tanpaFrasa = isi.replace("bukan jaminan informasi ini benar", "", ignoreCase = true)
            assertFalse("$nama memakai 'benar' di luar frasa persis", tanpaFrasa.contains("benar", ignoreCase = true))
        }
    }

    @Test
    fun teksPerbandinganDanKeteranganTingkatMemakaiIndikasiHoaks() {
        for ((nama, isi) in semuaTeks()) {
            if (nama.startsWith("banding_pesan_") || nama.startsWith("hasil_keterangan_")) {
                assertFalse("$nama memakai kata 'ciri'", Regex("""(?i)ciri""").containsMatchIn(isi))
            }
        }
    }

    @Test
    fun duaBelasNamaBulan() {
        val bulan = semuaTeks().filterKeys { it.startsWith("bulan_nama[") }
        assertEquals(12, bulan.size)
    }

    // ---------- Tes negatif: pemeriksa harus menandai pelanggaran ----------

    @Test
    fun pemeriksaMenandaiKataGantiOrangKedua() {
        assertTrue(kataGantiOrangKedua("Cek pesan-mu").isNotEmpty())
        assertTrue(kataGantiOrangKedua("Cek pesanmu").isNotEmpty())
        assertTrue(kataGantiOrangKedua("Apakah Anda yakin").isNotEmpty())
        assertTrue(kataGantiOrangKedua("KAMU harus hati-hati").isNotEmpty())
        assertTrue(kataGantiOrangKedua("Bagi mu sendiri").isNotEmpty())
    }

    @Test
    fun pemeriksaTidakMenandaiKataBiasa() {
        assertTrue(kataGantiOrangKedua("Bertemu tamu, belajar ilmu, minum jamu").isEmpty())
        assertTrue(kataGantiOrangKedua("Perlu Hati-hati terhadap pesan itu").isEmpty())
    }

    @Test
    fun pemeriksaLainMenandaiPelanggaran() {
        assertTrue(persenLiteral("Yakin 90%"))
        assertFalse(persenLiteral("Halaman %1\$d dari %2\$d"))
        assertTrue(menyebutPersen("sembilan puluh persen"))
        assertTrue(faktaSelainCekFakta("Ini fakta"))
        assertFalse(faktaSelainCekFakta("Artikel cek fakta"))
        assertTrue(benarTanpaBukanJaminan("Informasi ini benar"))
        assertFalse(benarTanpaBukanJaminan("Bukan jaminan informasi ini benar"))
    }
}
