package com.example.cekhoaks

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.ContextThemeWrapper
import android.view.Display
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.doOnPreDraw

/**
 * Jendela layar penuh tempat pengguna memilih bagian layar yang ingin dicek.
 *
 * Objek ini memegang Bitmap layar penuh sejak dibuat dan selalu membuangnya (recycle) saat
 * selesai, baik lewat Batal, Back, rotasi layar, maupun Cek Sekarang. Setiap objek hanya
 * dipakai untuk satu kali pemilihan.
 *
 * @param onBatal dipanggil saat pengguna membatalkan (tombol Batal, tombol Back, atau layar diputar).
 * @param onPotong dipanggil dengan Bitmap potongan, atau null jika pemotongan gagal.
 */
class OverlayPilihArea(
    context: Context,
    private val windowManager: WindowManager,
    private val layarPenuh: Bitmap,
    private val onBatal: () -> Unit,
    private val onPotong: (Bitmap?) -> Unit,
) {

    // Service tidak punya tema tampilan seperti Activity, jadi tema aplikasi dipasang manual
    // agar tombol dan teks di panel tampil konsisten.
    private val context = ContextThemeWrapper(context, R.style.Theme_CekHoaks)
    private val displayManager = context.getSystemService(DisplayManager::class.java)
    private val rotasiAwal = rotasiLayar()

    private var akar: AkarOverlay? = null
    private var tampilanSeleksi: CropSelectionView? = null
    private var panel: View? = null
    private var selesai = false

    // Layar diputar 180 derajat tidak memicu onConfigurationChanged, jadi rotasi dipantau
    // langsung dari DisplayManager.
    private val pemantauLayar = object : DisplayManager.DisplayListener {
        override fun onDisplayChanged(displayId: Int) {
            if (displayId == Display.DEFAULT_DISPLAY && rotasiLayar() != rotasiAwal) {
                Log.i(TAG, "Layar diputar saat memilih area, pemilihan dibatalkan")
                batal()
            }
        }
        override fun onDisplayAdded(displayId: Int) = Unit
        override fun onDisplayRemoved(displayId: Int) = Unit
    }

    /** Memasang jendela. Jika gagal, Bitmap layar penuh langsung dibuang dan hasilnya false. */
    fun tampilkan(): Boolean {
        val akarBaru = AkarOverlay(context, onKembali = ::batal)
        val seleksi = CropSelectionView(context, layarPenuh, onInteraksi = ::aturPanel)
        akarBaru.addView(seleksi, FrameLayout.LayoutParams(MATCH, MATCH))

        val panelBaru = LayoutInflater.from(context).inflate(R.layout.overlay_pilih_area_panel, akarBaru, false)
        akarBaru.addView(panelBaru)
        panelBaru.findViewById<View>(R.id.pilih_batal).setOnClickListener { batal() }
        panelBaru.findViewById<View>(R.id.pilih_cek).setOnClickListener { cek() }
        panelBaru.findViewById<View>(R.id.pilih_seluruh_layar).setOnClickListener { seleksi.pilihSeluruhLayar() }
        aturJarakPanel(akarBaru, panelBaru)

        // Kilatan putih singkat sebagai tanda layar sudah diambil.
        val kilatan = View(context).apply {
            setBackgroundColor(Color.WHITE)
            alpha = ALPHA_KILATAN
        }
        akarBaru.addView(kilatan, FrameLayout.LayoutParams(MATCH, MATCH))

        try {
            windowManager.addView(akarBaru, buatParamsLayarPenuh())
        } catch (e: RuntimeException) {
            Log.e(TAG, "Gagal memasang layar pilih area", e)
            selesai = true
            layarPenuh.recycle()
            return false
        }
        akar = akarBaru
        tampilanSeleksi = seleksi
        panel = panelBaru
        displayManager.registerDisplayListener(pemantauLayar, Handler(Looper.getMainLooper()))

        // Panel langsung tampil penuh di bawah kilatan; hanya kilatan yang dianimasikan. Keadaan
        // akhir (kilatan hilang) tidak bergantung pada animasi: postDelayed di bawah memaksanya
        // walau animasi tidak jalan, dibatalkan, atau skala animasi sistem 0. Animasi dimulai
        // pada frame pertama jendela karena sebelum itu view belum terpasang.
        val hilangkanKilatan = Runnable {
            kilatan.animate().cancel()
            kilatan.alpha = 0f
            kilatan.visibility = View.GONE
        }
        akarBaru.doOnPreDraw {
            kilatan.animate().alpha(0f).setDuration(DURASI_ANIMASI_MS).withEndAction(hilangkanKilatan)
        }
        akarBaru.postDelayed(hilangkanKilatan, DURASI_ANIMASI_MS * 3)
        return true
    }

    /**
     * Menutup jendela dan membuang Bitmap layar penuh tanpa memanggil callback, misalnya saat
     * service dimatikan. Aman dipanggil lebih dari sekali.
     */
    fun tutup() {
        if (selesai) return
        selesai = true
        lepasJendela()
        layarPenuh.recycle()
    }

    private fun batal() {
        if (selesai) return
        tutup()
        onBatal()
    }

    private fun cek() {
        if (selesai) return
        val seleksi = tampilanSeleksi ?: return
        val piksel = seleksi.seleksiDalamPiksel()
        val potongan = try {
            Bitmap.createBitmap(layarPenuh, piksel.x, piksel.y, piksel.lebar, piksel.tinggi)
        } catch (e: IllegalArgumentException) {
            Log.e(TAG, "Area potongan tidak valid: $piksel", e)
            null
        } catch (e: OutOfMemoryError) {
            Log.e(TAG, "Memori tidak cukup untuk memotong layar", e)
            null
        }

        selesai = true
        lepasJendela()
        // Jika seluruh layar dipilih, createBitmap boleh mengembalikan objek yang sama dengan
        // sumbernya. Dalam kasus itu Bitmap tidak boleh dibuang karena justru itulah hasilnya.
        if (potongan !== layarPenuh) layarPenuh.recycle()
        Log.i(TAG, "Potongan: ${piksel.lebar} x ${piksel.tinggi} dari (${piksel.x}, ${piksel.y})")
        onPotong(potongan)
    }

    private fun lepasJendela() {
        displayManager.unregisterDisplayListener(pemantauLayar)
        val view = akar ?: return
        try {
            // Versi "Immediate" melepas jendela saat itu juga, sehingga Bitmap yang dibuang
            // sesudahnya tidak sempat digambar lagi.
            windowManager.removeViewImmediate(view)
        } catch (e: IllegalArgumentException) {
            Log.w(TAG, "Layar pilih area sudah tidak terpasang", e)
        } finally {
            akar = null
            tampilanSeleksi = null
            panel = null
        }
    }

    /** Panel memudar saat jari sedang mengatur kotak, agar tidak menutupi bagian bawah layar. */
    private fun aturPanel(sedangDiatur: Boolean) {
        val view = panel ?: return
        view.animate().cancel()
        view.animate().alpha(if (sedangDiatur) 0f else 1f).setStartDelay(0).setDuration(DURASI_ANIMASI_MS)
    }

    /**
     * Menjauhkan panel dari navigation bar dan cutout. Insets adalah ukuran bagian layar yang
     * tertutup elemen sistem; WindowInsetsCompat menyamakan cara membacanya di semua versi Android.
     */
    private fun aturJarakPanel(akar: View, panel: View) {
        val jarakSamping = context.resources.getDimensionPixelSize(R.dimen.pilih_panel_jarak_samping)
        val jarakBawah = context.resources.getDimensionPixelSize(R.dimen.pilih_panel_jarak_bawah)
        ViewCompat.setOnApplyWindowInsetsListener(akar) { _, insets ->
            val bilah = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            // Sebagian HP tidak mengirim insets ke jendela overlay. Kalau semuanya 0, dipakai
            // tinggi navigation bar dari resource sistem sebagai cadangan.
            val tanpaInsets = bilah.left == 0 && bilah.top == 0 && bilah.right == 0 && bilah.bottom == 0
            val bawah = if (tanpaInsets) context.dimenSistem("navigation_bar_height") else bilah.bottom
            panel.setPadding(jarakSamping + bilah.left, panel.paddingTop, jarakSamping + bilah.right, jarakBawah + bawah)
            insets
        }
    }

    private fun rotasiLayar(): Int = displayManager.getDisplay(Display.DEFAULT_DISPLAY)?.rotation ?: 0

    companion object {
        private const val TAG = "CekHoaks"
        private const val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
        private const val ALPHA_KILATAN = 0.85f
        private const val DURASI_ANIMASI_MS = 150L
    }
}
