package com.example.cekhoaks

import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.SerializationException
import okhttp3.Call
import okhttp3.Callback
import okhttp3.Connection
import okhttp3.EventListener
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.io.InterruptedIOException
import java.net.UnknownServiceException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Hasil satu panggilan ke server: berhasil dengan data, atau gagal dengan jenis galatnya. */
sealed interface HasilPanggilan<out T> {
    data class Berhasil<T>(val data: T) : HasilPanggilan<T>
    data class Gagal(val jenis: JenisGagal) : HasilPanggilan<Nothing>
}

sealed interface JenisGagal {
    /** Alamat server kosong atau tidak valid. */
    data object UrlBelumDiatur : JenisGagal

    /** Koneksi ke server tidak terbentuk (server mati, alamat salah, beda jaringan, firewall). */
    data class TidakTerjangkau(val detail: String) : JenisGagal

    /** Sudah tersambung, tetapi server tidak menjawab dalam batas waktu baca. */
    data object WaktuHabis : JenisGagal

    /** HTTP tanpa TLS diblokir Android (terjadi di build release). */
    data object CleartextDiblokir : JenisGagal

    /** Server menjawab dengan status galat. [kode] null jika isinya bukan format galat kontrak. */
    data class GalatServer(val statusHttp: Int, val kode: String?) : JenisGagal

    /** Status 2xx, tetapi isinya tidak sesuai kontrak (misalnya alamat mengarah ke server lain). */
    data object ResponsTidakDikenali : JenisGagal
}

/**
 * Klien HTTP untuk server Cek Hoaks (kontrak di docs/API.md).
 *
 * Setiap fungsi adalah fungsi suspend: pemanggil menunggu tanpa memblokir main thread, dan
 * jika coroutine pemanggil dibatalkan (misalnya tombol Batal), permintaan HTTP ikut diputus.
 */
