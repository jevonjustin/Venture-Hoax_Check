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
        for (p in listOf(Penilaian.RAGU, Penilaian.TIDAK_PERCAYA)) {
            assertEquals(
                R.string.banding_pesan_tidak_ditemukan_waspada,
                pesanPerbandingan(p, Tingkat.TIDAK_DITEMUKAN),
            )
        }
    }

    @Test
    fun kuatDanHatiHatiDiperlakukanSama() {
        for (t in listOf(Tingkat.KUAT, Tingkat.HATI_HATI)) {
            assertEquals(R.string.banding_pesan_ada_ciri_percaya, pesanPerbandingan(Penilaian.PERCAYA, t))
            assertEquals(R.string.banding_pesan_ada_ciri_waspada, pesanPerbandingan(Penilaian.RAGU, t))
            assertEquals(R.string.banding_pesan_ada_ciri_waspada, pesanPerbandingan(Penilaian.TIDAK_PERCAYA, t))
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
