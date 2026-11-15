package com.example.cekhoaks

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import okhttp3.Dns
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.net.InetAddress
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

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
    fun semuaPermintaanMembawaHeaderLewatiPeringatanNgrok() = runBlocking {
        server.enqueue(json(200, """{"status": "ok", "versi": "0.7.0"}"""))
        server.enqueue(json(200, hasilMinimal))
        klien.cekKesehatan(urlDasar)
        klien.analisis(urlDasar, byteArrayOf(1, 2, 3))
        repeat(2) {
            assertEquals("1", server.takeRequest().getHeader(KlienApi.HEADER_LEWATI_PERINGATAN_NGROK))
        }
    }

    @Test
    fun serverSibukTerbacaSebagaiKodeGalat() = runBlocking {
        server.enqueue(json(503, """{"galat": {"kode": "server_sibuk", "pesan": "penuh"}}"""))
        assertEquals(
            HasilPanggilan.Gagal(JenisGagal.GalatServer(503, KodeGalat.SERVER_SIBUK)),
            klien.analisis(urlDasar, byteArrayOf(1, 2, 3)),
        )
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

    /** DNS tiruan: [gagalPertama] pencarian pertama gagal, sisanya diteruskan ke DNS sistem. */
    private class DnsGagalAwal(private val gagalPertama: Int) : Dns {
        val dipanggil = AtomicInteger()
        override fun lookup(hostname: String): List<InetAddress> {
            if (dipanggil.incrementAndGet() <= gagalPertama) throw UnknownHostException("uji: sinyal belum siap")
            return Dns.SYSTEM.lookup(hostname)
        }
    }

    @Test
    fun gagalSambungSekaliDiulangOtomatisLaluBerhasil() = runBlocking {
        val dns = DnsGagalAwal(gagalPertama = 1)
        val klienUlang = KlienApi(OkHttpClient.Builder().dns(dns).build())
        server.enqueue(json(200, hasilMinimal))
        val hasil = klienUlang.analisis(urlDasar.replace("127.0.0.1", "localhost"), byteArrayOf(1))
        assertTrue(hasil.toString(), hasil is HasilPanggilan.Berhasil)
        assertEquals(2, dns.dipanggil.get())
        assertEquals(1, server.requestCount)
    }

    @Test
    fun gagalSambungDuaKaliBerhentiSetelahSatuUlangan() = runBlocking {
        val dns = DnsGagalAwal(gagalPertama = 10)
        val klienUlang = KlienApi(OkHttpClient.Builder().dns(dns).build())
        val hasil = klienUlang.analisis(urlDasar.replace("127.0.0.1", "localhost"), byteArrayOf(1))
        assertTrue(hasil.toString(), (hasil as HasilPanggilan.Gagal).jenis is JenisGagal.TidakTerjangkau)
        assertEquals(KlienApi.MAKS_PERCOBAAN_SAMBUNG, dns.dipanggil.get())
        assertEquals(0, server.requestCount)
    }

    @Test
    fun putusSetelahTersambungTidakDiulang() = runBlocking {
        // Gambar mungkin sudah terkirim: jangan kirim ulang diam-diam.
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST))
        server.enqueue(json(200, hasilMinimal))
        val klienTanpaUlangOkHttp = KlienApi(OkHttpClient.Builder().retryOnConnectionFailure(false).build())
        val hasil = klienTanpaUlangOkHttp.analisis(urlDasar, byteArrayOf(1))
        assertTrue(hasil.toString(), (hasil as HasilPanggilan.Gagal).jenis is JenisGagal.TidakTerjangkau)
        assertEquals(1, server.requestCount)
    }

    @Test
    fun batasTotalMenghentikanAnalisisSebagaiWaktuHabis() = runBlocking {
        val klienBatas = KlienApi(batasTotalAnalisisMs = 500)
        server.enqueue(json(200, hasilMinimal).setHeadersDelay(5, TimeUnit.SECONDS))
        val mulai = System.nanoTime()
        assertEquals(HasilPanggilan.Gagal(JenisGagal.WaktuHabis), klienBatas.analisis(urlDasar, byteArrayOf(1)))
        assertTrue(TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - mulai) < 3_000)
    }

    @Test
    fun batasBawaanSesuaiKeputusanSesi82() {
        assertEquals(15L, KlienApi.TIMEOUT_CONNECT_DETIK)
        assertEquals(60L, KlienApi.BATAS_TOTAL_ANALISIS_DETIK)
        assertEquals(2, KlienApi.MAKS_PERCOBAAN_SAMBUNG)
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

    // ---------- Halaman galat ngrok (Sesi 8.3) ----------

    private fun halamanNgrok(status: Int, kode: String?, isi: String = "<!DOCTYPE html><html>$kode</html>") =
        MockResponse().setResponseCode(status).setHeader("Content-Type", "text/html").setBody(isi)
            .apply { if (kode != null) setHeader("Ngrok-Error-Code", kode) }

    @Test
    fun ngrokEndpointOffline3200MenjadiServerTidakAktif() = runBlocking {
        // Bentuk yang teramati 2026-11-15: 404, text/html, header Ngrok-Error-Code: ERR_NGROK_3200.
        server.enqueue(halamanNgrok(404, "ERR_NGROK_3200"))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.ServerTidakAktif), klien.analisis(urlDasar, byteArrayOf(1)))
        server.enqueue(halamanNgrok(404, "ERR_NGROK_3200"))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.ServerTidakAktif), klien.cekKesehatan(urlDasar))
    }

    @Test
    fun ngrokGagalKeServerLokal8012MenjadiServerTidakAktif() = runBlocking {
        server.enqueue(halamanNgrok(502, "ERR_NGROK_8012"))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.ServerTidakAktif), klien.analisis(urlDasar, byteArrayOf(1)))
    }

    @Test
    fun kodeNgrokDariIsiBilaHeaderTidakAda() = runBlocking {
        server.enqueue(halamanNgrok(404, null, "<html><p>ERR_NGROK_3200</p></html>"))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.ServerTidakAktif), klien.analisis(urlDasar, byteArrayOf(1)))
    }

    @Test
    fun kodeNgrokLainTetapGalatServer() = runBlocking {
        server.enqueue(halamanNgrok(502, "ERR_NGROK_3004"))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.GalatServer(502, null)), klien.analisis(urlDasar, byteArrayOf(1)))
    }

    @Test
    fun galatServerVeritasTanpaHeaderNgrokTidakBerubah() = runBlocking {
        server.enqueue(json(500, """{"galat": {"kode": "galat_server", "pesan": "x"}}"""))
        assertEquals(
            HasilPanggilan.Gagal(JenisGagal.GalatServer(500, KodeGalat.GALAT_SERVER)),
            klien.analisis(urlDasar, byteArrayOf(1)),
        )
        // 404 biasa (misalnya alamat mengarah ke server lain) bukan "server tidak aktif".
        server.enqueue(MockResponse().setResponseCode(404).setBody("Not Found"))
        assertEquals(HasilPanggilan.Gagal(JenisGagal.GalatServer(404, null)), klien.cekKesehatan(urlDasar))
    }

    @Test
    fun kodeGalatNgrokMengutamakanHeader() {
        assertEquals("ERR_NGROK_3200", KlienApi.kodeGalatNgrok(" err_ngrok_3200 ", ""))
        assertEquals("ERR_NGROK_8012", KlienApi.kodeGalatNgrok(null, "...ERR_NGROK_8012..."))
        assertEquals("ERR_NGROK_3200", KlienApi.kodeGalatNgrok("ERR_NGROK_3200", "ERR_NGROK_8012"))
        assertEquals(null, KlienApi.kodeGalatNgrok(null, """{"galat": {"kode": "galat_server"}}"""))
        assertEquals(null, KlienApi.kodeGalatNgrok("", ""))
    }
}
