package com.example.cekhoaks

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.util.DisplayMetrics
import android.util.Log
import android.view.Display
import android.view.Gravity
import android.view.View
import android.view.WindowInsets
import android.view.WindowManager
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.IntentCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Foreground service yang menampilkan tombol cek di atas aplikasi lain dan memegang sesi
 * rekam layar (MediaProjection) selama tombol aktif.
 * Foreground service ditandai dengan notifikasi tetap, sehingga sistem tidak mematikannya
 * saat pengguna berpindah ke aplikasi lain.
 *
 * Pola yang diadaptasi (lisensi MIT):
 * - LayoutParams overlay, aksi "Stop" di notifikasi lewat PendingIntent.getService, dan urutan
 *   startForeground bertipe mediaProjection sebelum getMediaProjection:
 *   Ervareza Naurian, screen-translator, https://github.com/ervareza/screen-translator
 * - Penanda "sudah terpasang" agar overlay tidak dipasang dua kali, removeView yang aman, dan
 *   pembatasan posisi saat tombol digeser: SavinduK, SnapCrop, https://github.com/SavinduK/SnapCrop
 */
class FloatingButtonService : Service() {

    private lateinit var windowManager: WindowManager
    private val handlerUtama = Handler(Looper.getMainLooper())

    private var pengambil: PengambilLayar? = null
    private var tombol: FloatingButtonView? = null
    private var paramsTombol: WindowManager.LayoutParams? = null
    private var yTombolSaatDisentuh = 0
    private var status = Status.SIAP
    private var overlayPilih: OverlayPilihArea? = null
    private var kartu: KartuAnalisis? = null

