package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TampilanGalatTest {

    private fun server(kode: String?) = tampilanGalat(JenisGagal.GalatServer(500, kode))

    @Test
    fun teksTidakTerbaca() {
        val t = server(KodeGalat.TEKS_TIDAK_TERBACA)
        assertEquals(R.string.galat_judul_teks, t.judul)
        assertEquals(R.string.galat_isi_teks, t.isi)
        assertEquals(AksiGalat.PILIH_ULANG, t.aksiUtama)
        assertFalse(t.tampilkanPengaturanKedua)
    }

    @Test
    fun terlaluBesar() {
        val t = server(KodeGalat.TERLALU_BESAR)
        assertEquals(R.string.galat_judul_besar, t.judul)
        assertEquals(AksiGalat.PILIH_ULANG, t.aksiUtama)
    }

    @Test
    fun gambarKosongBukanGambarDanPenyandianSama() {
        val k = server(KodeGalat.GAMBAR_KOSONG)
        assertEquals(R.string.galat_judul_gambar, k.judul)
        assertEquals(AksiGalat.PILIH_ULANG, k.aksiUtama)
        assertEquals(k, server(KodeGalat.BUKAN_GAMBAR))
        assertEquals(k, tampilanGalatPenyandian())
    }

    @Test
    fun tidakTerjangkauAdaTombolPengaturanKedua() {
        val t = tampilanGalat(JenisGagal.TidakTerjangkau("x"))
        assertEquals(R.string.galat_judul_tidak_terjangkau, t.judul)
        assertEquals(AksiGalat.COBA_LAGI, t.aksiUtama)
        assertTrue(t.tampilkanPengaturanKedua)
    }

    @Test
    fun urlBelumDiatur() {
        val t = tampilanGalat(JenisGagal.UrlBelumDiatur)
        assertEquals(R.string.galat_judul_url, t.judul)
        assertEquals(AksiGalat.BUKA_PENGATURAN, t.aksiUtama)
        assertFalse(t.tampilkanPengaturanKedua)
    }

    @Test
    fun waktuHabis() {
        val t = tampilanGalat(JenisGagal.WaktuHabis)
        assertEquals(R.string.galat_judul_waktu_habis, t.judul)
        assertEquals(AksiGalat.COBA_LAGI, t.aksiUtama)
    }

    @Test
    fun responsTidakDikenaliDanCleartext() {
        val r = tampilanGalat(JenisGagal.ResponsTidakDikenali)
        val c = tampilanGalat(JenisGagal.CleartextDiblokir)
        assertEquals(R.string.galat_judul_respons, r.judul)
        assertEquals(R.string.galat_judul_cleartext, c.judul)
        assertEquals(R.string.galat_isi_respons, r.isi)
        assertEquals(R.string.galat_isi_cleartext, c.isi)
        assertEquals(AksiGalat.BUKA_PENGATURAN, r.aksiUtama)
        assertEquals(AksiGalat.BUKA_PENGATURAN, c.aksiUtama)
    }

    @Test
    fun galatServerUmumKodeTakDikenalDanNull() {
        val umum = tampilanGalat(JenisGagal.GalatServer(500, KodeGalat.GALAT_SERVER))
        assertEquals(R.string.galat_judul_server, umum.judul)
        assertEquals(AksiGalat.COBA_LAGI, umum.aksiUtama)
        assertFalse(umum.tampilkanPengaturanKedua)
        assertEquals(umum, tampilanGalat(JenisGagal.GalatServer(502, KodeGalat.GALAT_HTTP)))
        assertEquals(umum, server("kode_baru_dari_masa_depan"))
        assertEquals(umum, server(null))
    }
}
