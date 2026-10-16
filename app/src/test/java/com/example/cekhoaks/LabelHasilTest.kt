package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LabelHasilTest {

    @Test
    fun sembilanIdCiriMemakaiResourceSendiri() {
        val diharapkan = mapOf(
            "permintaan_data_rahasia" to R.string.ciri_nama_permintaan_data_rahasia,
            "ajakan_menyebarkan" to R.string.ciri_nama_ajakan_menyebarkan,
            "desakan_waktu" to R.string.ciri_nama_desakan_waktu,
            "kapital_tanda_seru" to R.string.ciri_nama_kapital_tanda_seru,
            "link_mencurigakan" to R.string.ciri_nama_link_mencurigakan,
            "sumber_tidak_jelas" to R.string.ciri_nama_sumber_tidak_jelas,
            "judul_clickbait" to R.string.ciri_nama_judul_clickbait,
            "bahasa_provokatif" to R.string.ciri_nama_bahasa_provokatif,
            "pernah_dibantah" to R.string.ciri_nama_pernah_dibantah,
        )
        assertEquals(9, diharapkan.size)
        for ((id, res) in diharapkan) {
            // Nama dari server diabaikan untuk id yang dikenal.
            assertEquals(id, NamaCiri.DariResource(res), namaCiri(id, "nama dari server"))
        }
        assertEquals(9, diharapkan.values.toSet().size)
    }

    @Test
    fun idTakDikenalMemakaiNamaServer() {
        assertEquals(NamaCiri.DariServer("Ciri Baru"), namaCiri("ciri_baru", "Ciri Baru"))
        assertEquals(NamaCiri.DariServer("Ciri Baru"), namaCiri("ciri_baru", "  Ciri Baru "))
    }

    @Test
    fun namaServerKosongMenjadiCiriLain() {
        assertEquals(NamaCiri.DariResource(R.string.ciri_nama_lain), namaCiri("ciri_baru", ""))
        assertEquals(NamaCiri.DariResource(R.string.ciri_nama_lain), namaCiri("ciri_baru", "   "))
    }

    @Test
    fun teksNamaCiri() {
        val ambil = { res: Int -> "res$res" }
        assertEquals("res${R.string.ciri_nama_lain}", NamaCiri.DariResource(R.string.ciri_nama_lain).teks(ambil))
        assertEquals("X", NamaCiri.DariServer("X").teks(ambil))
    }

    @Test
    fun keyakinan() {
        assertEquals(R.string.hasil_keyakinan_tinggi, teksKeyakinan("tinggi"))
        assertEquals(R.string.hasil_keyakinan_sedang, teksKeyakinan("sedang"))
        assertNull(teksKeyakinan("rendah"))
        assertNull(teksKeyakinan(""))
        assertNull(teksKeyakinan("sangat tinggi"))
    }

    @Test
    fun labelArtikelMerah() {
        val salah = labelArtikel("salah")
        assertEquals(R.string.hasil_label_salah, salah.teks)
        assertEquals(GayaLabel.MERAH, salah.gaya)
        val penipuan = labelArtikel("penipuan")
        assertEquals(R.string.hasil_label_penipuan, penipuan.teks)
        assertEquals(GayaLabel.MERAH, penipuan.gaya)
    }

    @Test
    fun labelArtikelNetral() {
        assertEquals(R.string.hasil_label_klarifikasi, labelArtikel("klarifikasi").teks)
        assertEquals(R.string.hasil_label_satir, labelArtikel("satir").teks)
        assertEquals(R.string.hasil_label_belum_terbukti, labelArtikel("belum_terbukti").teks)
        for (l in listOf("klarifikasi", "satir", "belum_terbukti")) {
            assertEquals(GayaLabel.NETRAL, labelArtikel(l).gaya)
        }
    }

    @Test
    fun benarLainnyaDanTakDikenalMenjadiRujukan() {
        for (l in listOf("benar", "lainnya", "label_baru", "")) {
            val hasil = labelArtikel(l)
            assertEquals(l, R.string.hasil_label_rujukan, hasil.teks)
            assertEquals(l, GayaLabel.NETRAL, hasil.gaya)
        }
    }

    @Test
    fun tampilanTiapTingkatBerbeda() {
        val kuat = tampilanTingkat(Tingkat.KUAT)
        val hati = tampilanTingkat(Tingkat.HATI_HATI)
        val tidak = tampilanTingkat(Tingkat.TIDAK_DITEMUKAN)
        assertEquals(R.string.hasil_tingkat_kuat, kuat.judul)
        assertEquals(R.string.hasil_tingkat_hati_hati, hati.judul)
        assertEquals(R.string.hasil_tingkat_tidak_ditemukan, tidak.judul)
        assertEquals(IkonTingkat.SEGITIGA_SERU, kuat.ikon)
        assertEquals(IkonTingkat.LINGKARAN_SERU, hati.ikon)
        assertEquals(IkonTingkat.LINGKARAN_INFO, tidak.ikon)
        assertNotEquals(kuat.palet, hati.palet)
        assertNotEquals(hati.palet, tidak.palet)
        assertEquals(R.string.hasil_keterangan_kuat, kuat.keterangan)
        assertEquals(R.string.hasil_tips_hati_hati, hati.tips)
    }

    @Test
    fun tingkatTidakDikenalNetral() {
        val t = tampilanTingkat(Tingkat.TIDAK_DIKENAL)
        assertEquals(R.string.hasil_tingkat_tidak_dikenal, t.judul)
        assertEquals(R.string.hasil_keterangan_tidak_dikenal, t.keterangan)
        assertEquals(R.string.hasil_tips_tidak_dikenal, t.tips)
        assertEquals(tampilanTingkat(Tingkat.TIDAK_DITEMUKAN).palet, t.palet)
        assertEquals(IkonTingkat.LINGKARAN_INFO, t.ikon)
    }

    @Test
    fun pemeriksaanTerbatas() {
        assertEquals(listOf(R.string.hasil_terbatas_cek_fakta), kalimatPemeriksaanTerbatas(listOf("cek_fakta")))
        assertEquals(listOf(R.string.hasil_terbatas_ai), kalimatPemeriksaanTerbatas(listOf("ai")))
        assertEquals(
            listOf(R.string.hasil_terbatas_cek_fakta, R.string.hasil_terbatas_ai),
            kalimatPemeriksaanTerbatas(listOf("cek_fakta", "ai")),
        )
        assertEquals(listOf(R.string.hasil_terbatas_lain), kalimatPemeriksaanTerbatas(listOf("sesuatu_baru")))
        assertTrue(kalimatPemeriksaanTerbatas(emptyList()).isEmpty())
    }

    @Test
    fun pemeriksaanTerbatasTanpaDuplikat() {
        assertEquals(
            listOf(R.string.hasil_terbatas_ai, R.string.hasil_terbatas_lain),
            kalimatPemeriksaanTerbatas(listOf("ai", "ai", "x", "y")),
        )
    }

    @Test
    fun artiPemeriksaanTerbatasLebihTegasUntukTidakDitemukan() {
        assertEquals(
            R.string.hasil_terbatas_arti_tidak_ditemukan,
            artiPemeriksaanTerbatas(Tingkat.TIDAK_DITEMUKAN),
        )
        for (t in listOf(Tingkat.KUAT, Tingkat.HATI_HATI, Tingkat.TIDAK_DIKENAL)) {
            assertEquals(R.string.hasil_terbatas_arti, artiPemeriksaanTerbatas(t))
        }
    }

    @Test
    fun cekFaktaTerbatas() {
        assertTrue(cekFaktaTerbatas(listOf("ai", "cek_fakta")))
        assertFalse(cekFaktaTerbatas(listOf("ai")))
        assertFalse(cekFaktaTerbatas(emptyList()))
    }

    @Test
    fun nilaiDinormalkanDenganTrimDanHurufKecil() {
        assertEquals(R.string.hasil_keyakinan_tinggi, teksKeyakinan(" Tinggi "))
        assertEquals(R.string.hasil_keyakinan_sedang, teksKeyakinan("SEDANG"))
        assertEquals(R.string.hasil_label_salah, labelArtikel(" SALAH ").teks)
        assertEquals(GayaLabel.MERAH, labelArtikel("Penipuan ").gaya)
        assertEquals(R.string.hasil_label_satir, labelArtikel("Satir").teks)
        assertEquals(
            NamaCiri.DariResource(R.string.ciri_nama_desakan_waktu),
            namaCiri(" Desakan_Waktu ", "x"),
        )
        assertEquals(
            listOf(R.string.hasil_terbatas_cek_fakta, R.string.hasil_terbatas_ai),
            kalimatPemeriksaanTerbatas(listOf(" CEK_FAKTA", "Ai ")),
        )
    }
}
