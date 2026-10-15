package com.example.cekhoaks

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.SystemClock
import android.util.DisplayMetrics
import android.util.Log
import android.view.Display
import androidx.core.graphics.createBitmap

/**
 * Menyimpan satu sesi rekam layar selama tombol cek aktif dan menghasilkan Bitmap layar penuh.
 *
 * Cara kerjanya: MediaProjection "menyalin" layar HP ke sebuah layar virtual (VirtualDisplay).
 * Isi layar virtual itu dikirim ke ImageReader sebagai rangkaian frame, tetapi hanya saat isi
 * layar berubah. Frame baru disimpan setelah [ambil] dipanggil, dan pemilihannya diatur oleh
 * [PemilihFrame]. Di luar itu, frame yang masuk langsung ditutup.
 *
 * VirtualDisplay dan ImageReader dibuat satu kali saja. Sejak Android 14, createVirtualDisplay
 * tidak boleh dipanggil lebih dari sekali pada MediaProjection yang sama, jadi saat layar
 * diputar ukurannya disesuaikan lewat [sesuaikanUkuran], tidak dibuat ulang.
 *
 * Pola yang diadaptasi (lisensi MIT):
 * - MediaProjection.Callback didaftarkan sebelum createVirtualDisplay, dan konversi Image ke
 *   Bitmap dengan memperhitungkan padding baris: Ervareza Naurian, screen-translator,
 *   https://github.com/ervareza/screen-translator
 */
