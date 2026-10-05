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

    @Test
    fun responsGalatTerbaca() {
        val galat = jsonApi.decodeFromString(
            ResponsGalat.serializer(),
            """{"galat": {"kode": "teks_tidak_terbaca", "pesan": "Tidak ada teks"}}""",
        )
        assertEquals(KodeGalat.TEKS_TIDAK_TERBACA, galat.galat.kode)
    }
}
