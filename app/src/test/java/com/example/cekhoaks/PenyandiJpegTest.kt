package com.example.cekhoaks

import org.junit.Assert.assertEquals
import org.junit.Test

class PenyandiJpegTest {

    @Test
    fun gambarKecilTidakDiubah() {
        assertEquals(1000 to 500, PenyandiJpeg.ukuranTarget(1000, 500))
        assertEquals(2000 to 2000, PenyandiJpeg.ukuranTarget(2000, 2000))
    }

    @Test
    fun sisiTerpanjangDibatasiSecaraProporsional() {
        assertEquals(2000 to 500, PenyandiJpeg.ukuranTarget(4000, 1000))
        assertEquals(900 to 2000, PenyandiJpeg.ukuranTarget(1080, 2400))
        assertEquals(2000 to 2000, PenyandiJpeg.ukuranTarget(2001, 2001))
    }

    @Test
    fun sisiPendekMinimalSatuPiksel() {
        assertEquals(2000 to 1, PenyandiJpeg.ukuranTarget(10000, 3))
        assertEquals(1 to 2000, PenyandiJpeg.ukuranTarget(2, 20000))
    }
}
