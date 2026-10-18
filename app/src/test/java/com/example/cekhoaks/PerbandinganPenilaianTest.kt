package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class PerbandinganPenilaianTest {

    @Test
    fun labelPenilaianSesuai() {
        assertEquals(R.string.penilaian_percaya, labelPenilaian(Penilaian.PERCAYA))
        assertEquals(R.string.penilaian_ragu, labelPenilaian(Penilaian.RAGU))
        assertEquals(R.string.penilaian_tidak_percaya, labelPenilaian(Penilaian.TIDAK_PERCAYA))
        assertEquals(R.string.penilaian_dilewati, labelPenilaian(Penilaian.DILEWATI))
    }

    @Test
    fun dilewatiUntukSemuaTingkat() {
        for (t in Tingkat.entries) {
            assertEquals(R.string.banding_pesan_dilewati, pesanPerbandingan(Penilaian.DILEWATI, t))
        }
    }

    @Test
    fun tidakDitemukan() {
        assertEquals(
            R.string.banding_pesan_tidak_ditemukan_percaya,
            pesanPerbandingan(Penilaian.PERCAYA, Tingkat.TIDAK_DITEMUKAN),
        )
        assertEquals(
            R.string.banding_pesan_tidak_ditemukan_ragu,
            pesanPerbandingan(Penilaian.RAGU, Tingkat.TIDAK_DITEMUKAN),
        )
        assertEquals(
            R.string.banding_pesan_tidak_ditemukan_tidak_percaya,
            pesanPerbandingan(Penilaian.TIDAK_PERCAYA, Tingkat.TIDAK_DITEMUKAN),
        )
    }

    @Test
    fun kuatPercaya() {
        assertEquals(R.string.banding_pesan_kuat_percaya, pesanPerbandingan(Penilaian.PERCAYA, Tingkat.KUAT))
    }

    @Test
    fun hatiHatiPercayaMengikutiPenyebab() {
        val peta = mapOf(
            PenyebabHatiHati.CIRI to R.string.banding_pesan_hati_hati_percaya_ciri,
            PenyebabHatiHati.ARTIKEL_SATIR to R.string.banding_pesan_hati_hati_percaya_satir,
            PenyebabHatiHati.ARTIKEL_LAIN to R.string.banding_pesan_hati_hati_percaya_artikel,
            PenyebabHatiHati.UMUM to R.string.banding_pesan_hati_hati_percaya_umum,
        )
        for ((penyebab, id) in peta) {
            assertEquals(id, pesanPerbandingan(Penilaian.PERCAYA, Tingkat.HATI_HATI, penyebab))
        }
        assertEquals(4, peta.values.toSet().size)
    }

    @Test
    fun penyebabTidakMempengaruhiPenilaianWaspada() {
        for (t in listOf(Tingkat.KUAT, Tingkat.HATI_HATI)) {
            for (p in listOf(Penilaian.RAGU, Penilaian.TIDAK_PERCAYA)) {
                for (s in PenyebabHatiHati.entries) {
                    assertEquals(R.string.banding_pesan_ada_ciri_waspada, pesanPerbandingan(p, t, s))
                }
            }
        }
    }

    private fun ciri() = Ciri("desakan_waktu", "Desakan waktu", listOf("segera"), "penjelasan", "sedang")
    private fun artikel(label: String) = ArtikelCekFakta("j", "s", "https://example.com", 0.7, label)
    private fun hasil(tingkat: Tingkat, ciri: List<Ciri>, artikel: List<ArtikelCekFakta>) =
        HasilAnalisis("id", tingkat, null, ciri, artikel, "teks", 1L)

    @Test
    fun penyebabDisimpulkanDariData() {
        assertEquals(PenyebabHatiHati.CIRI, penyebabHatiHati(hasil(Tingkat.HATI_HATI, listOf(ciri()), emptyList())))
        // Ciri menang atas artikel, termasuk artikel satir.
        assertEquals(
            PenyebabHatiHati.CIRI,
            penyebabHatiHati(hasil(Tingkat.HATI_HATI, listOf(ciri()), listOf(artikel("satir")))),
        )
        assertEquals(
            PenyebabHatiHati.ARTIKEL_SATIR,
            penyebabHatiHati(hasil(Tingkat.HATI_HATI, emptyList(), listOf(artikel("salah"), artikel("satir")))),
        )
        for (label in listOf("salah", "klarifikasi", "belum_terbukti", "benar", "penipuan", "label_baru")) {
            assertEquals(
                label,
                PenyebabHatiHati.ARTIKEL_LAIN,
                penyebabHatiHati(hasil(Tingkat.HATI_HATI, emptyList(), listOf(artikel(label)))),
            )
        }
        assertEquals(PenyebabHatiHati.UMUM, penyebabHatiHati(hasil(Tingkat.HATI_HATI, emptyList(), emptyList())))
    }

    @Test
    fun pesanDariHasilLengkap() {
        assertEquals(
            R.string.banding_pesan_hati_hati_percaya_satir,
            pesanPerbandingan(Penilaian.PERCAYA, hasil(Tingkat.HATI_HATI, emptyList(), listOf(artikel("satir")))),
        )
        assertEquals(
            R.string.banding_pesan_kuat_percaya,
            pesanPerbandingan(Penilaian.PERCAYA, hasil(Tingkat.KUAT, emptyList(), listOf(artikel("salah")))),
        )
    }

    @Test
    fun semuaKombinasiMenghasilkanPesan() {
        for (p in Penilaian.entries) for (t in Tingkat.entries) for (s in PenyebabHatiHati.entries) {
            assertNotEquals(0, pesanPerbandingan(p, t, s))
        }
    }

    @Test
    fun tingkatTidakDikenalTidakDibandingkan() {
        for (p in listOf(Penilaian.PERCAYA, Penilaian.RAGU, Penilaian.TIDAK_PERCAYA)) {
            assertEquals(R.string.banding_pesan_tidak_dikenal, pesanPerbandingan(p, Tingkat.TIDAK_DIKENAL))
        }
    }

    @Test
    fun pesanBerbedaAntarKelompok() {
        assertNotEquals(
            pesanPerbandingan(Penilaian.PERCAYA, Tingkat.KUAT),
            pesanPerbandingan(Penilaian.RAGU, Tingkat.KUAT),
        )
    }
}
