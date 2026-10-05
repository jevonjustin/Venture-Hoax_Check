package com.example.cekhoaks

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.concurrent.TimeUnit

/** Menguji KlienApi terhadap server HTTP tiruan (MockWebServer) di dalam proses test. */
class KlienApiTest {

    private lateinit var server: MockWebServer
    private lateinit var urlDasar: String
    private val klien = KlienApi()

    private val hasilMinimal = """
        {"id_permintaan": "abc", "tingkat": "hati_hati", "klaim_utama": null, "ciri": [],
         "cek_fakta": [], "teks_terbaca": "teks", "durasi_ms": 12}
    """.trimIndent()

    @Before
    fun mulai() {
        server = MockWebServer()
        server.start()
        urlDasar = server.url("/").toString().removeSuffix("/")
    }

    @After
    fun selesai() {
        server.shutdown()
    }

    private fun json(kode: Int, isi: String) =
        MockResponse().setResponseCode(kode).setHeader("Content-Type", "application/json").setBody(isi)

    @Test
    fun cekKesehatanBerhasil() = runBlocking {
        server.enqueue(json(200, """{"status": "ok", "versi": "0.4.0"}"""))
        val hasil = klien.cekKesehatan(urlDasar)
        assertEquals(HasilPanggilan.Berhasil(StatusServer("ok", "0.4.0")), hasil)
        assertEquals("/health", server.takeRequest().path)
    }

    @Test
    fun analisisMengirimMultipartDenganFieldGambar() = runBlocking {
        server.enqueue(json(200, hasilMinimal))
        val jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 1, 2, 3)

        val hasil = klien.analisis(urlDasar, jpeg)

        assertTrue(hasil is HasilPanggilan.Berhasil)
        assertEquals(Tingkat.HATI_HATI, (hasil as HasilPanggilan.Berhasil).data.tingkat)
        val permintaan = server.takeRequest()
        assertEquals("POST", permintaan.method)
        assertEquals("/analisis", permintaan.path)
        assertTrue(permintaan.getHeader("Content-Type")!!.startsWith("multipart/form-data"))
        val body = permintaan.body.readUtf8()
        assertTrue(body.contains("name=\"gambar\""))
        assertTrue(body.contains("Content-Type: image/jpeg"))
    }

    @Test
    fun galatDenganFormatKontrak() = runBlocking {
        server.enqueue(json(422, """{"galat": {"kode": "teks_tidak_terbaca", "pesan": "x"}}"""))
        val hasil = klien.analisis(urlDasar, byteArrayOf(1))
        assertEquals(
            HasilPanggilan.Gagal(JenisGagal.GalatServer(422, KodeGalat.TEKS_TIDAK_TERBACA)),
            hasil,
        )
    }

    @Test
    fun galatTanpaFormatKontrak() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(502).setBody("<html>Bad Gateway</html>"))
        assertEquals(
            HasilPanggilan.Gagal(JenisGagal.GalatServer(502, null)),
            klien.analisis(urlDasar, byteArrayOf(1)),
        )
    }

    @Test
    fun responsBukanKontrak() = runBlocking {
        server.enqueue(json(200, """{"pesan": "halo dari server lain"}"""))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.ResponsTidakDikenali), klien.analisis(urlDasar, byteArrayOf(1)))
    }

    @Test
    fun urlKosong() = runBlocking {
        assertEquals(HasilPanggilan.Gagal(JenisGagal.UrlBelumDiatur), klien.analisis("", byteArrayOf(1)))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.UrlBelumDiatur), klien.cekKesehatan("  "))
    }

    @Test
    fun serverMatiBerartiTidakTerjangkau() = runBlocking {
        server.shutdown()
        val hasil = klien.cekKesehatan(urlDasar)
        assertTrue(hasil.toString(), (hasil as HasilPanggilan.Gagal).jenis is JenisGagal.TidakTerjangkau)
    }

    @Test
    fun serverLambatBerartiWaktuHabis() = runBlocking {
        val klienCepat = KlienApi(
            OkHttpClient.Builder().readTimeout(200, TimeUnit.MILLISECONDS).build(),
        )
        server.enqueue(json(200, hasilMinimal).setHeadersDelay(2, TimeUnit.SECONDS))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.WaktuHabis), klienCepat.analisis(urlDasar, byteArrayOf(1)))
    }

    @Test
    fun pembatalanMemutusPermintaan() = runBlocking {
        val http = KlienApi.buatHttpBawaan()
        val klienDipantau = KlienApi(http)
        server.enqueue(json(200, hasilMinimal).setHeadersDelay(30, TimeUnit.SECONDS))
        val pekerjaan = launch(Dispatchers.IO) { klienDipantau.analisis(urlDasar, byteArrayOf(1)) }
        server.takeRequest(5, TimeUnit.SECONDS)
        assertEquals(1, http.dispatcher.runningCallsCount())

        withTimeout(2_000) { pekerjaan.cancelAndJoin() }
        assertTrue(pekerjaan.isCancelled)
        // Panggilan HTTP juga berhenti, bukan hanya coroutine-nya. Tanpa call.cancel(),
        // panggilan ini baru selesai setelah 30 detik.
        withTimeout(2_000) {
            while (http.dispatcher.runningCallsCount() > 0) delay(20)
        }
    }
}