class PengambilLayar(
    private val context: Context,
    private val proyeksi: MediaProjection,
    private val onDihentikanSistem: () -> Unit,
) {

    private val handlerUtama = Handler(Looper.getMainLooper())

    // Thread latar khusus untuk ImageReader, agar penerimaan frame dan konversi Bitmap
    // tidak membebani thread utama (thread yang menggambar tampilan).
    private val threadTangkap = HandlerThread("CekHoaksTangkap").apply { start() }
    private val handlerTangkap = Handler(threadTangkap.looper)

    // Setelah mulai(), nilai-nilai ini hanya diakses dari threadTangkap.
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var ukuran: Ukuran? = null
    private val pemilih = PemilihFrame<Image>(jam = { SystemClock.uptimeMillis() })
    private var onSelesaiTertunda: ((Bitmap?) -> Unit)? = null
    private val periksaTertunda = Runnable { jalankan(pemilih.periksa()) }

    @Volatile
    private var berhenti = false

    // Dipanggil saat sesi dihentikan dari luar aplikasi, misalnya lewat panel sistem.
    private val callback = object : MediaProjection.Callback() {
        override fun onStop() {
            if (berhenti) return
            Log.i(TAG, "Sesi rekam layar dihentikan oleh sistem")
            onDihentikanSistem()
        }
    }

    private val pendengarFrame = ImageReader.OnImageAvailableListener { reader ->
        // acquireLatestImage mengambil semua frame yang antre sekaligus. Pendengar ini bisa
        // berjalan lagi untuk frame yang sudah ikut terambil, dan saat itu hasilnya null.
        // ImageReader hanya punya beberapa slot buffer, jadi setiap frame tetap harus diambil
        // lalu ditutup; PemilihFrame yang memutuskan frame mana yang disimpan.
        val baru = try {
            reader.acquireLatestImage()
        } catch (e: IllegalStateException) {
            // ImageReader sudah ditutup (misalnya tepat saat layar diputar).
            null
        }
        pemilih.frameMasuk(baru)?.let(::jalankan)
    }

    /** Memulai layar virtual. Dipanggil sekali dari thread utama. Mengembalikan false jika gagal. */
    fun mulai(): Boolean {
        // Wajib sebelum createVirtualDisplay sejak Android 14.
        proyeksi.registerCallback(callback, handlerUtama)

        val ukuranAwal = ukuranLayar()
        val reader = buatImageReader(ukuranAwal)
        val display = try {
            proyeksi.createVirtualDisplay(
                NAMA_LAYAR_VIRTUAL,
                ukuranAwal.lebar,
                ukuranAwal.tinggi,
                ukuranAwal.dpi,
                // AUTO_MIRROR: layar virtual menampilkan salinan layar utama HP.
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader.surface,
                null,
                null,
            )
        } catch (e: RuntimeException) {
            Log.e(TAG, "Gagal membuat layar virtual", e)
            null
        }

        imageReader = reader
        ukuran = ukuranAwal
        virtualDisplay = display
        return display != null
    }

    /**
     * Mengambil layar sebagai Bitmap. Dipanggil tepat setelah tombol cek disembunyikan, karena
     * hanya frame yang digambar setelah itu yang dipakai. [onSelesai] dipanggil di thread utama
     * dengan Bitmap hasilnya, atau null jika tidak ada frame atau konversi gagal.
     */
    fun ambil(onSelesai: (Bitmap?) -> Unit) {
        handlerTangkap.post {
            onSelesaiTertunda = onSelesai
            jalankan(pemilih.mulai())
        }
    }

    /** Menjalankan keputusan PemilihFrame. Hanya dipanggil dari threadTangkap. */
    private fun jalankan(keputusan: PemilihFrame.Keputusan<Image>) {
        handlerTangkap.removeCallbacks(periksaTertunda)
        when (keputusan) {
            is PemilihFrame.Keputusan.PeriksaLagi ->
                handlerTangkap.postDelayed(periksaTertunda, keputusan.setelahMs)
            is PemilihFrame.Keputusan.PaksaFrameBaru -> {
                Log.d(TAG, "Belum ada frame setelah tombol disembunyikan, memaksa frame baru")
                paksaFrameBaru()
                handlerTangkap.postDelayed(periksaTertunda, keputusan.setelahMs)
            }
            is PemilihFrame.Keputusan.Pakai -> {
                catatWaktu("Frame dipakai", keputusan.info)
                val gambar = keputusan.frame
                val bitmap = try {
                    keBitmap(gambar)
                } catch (e: RuntimeException) {
                    Log.e(TAG, "Gagal mengubah frame menjadi Bitmap", e)
                    null
                } finally {
                    gambar.close()
                }
                selesaikan(bitmap)
            }
            is PemilihFrame.Keputusan.Gagal -> {
                catatWaktu("Tidak ada frame", keputusan.info)
                selesaikan(null)
            }
            PemilihFrame.Keputusan.TidakMenunggu -> Unit
        }
    }

    private fun selesaikan(bitmap: Bitmap?) {
        val onSelesai = onSelesaiTertunda
        onSelesaiTertunda = null
        handlerUtama.post { if (!berhenti) onSelesai?.invoke(bitmap) }
    }

    // Hanya waktu dan jumlah frame, tanpa isi gambar.
    private fun catatWaktu(status: String, info: PemilihFrame.InfoFrame) {
        Log.d(
            TAG,
            "$status: tiba ${info.tibaMs ?: "-"} ms, diputuskan ${info.selesaiMs} ms setelah tombol " +
                "disembunyikan, ${info.jumlahFrame} frame masuk, cadangan ${if (info.cadanganDipakai) "dipakai" else "tidak"}",
        )
    }

    /**
     * Cadangan saat layar diam dan tidak ada frame yang datang. Melepas lalu memasang lagi surface
     * tujuan membuat sistem menggambar ulang isi layar virtual ke surface itu.
     */
    private fun paksaFrameBaru() {
        val display = virtualDisplay ?: return
        val surface = imageReader?.surface ?: return
        display.surface = null
        display.surface = surface
    }

    /** Menyesuaikan ukuran layar virtual dengan ukuran layar HP saat ini, misalnya setelah diputar. */
    fun sesuaikanUkuran() {
        val ukuranBaru = ukuranLayar()
        handlerTangkap.post {
            val display = virtualDisplay ?: return@post
            if (berhenti || ukuranBaru == ukuran) return@post

            // Buffer ImageReader berukuran tetap, jadi dibuat ImageReader baru seukuran layar baru.
            val readerLama = imageReader
            val readerBaru = buatImageReader(ukuranBaru)
            display.resize(ukuranBaru.lebar, ukuranBaru.tinggi, ukuranBaru.dpi)
            display.surface = readerBaru.surface

            // Pengambilan yang sedang menunggu dibatalkan; frame dari ukuran lama tidak dipakai.
            if (pemilih.batalkan()) {
                handlerTangkap.removeCallbacks(periksaTertunda)
                selesaikan(null)
            }
            readerLama?.setOnImageAvailableListener(null, null)
            readerLama?.close()
            imageReader = readerBaru
            ukuran = ukuranBaru
            Log.d(TAG, "Ukuran layar virtual disesuaikan: ${ukuranBaru.lebar} x ${ukuranBaru.tinggi}")
        }
    }

    /** Melepas layar virtual, menutup ImageReader, dan mengakhiri sesi rekam layar. */
    fun hentikan() {
        if (berhenti) return
        berhenti = true
        // Dilepas dulu agar proyeksi.stop() di bawah tidak memicu onStop milik kita sendiri.
        proyeksi.unregisterCallback(callback)

        handlerTangkap.post {
            virtualDisplay?.release()
            virtualDisplay = null
            handlerTangkap.removeCallbacks(periksaTertunda)
            pemilih.batalkan()
            onSelesaiTertunda = null
            imageReader?.setOnImageAvailableListener(null, null)
            imageReader?.close()
            imageReader = null
            proyeksi.stop()
        }
        // quitSafely tetap menjalankan tugas yang sudah antre (termasuk pembersihan di atas).
        threadTangkap.quitSafely()
    }

    private fun keBitmap(gambar: Image): Bitmap {
        val bidang = gambar.planes[0]
        // Panjang satu baris di memori (rowStride) bisa lebih besar dari lebar gambar karena
        // ada padding untuk perataan memori. Bitmap dibuat selebar baris memori dulu, lalu
        // kolom padding di sisi kanan dipotong.
        val lebarBaris = bidang.rowStride / bidang.pixelStride
        val mentah = createBitmap(lebarBaris, gambar.height)
        mentah.copyPixelsFromBuffer(bidang.buffer)
        if (lebarBaris == gambar.width) return mentah

        val hasil = Bitmap.createBitmap(mentah, 0, 0, gambar.width, gambar.height)
        mentah.recycle()
        return hasil
    }

    // Format RGBA_8888 berasal dari PixelFormat, sedangkan lint mengharapkan konstanta ImageFormat.
    @SuppressLint("WrongConstant")
    private fun buatImageReader(ukuran: Ukuran): ImageReader =
        ImageReader.newInstance(ukuran.lebar, ukuran.tinggi, PixelFormat.RGBA_8888, MAKS_FRAME).apply {
            setOnImageAvailableListener(pendengarFrame, handlerTangkap)
        }

    /** Ukuran layar fisik penuh, termasuk status bar dan navigation bar, sesuai orientasi saat ini. */
    private fun ukuranLayar(): Ukuran {
        val metrik = DisplayMetrics()
        val layar = context.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
        if (layar != null) {
            @Suppress("DEPRECATION")
            layar.getRealMetrics(metrik)
        } else {
            metrik.setTo(context.resources.displayMetrics)
        }
        return Ukuran(metrik.widthPixels, metrik.heightPixels, metrik.densityDpi)
    }

    private data class Ukuran(val lebar: Int, val tinggi: Int, val dpi: Int)

    companion object {
        private const val TAG = "CekHoaks"
        private const val NAMA_LAYAR_VIRTUAL = "CekHoaksLayar"
        private const val MAKS_FRAME = 2
    }
}