class KlienApi(
    private val http: OkHttpClient = buatHttpBawaan(),
    /** Batas waktu total satu analisis, termasuk percobaan ulang menyambung. */
    private val batasTotalAnalisisMs: Long = TimeUnit.SECONDS.toMillis(BATAS_TOTAL_ANALISIS_DETIK),
    private val batasTotalKesehatanMs: Long = TimeUnit.SECONDS.toMillis(BATAS_TOTAL_KESEHATAN_DETIK),
) {

    suspend fun cekKesehatan(urlDasar: String): HasilPanggilan<StatusServer> {
        val url = gabungUrl(urlDasar, "health") ?: return HasilPanggilan.Gagal(JenisGagal.UrlBelumDiatur)
        // Cek kesehatan tidak perlu menunggu selama analisis.
        val klien = http.newBuilder().readTimeout(TIMEOUT_BACA_KESEHATAN_DETIK, TimeUnit.SECONDS).build()
        return panggil(klien, permintaan(url).get().build(), StatusServer.serializer(), batasTotalKesehatanMs)
    }

    suspend fun analisis(urlDasar: String, jpeg: ByteArray): HasilPanggilan<HasilAnalisis> {
        val url = gabungUrl(urlDasar, "analisis") ?: return HasilPanggilan.Gagal(JenisGagal.UrlBelumDiatur)
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(FIELD_GAMBAR, "potongan.jpg", jpeg.toRequestBody(JENIS_JPEG))
            .build()
        return panggil(http, permintaan(url).post(body).build(), HasilAnalisis.serializer(), batasTotalAnalisisMs)
    }

    private suspend fun <T> panggil(
        klienDasar: OkHttpClient,
        request: Request,
        pembaca: DeserializationStrategy<T>,
        batasTotalMs: Long,
    ): HasilPanggilan<T> {
        val tenggat = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(batasTotalMs)
        var percobaan = 0
        var jawaban: Pair<Int, String>? = null
        while (jawaban == null) {
            percobaan++
            // Penanda apakah koneksi sempat terbentuk, untuk membedakan "server tidak terjangkau"
            // (gagal menyambung) dari "server terlalu lama menjawab" (timeout saat membaca).
            val pemantau = PemantauKoneksi()
            val sisaMs = TimeUnit.NANOSECONDS.toMillis(tenggat - System.nanoTime()).coerceAtLeast(1)
            // callTimeout menjaga batas total, termasuk waktu yang sudah terpakai percobaan pertama.
            val klien = klienDasar.newBuilder()
                .eventListener(pemantau)
                .callTimeout(sisaMs, TimeUnit.MILLISECONDS)
                .build()
            val gagal = try {
                jawaban = klien.newCall(request).tunggu()
                continue
            } catch (e: IOException) {
                e
            }
            // Satu percobaan ulang hanya bila koneksi belum pernah terbentuk, jadi gambar pasti belum
            // terkirim (misalnya sinyal seluler baru bangun). Galat setelah tersambung tidak diulang.
            val bisaDiulang = !pemantau.tersambung && percobaan < MAKS_PERCOBAAN_SAMBUNG &&
                !cleartextDiblokir(gagal) && tenggat - System.nanoTime() > 0
            if (bisaDiulang) continue
            return HasilPanggilan.Gagal(jenisGagal(gagal, pemantau.tersambung))
        }
        val (status, isi) = jawaban

        if (status !in 200..299) {
            val kode = try {
                jsonApi.decodeFromString(ResponsGalat.serializer(), isi).galat.kode
            } catch (_: SerializationException) {
                null
            } catch (_: IllegalArgumentException) {
                null
            }
            return HasilPanggilan.Gagal(JenisGagal.GalatServer(status, kode))
        }
        return try {
            HasilPanggilan.Berhasil(jsonApi.decodeFromString(pembaca, isi))
        } catch (_: SerializationException) {
            HasilPanggilan.Gagal(JenisGagal.ResponsTidakDikenali)
        } catch (_: IllegalArgumentException) {
            HasilPanggilan.Gagal(JenisGagal.ResponsTidakDikenali)
        }
    }

    /**
     * Menjalankan permintaan di thread milik OkHttp lalu menunggu jawabannya.
     * Jika coroutine dibatalkan, call.cancel() memutus koneksi saat itu juga.
     */
    private suspend fun Call.tunggu(): Pair<Int, String> = suspendCancellableCoroutine { lanjutan ->
        lanjutan.invokeOnCancellation { cancel() }
        enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                lanjutan.resumeWithException(e)
            }

            override fun onResponse(call: Call, response: Response) {
                val hasil = try {
                    response.use { it.code to it.body.string() }
                } catch (e: IOException) {
                    lanjutan.resumeWithException(e)
                    return
                }
                lanjutan.resume(hasil)
            }
        })
    }

    // Pesan ini dilempar OkHttp saat network security config melarang HTTP biasa.
    private fun cleartextDiblokir(e: IOException) =
        e is UnknownServiceException && e.message?.contains("CLEARTEXT") == true

    private fun jenisGagal(e: IOException, tersambung: Boolean): JenisGagal = when {
        cleartextDiblokir(e) -> JenisGagal.CleartextDiblokir
        // InterruptedIOException mencakup timeout soket dan callTimeout (batas total).
        e is InterruptedIOException && tersambung -> JenisGagal.WaktuHabis
        else -> JenisGagal.TidakTerjangkau(e.toString())
    }

    private class PemantauKoneksi : EventListener() {
        @Volatile var tersambung = false

        override fun connectionAcquired(call: Call, connection: Connection) {
            tersambung = true
        }
    }

    companion object {
        /**
         * Batas waktu membentuk koneksi ke server (TCP dan TLS). Di data seluler, sambungan pertama
         * setelah radio diam bisa lebih dari 5 detik (uji HP Sesi 8.2).
         */
        const val TIMEOUT_CONNECT_DETIK = 15L

        /** Berapa kali mencoba menyambung bila koneksi belum terbentuk (1 percobaan ulang). */
        const val MAKS_PERCOBAAN_SAMBUNG = 2

        /** Batas total satu analisis dari kirim sampai respons, termasuk percobaan ulang. */
        const val BATAS_TOTAL_ANALISIS_DETIK = 60L

        /** Cek kesehatan: batas baca dan batas total yang lebih pendek. */
        const val TIMEOUT_BACA_KESEHATAN_DETIK = 5L
        const val BATAS_TOTAL_KESEHATAN_DETIK = 35L

        /** Batas waktu menunggu jawaban analisis. Model sungguhan (tahap 5) bisa lambat. */
        const val TIMEOUT_READ_DETIK = 60L

        private const val FIELD_GAMBAR = "gambar"
        private val JENIS_JPEG = "image/jpeg".toMediaType()

        /** Satu klien dipakai bersama agar koneksi dan thread OkHttp tidak dibuat berulang. */
        val bersama: KlienApi by lazy { KlienApi() }

        fun buatHttpBawaan(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(TIMEOUT_CONNECT_DETIK, TimeUnit.SECONDS)
            .readTimeout(TIMEOUT_READ_DETIK, TimeUnit.SECONDS)
            .writeTimeout(TIMEOUT_READ_DETIK, TimeUnit.SECONDS)
            .build()

        /**
         * Header pengaman untuk alamat ngrok gratis: tanpa header ini ngrok bisa menyisipkan halaman
         * peringatan HTML sebagai pengganti respons JSON. Nilainya bebas, dan server lain mengabaikannya.
         */
        const val HEADER_LEWATI_PERINGATAN_NGROK = "ngrok-skip-browser-warning"

        private fun permintaan(url: HttpUrl) =
            Request.Builder().url(url).header(HEADER_LEWATI_PERINGATAN_NGROK, "1")

        private fun gabungUrl(urlDasar: String, jalur: String) =
            urlDasar.takeIf { it.isNotBlank() }?.toHttpUrlOrNull()?.newBuilder()?.addPathSegment(jalur)?.build()
    }
}
