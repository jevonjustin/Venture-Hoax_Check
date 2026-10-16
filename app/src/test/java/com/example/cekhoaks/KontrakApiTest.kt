package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class KontrakApiTest {

    // Contoh respons dari server dummy (tingkat kuat), diringkas.
    private val contohKuat = """
        {
          "id_permintaan": "1d3527b25b394e1bab098b3f9112b28f",
          "tingkat": "kuat",
          "klaim_utama": "Air keran di Jakarta mengandung zat berbahaya",
          "ciri": [
            {
              "id": "ajakan_menyebarkan",
              "nama": "Ajakan menyebarkan",
              "bukti": ["SEBARKAN ke keluarga"],
              "penjelasan": "Pesan yang mendesak untuk segera disebarkan...",
              "keyakinan": "tinggi"
            },
            {
              "id": "kapital_tanda_seru",
              "nama": "Huruf kapital dan tanda seru berlebihan",
              "bukti": ["VIRAL!!", "dihapus!!!"],
              "penjelasan": "Huruf kapital...",
              "keyakinan": "tinggi"
            }
          ],
          "cek_fakta": [
            {
              "judul": "[SALAH] Air Keran",
              "sumber": "Contoh Cek Fakta",
              "url": "https://example.com/cek-fakta/air-keran",
              "skor_kemiripan": 0.87,
              "label": "salah",
              "tanggal": "2025-11-04"
            },
            {
              "judul": "[HOAKS] Pesan Berantai",
              "sumber": "Contoh Cek Fakta",
              "url": "https://example.com/cek-fakta/pesan-berantai",
              "skor_kemiripan": 0.74,
              "label": "hoaks",
              "tanggal": null
            }
          ],
          "teks_terbaca": "VIRAL!! Air keran...",
          "durasi_ms": 1876
        }
    """.trimIndent()

    @Test
    fun hasilAnalisisTerbacaLengkap() {
        val hasil = jsonApi.decodeFromString(HasilAnalisis.serializer(), contohKuat)
        assertEquals("1d3527b25b394e1bab098b3f9112b28f", hasil.idPermintaan)
        assertEquals(Tingkat.KUAT, hasil.tingkat)
        assertEquals(2, hasil.ciri.size)
        assertEquals(listOf("VIRAL!!", "dihapus!!!"), hasil.ciri[1].bukti)
        assertEquals(0.87, hasil.cekFakta[0].skorKemiripan, 1e-9)
        assertEquals("2025-11-04", hasil.cekFakta[0].tanggal)
        assertNull(hasil.cekFakta[1].tanggal)
        assertEquals(1876L, hasil.durasiMs)
    }

    @Test
    fun tingkatLainTerbaca() {
        val hatiHati = contohKuat.replace("\"kuat\"", "\"hati_hati\"")
        val tidakDitemukan = contohKuat.replace("\"kuat\"", "\"tidak_ditemukan\"")
        assertEquals(Tingkat.HATI_HATI, jsonApi.decodeFromString(HasilAnalisis.serializer(), hatiHati).tingkat)
        assertEquals(
            Tingkat.TIDAK_DITEMUKAN,
            jsonApi.decodeFromString(HasilAnalisis.serializer(), tidakDitemukan).tingkat,
        )
    }

    @Test
    fun fieldBaruDariServerDiabaikan() {
        val denganTambahan = contohKuat.replaceFirst("{", "{\"field_masa_depan\": [1, 2],")
        assertEquals(Tingkat.KUAT, jsonApi.decodeFromString(HasilAnalisis.serializer(), denganTambahan).tingkat)
    }

    @Test
    fun klaimUtamaBolehNull() {
        val tanpaKlaim = contohKuat.replace("\"Air keran di Jakarta mengandung zat berbahaya\"", "null")
        assertNull(jsonApi.decodeFromString(HasilAnalisis.serializer(), tanpaKlaim).klaimUtama)
    }

    // Contoh kontrak 0.5 dengan field tambahan tak dikenal di level atas dan di dalam objek bersarang.
    private val contohKontrak05 = """
        {
          "id_permintaan": "abc",
          "tingkat": "hati_hati",
          "klaim_utama": null,
          "ciri": [
            {
              "id": "ciri_dari_masa_depan",
              "nama": "Ciri Baru",
              "bukti": ["bukti satu"],
              "penjelasan": "Penjelasan.",
              "keyakinan": "sedang",
              "field_ciri_baru": {"a": 1}
            }
          ],
          "cek_fakta": [
            {
              "judul": "Judul lama",
              "sumber": "TurnBackHoax",
              "url": "https://turnbackhoax.id/lama",
              "skor_kemiripan": 0.6,
              "label": "label_baru",
              "tanggal": null,
              "url_format_lama": true,
              "field_artikel_baru": [1, 2]
            }
          ],
          "teks_terbaca": "bukti satu",
          "durasi_ms": 10,
          "pemeriksaan_terbatas": ["cek_fakta", "ai"],
          "field_level_atas": "x"
        }
    """.trimIndent()

    private fun urai(json: String) = jsonApi.decodeFromString(HasilAnalisis.serializer(), json)

    @Test
    fun kontrak05DenganFieldTambahanDiTiapLevel() {
        val hasil = urai(contohKontrak05)
        assertEquals(Tingkat.HATI_HATI, hasil.tingkat)
        assertEquals("ciri_dari_masa_depan", hasil.ciri.single().id)
        assertEquals(listOf("cek_fakta", "ai"), hasil.pemeriksaanTerbatas)
        assertEquals(true, hasil.cekFakta.single().urlFormatLama)
        assertNull(hasil.cekFakta.single().tanggal)
        assertEquals("label_baru", hasil.cekFakta.single().label)
    }

    @Test
    fun cekFaktaKosong() {
        val json = contohKuat.replace(Regex("\"cek_fakta\": \\[.*?\\],\\s*\"teks_terbaca\"", RegexOption.DOT_MATCHES_ALL), "\"cek_fakta\": [], \"teks_terbaca\"")
        assertEquals(emptyList<ArtikelCekFakta>(), urai(json).cekFakta)
    }

    @Test
    fun klaimUtamaTidakAdaSamaDenganNull() {
        val tanpaField = contohKuat.replace(Regex("\"klaim_utama\": \".*?\",\\s*"), "")
        assertNull(urai(tanpaField).klaimUtama)
    }

    @Test
    fun defaultUntukFieldKontrak05YangTidakAda() {
        val hasil = urai(contohKuat)
        assertEquals(emptyList<String>(), hasil.pemeriksaanTerbatas)
        assertEquals(false, hasil.cekFakta[0].urlFormatLama)
    }

    @Test
    fun tingkatTakDikenalMenjadiCadangan() {
        val baru = contohKuat.replace("\"kuat\"", "\"sangat_kuat\"")
        assertEquals(Tingkat.TIDAK_DIKENAL, urai(baru).tingkat)
        val kosong = contohKuat.replace("\"kuat\"", "\"\"")
        assertEquals(Tingkat.TIDAK_DIKENAL, urai(kosong).tingkat)
        // Huruf besar bukan nilai kontrak, jadi juga cadangan.
        assertEquals(Tingkat.TIDAK_DIKENAL, urai(contohKuat.replace("\"kuat\"", "\"KUAT\"")).tingkat)
    }

    @Test
    fun tingkatYangDikenalTidakJatuhKeCadangan() {
        for (t in listOf(Tingkat.KUAT, Tingkat.HATI_HATI, Tingkat.TIDAK_DITEMUKAN)) {
            assertEquals(t, urai(contohKuat.replace("\"kuat\"", "\"${t.kode}\"")).tingkat)
        }
    }

    @Test
    fun tingkatDitulisKembaliSebagaiKode() {
        assertEquals("\"hati_hati\"", jsonApi.encodeToString(Tingkat.serializer(), Tingkat.HATI_HATI))
    }

    @Test
    fun fieldWajibKontrakTetapWajib() {
        val tanpaCiri = contohKuat.replace("\"ciri\"", "\"ciri_x\"")
        val galat = runCatching { urai(tanpaCiri) }.exceptionOrNull()
        assertEquals(true, galat is kotlinx.serialization.SerializationException)
    }

    @Test
    fun responsGalatTerbaca() {
        val galat = jsonApi.decodeFromString(
            ResponsGalat.serializer(),
            """{"galat": {"kode": "teks_tidak_terbaca", "pesan": "Tidak ada teks"}}""",
        )
        assertEquals(KodeGalat.TEKS_TIDAK_TERBACA, galat.galat.kode)
    }
}
