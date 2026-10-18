package com.example.cekhoaks

import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Memeriksa berkas fixture debug (app/src/debug/assets/fixture) tetap sesuai kontrak 0.5,
 * sehingga tampilan bisa diuji di HP tanpa server.
 */
class FixtureTest {

    private val idCiriTerkunci = setOf(
        "permintaan_data_rahasia", "ajakan_menyebarkan", "desakan_waktu", "kapital_tanda_seru",
        "link_mencurigakan", "sumber_tidak_jelas", "judul_clickbait", "bahasa_provokatif", "pernah_dibantah",
    )

    private fun folderFixture(): File =
        listOf("src/debug/assets/fixture", "app/src/debug/assets/fixture")
            .map(::File).firstOrNull { it.isDirectory }
            ?: error("folder fixture tidak ditemukan dari ${File(".").absolutePath}")

    private fun semuaBerkas(): List<File> =
        folderFixture().listFiles { f -> f.extension == "json" }!!.sortedBy { it.name }

    private fun isi(f: File) = f.readText(Charsets.UTF_8)

    private fun fixtureSukses(): List<File> = semuaBerkas().filter { !it.name.startsWith("galat_") }
    private fun fixtureGalat(): List<File> = semuaBerkas().filter { it.name.startsWith("galat_") }

    @Test
    fun fixtureWajibAda() {
        val nama = semuaBerkas().map { it.nameWithoutExtension }.toSet()
        val wajib = setOf(
            "kuat", "hati_hati", "hati_hati_mirip", "hati_hati_satir", "hati_hati_artikel", "hati_hati_umum", "tidak_ditemukan", "tidak_ditemukan_rujukan",
            "klaim_kosong", "cek_fakta_kosong", "url_format_lama", "pemeriksaan_terbatas",
            "pemeriksaan_terbatas_ai", "panjang", "tak_dikenal", "galat_teks_tidak_terbaca",
            "galat_terlalu_besar", "galat_server", "galat_kode_tak_dikenal", "galat_tidak_terjangkau",
            "galat_waktu_habis", "galat_url_belum_diatur", "galat_respons_tidak_dikenali", "galat_cleartext",
        )
        assertTrue("fixture hilang: ${wajib - nama}", nama.containsAll(wajib))
    }

    @Test
    fun fixtureSuksesBisaDidekode() {
        fixtureSukses().forEach { f ->
            val hasil = jsonApi.decodeFromString(HasilAnalisis.serializer(), isi(f))
            assertTrue("${f.name}: id kosong", hasil.idPermintaan.isNotEmpty())
        }
    }

    @Test
    fun fixtureGalatBisaDidekode() {
        fixtureGalat().forEach { f ->
            val obj = jsonApi.parseToJsonElement(isi(f)).jsonObject
            if (obj.containsKey("_jenis")) {
                // Pseudo-fixture galat sisi klien.
                val jenis = obj["_jenis"]!!.jsonPrimitive.content
                assertEquals("${f.name}: nama berkas harus sesuai _jenis", "galat_$jenis", f.nameWithoutExtension)
            } else {
                val galat = jsonApi.decodeFromString(ResponsGalat.serializer(), isi(f))
                assertTrue("${f.name}: kode kosong", galat.galat.kode.isNotEmpty())
                assertTrue("${f.name}: _status_http hilang", obj.containsKey("_status_http"))
            }
        }
    }

    @Test
    fun takDikenalMenghasilkanTingkatCadangan() {
        val hasil = jsonApi.decodeFromString(HasilAnalisis.serializer(), isi(File(folderFixture(), "tak_dikenal.json")))
        assertEquals(Tingkat.TIDAK_DIKENAL, hasil.tingkat)
        assertEquals(null, hasil.cekFakta.single().tanggal)
    }

    @Test
    fun setiapBuktiDitemukanPencocok() {
        // Semua fixture sukses, termasuk tak_dikenal, dirancang agar tiap bukti ketemu di teks_terbaca
        // (spasi/baris baru diabaikan). Tidak ada bukti yang sengaja tidak cocok.
        fixtureSukses().forEach { f ->
            val hasil = jsonApi.decodeFromString(HasilAnalisis.serializer(), isi(f))
            hasil.ciri.forEach { c ->
                c.bukti.forEach { b ->
                    assertTrue(
                        "${f.name}: bukti tidak ditemukan di teks_terbaca: \"$b\"",
                        cariSorotan(hasil.teksTerbaca, listOf(b)).isNotEmpty(),
                    )
                }
            }
        }
    }

    @Test
    fun kesembilanIdCiriTerpakai() {
        val dipakai = fixtureSukses().flatMap {
            jsonApi.decodeFromString(HasilAnalisis.serializer(), isi(it)).ciri.map { c -> c.id }
        }.toSet()
        assertTrue("id ciri belum terpakai: ${idCiriTerkunci - dipakai}", dipakai.containsAll(idCiriTerkunci))
    }

    @Test
    fun fixturePanjangBenarBenarPanjang() {
        val hasil = jsonApi.decodeFromString(HasilAnalisis.serializer(), isi(File(folderFixture(), "panjang.json")))
        assertTrue(hasil.teksTerbaca.length >= 3500)
        assertEquals(9, hasil.ciri.size)
        assertEquals(3, hasil.cekFakta.size)
    }

    @Test
    fun fixtureHatiHatiMencakupSemuaPenyebab() {
        fun penyebab(nama: String) = penyebabHatiHati(
            jsonApi.decodeFromString(HasilAnalisis.serializer(), isi(File(folderFixture(), "$nama.json"))),
        )
        assertEquals(PenyebabHatiHati.CIRI, penyebab("hati_hati"))
        assertEquals(PenyebabHatiHati.CIRI, penyebab("hati_hati_mirip"))
        assertEquals(PenyebabHatiHati.ARTIKEL_SATIR, penyebab("hati_hati_satir"))
        assertEquals(PenyebabHatiHati.ARTIKEL_LAIN, penyebab("hati_hati_artikel"))
        assertEquals(PenyebabHatiHati.UMUM, penyebab("hati_hati_umum"))
    }

    @Test
    fun fixtureTidakAdaDiSrcMain() {
        val main = listOf("src/main", "app/src/main").map(::File).first { it.isDirectory }
        val ditemukan = main.walkTopDown().filter { it.isFile && it.path.replace('\\', '/').contains("fixture") }.toList()
        assertFalse("fixture tidak boleh ada di src/main: $ditemukan", ditemukan.isNotEmpty())
    }
}