    // Lingkup coroutine milik service: semua pekerjaan di dalamnya ikut dibatalkan di onDestroy.
    // Dispatchers.Main berarti kode berjalan di main thread kecuali dipindah dengan withContext.
    private val lingkup = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var pekerjaanKirim: Job? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        buatChannelNotifikasi()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_MATIKAN) {
            stopSelf()
            return START_NOT_STICKY
        }

        if (pengambil != null) {
            // Sesi sudah berjalan. Izin baru tidak dipakai; satu sesi dipertahankan selama tombol aktif.
            Log.w(TAG, "Tombol cek sudah aktif, permintaan mulai diabaikan")
            return START_NOT_STICKY
        }

        val kodeHasil = intent?.getIntExtra(EXTRA_KODE_HASIL, Activity.RESULT_CANCELED)
        val dataHasil = intent?.let { IntentCompat.getParcelableExtra(it, EXTRA_DATA_HASIL, Intent::class.java) }
        if (kodeHasil != Activity.RESULT_OK || dataHasil == null) {
            // Tidak terjadi lewat MainActivity, yang hanya memulai service setelah izin diberikan.
            Log.e(TAG, "Service dimulai tanpa izin rekam layar")
            stopSelf()
            return START_NOT_STICKY
        }

        // URUTAN WAJIB: service harus sudah menjadi foreground service bertipe mediaProjection
        // SEBELUM getMediaProjection dipanggil. Android 14 ke atas melempar SecurityException
        // jika urutannya terbalik.
        try {
            mulaiForeground()
        } catch (e: RuntimeException) {
            Log.e(TAG, "Gagal memulai foreground service", e)
            stopSelf()
            return START_NOT_STICKY
        }

        if (!Settings.canDrawOverlays(this)) {
            Log.w(TAG, "Izin tampil di atas aplikasi lain belum diberikan, service dihentikan")
            stopSelf()
            return START_NOT_STICKY
        }

        val proyeksi = mintaMediaProjection(kodeHasil, dataHasil)
        if (proyeksi == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        val pengambilBaru = PengambilLayar(this, proyeksi, onDihentikanSistem = ::hentikanDariSistem)
        pengambil = pengambilBaru
        if (!pengambilBaru.mulai()) {
            stopSelf()
            return START_NOT_STICKY
        }

        pasangTombol()
        return START_NOT_STICKY
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        // Saat layar diputar, lebar dan tinggi layar bertukar. Layar virtual disesuaikan agar
        // hasil tangkapan tidak gepeng, dan posisi tombol dibatasi ulang ke area layar yang baru.
        pengambil?.sesuaikanUkuran()
        val params = paramsTombol ?: return
        params.y = batasiY(params.y)
        perbaruiPosisiTombol()
    }

    override fun onDestroy() {
        bersihkan()
        lingkup.cancel()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun mulaiForeground() {
        val tipe = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
        } else {
            0
        }
        ServiceCompat.startForeground(this, ID_NOTIFIKASI, buatNotifikasi(), tipe)
    }

    private fun mintaMediaProjection(kodeHasil: Int, dataHasil: Intent): MediaProjection? {
        val manager = getSystemService(MediaProjectionManager::class.java)
        return try {
            manager.getMediaProjection(kodeHasil, dataHasil)
        } catch (e: SecurityException) {
            Log.e(TAG, "Sesi rekam layar ditolak sistem", e)
            null
        } catch (e: IllegalStateException) {
            Log.e(TAG, "Sesi rekam layar ditolak sistem", e)
            null
        }
    }

    /** Pengguna menghentikan perekaman dari panel sistem, atau sistem mengakhiri sesi. */
    private fun hentikanDariSistem() {
        bersihkan()
        stopSelf()
    }

    /** Aman dipanggil lebih dari sekali. */
    private fun bersihkan() {
        handlerUtama.removeCallbacksAndMessages(null)
        overlayPilih?.tutup()
        overlayPilih = null
        pekerjaanKirim?.cancel()
        pekerjaanKirim = null
        tutupKartu()
        lepasTombol()
        pengambil?.hentikan()
        pengambil = null
        status = Status.SIAP
        _berjalan.value = false
    }

    // --- Tombol mengambang ---

    private fun pasangTombol() {
        if (tombol != null) return

        val view = FloatingButtonView(
            this,
            onKetuk = ::ambilLayar,
            onSentuhanMulai = { yTombolSaatDisentuh = paramsTombol?.y ?: 0 },
            onGeser = { selisihY -> geserTombol(selisihY) },
        )
        val params = buatLayoutParams()
        try {
            windowManager.addView(view, params)
        } catch (e: RuntimeException) {
            // Misalnya izin dicabut tepat sebelum tombol dipasang.
            Log.e(TAG, "Gagal memasang tombol cek", e)
            stopSelf()
            return
        }
        tombol = view
        paramsTombol = params
        _berjalan.value = true
    }

    private fun lepasTombol() {
        val view = tombol ?: return
        try {
            windowManager.removeView(view)
        } catch (e: IllegalArgumentException) {
            Log.w(TAG, "Tombol cek sudah tidak terpasang", e)
        } finally {
            tombol = null
            paramsTombol = null
        }
    }

    private fun geserTombol(selisihY: Int) {
        val params = paramsTombol ?: return
        params.y = batasiY(yTombolSaatDisentuh + selisihY)
        perbaruiPosisiTombol()
    }

    private fun perbaruiPosisiTombol() {
        val view = tombol ?: return
        val params = paramsTombol ?: return
        try {
            windowManager.updateViewLayout(view, params)
        } catch (e: IllegalArgumentException) {
            Log.w(TAG, "Gagal memperbarui posisi tombol", e)
        }
    }

    private fun buatLayoutParams(): WindowManager.LayoutParams {
        val ruangBayangan = resources.getDimensionPixelSize(R.dimen.tombol_cek_ruang_bayangan)
        val jarakTepi = resources.getDimensionPixelSize(R.dimen.tombol_cek_jarak_tepi)
        val tinggiLayar = resources.displayMetrics.heightPixels

        return WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            // NOT_FOCUSABLE: tidak mengambil keyboard, dan sentuhan di luar tombol
            // diteruskan ke aplikasi di bawahnya.
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.END
            // Dengan gravity END, x adalah jarak dari tepi kanan. Ruang bayangan dikurangkan
            // agar lingkarannya sendiri berjarak 14dp dari tepi.
            x = jarakTepi - ruangBayangan
            y = batasiY((tinggiLayar * POSISI_VERTIKAL).toInt() - ruangBayangan)
        }
    }

    /**
     * Membatasi y agar tombol tidak menutupi status bar maupun navigation bar.
     * Sistem menata jendela overlay di area antara kedua bilah itu, sehingga y = 0 berarti
     * tepat di bawah status bar.
     */
    private fun batasiY(y: Int): Int {
        val tinggiJendela = resources.getDimensionPixelSize(R.dimen.tombol_cek_ukuran) +
            2 * resources.getDimensionPixelSize(R.dimen.tombol_cek_ruang_bayangan)
        val maks = (tinggiAreaAman() - tinggiJendela).coerceAtLeast(0)
        return y.coerceIn(0, maks)
    }

    /** Tinggi layar dikurangi status bar dan navigation bar, sesuai orientasi saat ini. */
    private fun tinggiAreaAman(): Int {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val metrik = windowManager.maximumWindowMetrics
            val bilah = metrik.windowInsets.getInsetsIgnoringVisibility(WindowInsets.Type.systemBars())
            return metrik.bounds.height() - bilah.top - bilah.bottom
        }
        val metrik = DisplayMetrics()
        val layar = getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
        @Suppress("DEPRECATION")
        layar?.getRealMetrics(metrik) ?: metrik.setTo(resources.displayMetrics)
        // Android 10 ke bawah belum punya API resmi untuk tinggi bilah sistem di luar Activity.
        return metrik.heightPixels - dimenSistem("status_bar_height") - dimenSistem("navigation_bar_height")
    }

    // --- Pengambilan layar dan pilih area ---

    private fun ambilLayar() {
        val view = tombol ?: return
        val pengambilAktif = pengambil ?: return
        if (status != Status.SIAP) {
            // Mencegah ketukan ganda: selama layar diambil, area sedang dipilih, atau potongan
            // sedang dikirim, ketukan tidak memicu pengambilan baru.
            Log.d(TAG, "Ketukan diabaikan, status: $status")
            return
        }
        status = Status.MENGAMBIL

        // Tombol dan kartu hasil sebelumnya disingkirkan dulu agar tidak ikut tertangkap. Jeda
        // memberi waktu sistem menggambar ulang layar tanpa keduanya sebelum frame diambil.
        tutupKartu()
        view.visibility = View.INVISIBLE
        handlerUtama.postDelayed({
            pengambilAktif.ambil(::selesaiMengambil)
        }, JEDA_SEMBUNYI_MS)
    }

    private fun selesaiMengambil(bitmap: Bitmap?) {
        if (bitmap == null) {
            Toast.makeText(this, R.string.tangkap_gagal, Toast.LENGTH_SHORT).show()
            kembaliSiap()
            return
        }
        if (tombol == null) {
            // Tombol sudah dilepas saat gambar selesai diproses; hasilnya tidak dipakai.
            bitmap.recycle()
            status = Status.SIAP
            return
        }
        Log.i(TAG, "Tangkapan layar berhasil: ${bitmap.width} x ${bitmap.height}")

        // Tombol tetap tersembunyi selama layar pilih area terbuka.
        val overlay = OverlayPilihArea(
            this,
            windowManager,
            bitmap,
            onBatal = { selesaiMemilih() },
            onPotong = { potongan -> selesaiMemilih(potongan, gagal = potongan == null) },
        )
        if (!overlay.tampilkan()) {
            Toast.makeText(this, R.string.pilih_gagal_dibuka, Toast.LENGTH_SHORT).show()
            kembaliSiap()
            return
        }
        overlayPilih = overlay
        status = Status.MEMILIH
    }

    private fun selesaiMemilih(potongan: Bitmap? = null, gagal: Boolean = false) {
        overlayPilih = null
        if (gagal) Toast.makeText(this, R.string.potong_gagal, Toast.LENGTH_SHORT).show()
        if (potongan == null) {
            kembaliSiap()
            return
        }
        kirim(potongan)
    }

    private fun kembaliSiap() {
        tombol?.visibility = View.VISIBLE
        status = Status.SIAP
    }

    // --- Pengiriman ke server dan kartu status ---

    /**
     * Mengirim potongan ke server sambil menampilkan kartu "sedang menganalisis".
     * [potongan] selalu dibuang (recycle) di sini, termasuk saat dibatalkan atau gagal.
     */
    private fun kirim(potongan: Bitmap) {
        // Kartu memakai salinan kecil, sehingga potongan asli bisa dibuang segera setelah
        // disandikan tanpa ada view yang masih menggambarnya.
        val kecil = KartuAnalisis.buatThumbnail(potongan, resources.getDimensionPixelSize(R.dimen.kartu_thumbnail))
        val kartuBaru = KartuAnalisis(
            this,
            windowManager,
            kecil,
            onBatal = ::batalKirim,
            onTutup = ::tutupKartu,
            onBukaPengaturan = ::bukaPengaturanServer,
        )
        if (!kartuBaru.tampilkan()) {
            potongan.recycle()
            Toast.makeText(this, R.string.kartu_gagal_dibuka, Toast.LENGTH_SHORT).show()
            kembaliSiap()
            return
        }
        kartu = kartuBaru
        // Tombol tampil lagi, tetapi ketukannya diabaikan selama status MENGIRIM.
        tombol?.visibility = View.VISIBLE
        status = Status.MENGIRIM

        val urlServer = PengaturanServer.baca(this)
        val pekerjaan = lingkup.launch {
            try {
                if (urlServer.isBlank()) {
                    kartuBaru.tampilkanGalat(JenisGagal.UrlBelumDiatur)
                    return@launch
                }
                // Penyandian JPEG berat, jadi dipindah ke thread latar (Dispatchers.Default).
                val jpeg = withContext(Dispatchers.Default) { PenyandiJpeg.sandikanLaluBuang(potongan) }
                if (jpeg == null) {
                    Log.w(TAG, "Penyandian JPEG gagal")
                    kartuBaru.tampilkanGalat(R.string.galat_penyandian)
                    return@launch
                }
                Log.i(TAG, "Mengirim JPEG ${jpeg.size} byte ke $urlServer")
                when (val hasil = KlienApi.bersama.analisis(urlServer, jpeg)) {
                    is HasilPanggilan.Berhasil -> {
                        val data = hasil.data
                        Log.i(TAG, "Hasil ${data.idPermintaan}: ${data.tingkat}, ${data.ciri.size} ciri, ${data.durasiMs} ms")
                        kartuBaru.tampilkanHasil(data)
                    }
                    is HasilPanggilan.Gagal -> {
                        Log.w(TAG, "Pengecekan gagal: ${hasil.jenis}")
                        kartuBaru.tampilkanGalat(hasil.jenis)
                    }
                }
            } finally {
                // Hanya membereskan status milik pengecekan ini. Setelah Batal, pengecekan baru
                // bisa sudah dimulai dengan kartu lain sebelum blok ini sempat berjalan.
                if (kartu === kartuBaru) {
                    pekerjaanKirim = null
                    if (status == Status.MENGIRIM) status = Status.SIAP
                }
            }
        }
        // Dipanggil saat pekerjaan benar-benar selesai, termasuk jika dibatalkan sebelum sempat
        // berjalan. Pekerjaan baru dianggap selesai setelah blok withContext di atas selesai,
        // jadi potongan tidak mungkin dibuang saat masih disandikan.
        pekerjaan.invokeOnCompletion { if (!potongan.isRecycled) potongan.recycle() }
        if (pekerjaan.isActive) pekerjaanKirim = pekerjaan
    }

    /** Tombol Batal di kartu menunggu: memutus permintaan HTTP dan menutup kartu. */
    private fun batalKirim() {
        Log.i(TAG, "Pengecekan dibatalkan pengguna")
        pekerjaanKirim?.cancel()
        pekerjaanKirim = null
        tutupKartu()
        kembaliSiap()
    }

    private fun tutupKartu() {
        kartu?.tutup()
        kartu = null
    }

    private fun bukaPengaturanServer() {
        tutupKartu()
        // Aplikasi yang punya izin tampil di atas aplikasi lain boleh membuka Activity dari service.
        try {
            startActivity(MainActivity.intentPengaturanServer(this).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: RuntimeException) {
            Log.w(TAG, "Gagal membuka pengaturan server", e)
        }
    }

    // --- Notifikasi ---

    private fun buatChannelNotifikasi() {
        val channel = NotificationChannel(
            ID_CHANNEL,
            getString(R.string.notif_channel_nama),
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.notif_channel_deskripsi)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun buatNotifikasi(): Notification {
        // PendingIntent adalah "titipan" Intent yang dijalankan sistem saat notifikasi diketuk.
        val bukaAplikasi = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val matikan = PendingIntent.getService(
            this,
            1,
            Intent(this, FloatingButtonService::class.java).setAction(ACTION_MATIKAN),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        return NotificationCompat.Builder(this, ID_CHANNEL)
            .setSmallIcon(R.drawable.ic_verified_user)
            .setContentTitle(getString(R.string.notif_judul))
            .setContentText(getString(R.string.notif_isi))
            .setContentIntent(bukaAplikasi)
            .addAction(R.drawable.ic_verified_user, getString(R.string.notif_aksi_matikan), matikan)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }

    private enum class Status { SIAP, MENGAMBIL, MEMILIH, MENGIRIM }

    companion object {
        private const val TAG = "CekHoaks"
        private const val ID_CHANNEL = "tombol_cek"
        private const val ID_NOTIFIKASI = 1
        private const val ACTION_MATIKAN = "com.example.cekhoaks.action.MATIKAN_TOMBOL_CEK"
        private const val EXTRA_KODE_HASIL = "com.example.cekhoaks.extra.KODE_HASIL"
        private const val EXTRA_DATA_HASIL = "com.example.cekhoaks.extra.DATA_HASIL"
        private const val POSISI_VERTIKAL = 0.4f
        private const val JEDA_SEMBUNYI_MS = 150L

        private val _berjalan = MutableStateFlow(false)

        /** Bernilai true selama tombol cek sedang terpasang di layar. */
        val berjalan: StateFlow<Boolean> = _berjalan.asStateFlow()

        /**
         * Intent untuk memulai service dengan hasil dialog izin rekam layar.
         * Hasil izin hanya berlaku untuk satu sesi dan tidak boleh dipakai ulang.
         */
        fun buatIntentMulai(context: Context, kodeHasil: Int, dataHasil: Intent): Intent =
            Intent(context, FloatingButtonService::class.java)
                .putExtra(EXTRA_KODE_HASIL, kodeHasil)
                .putExtra(EXTRA_DATA_HASIL, dataHasil)
    }
}
