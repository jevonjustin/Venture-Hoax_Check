package com.example.cekhoaks

import android.content.Context
import android.util.Log
import android.view.ContextThemeWrapper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import androidx.annotation.DrawableRes
import androidx.annotation.LayoutRes
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.doOnPreDraw

/** Lembar atau kartu overlay yang bisa ditutup dari luar (misalnya saat service dimatikan). */
interface LembarOverlay {
    /** Melepas jendela dan membuang sumber daya milik lembar. Aman dipanggil lebih dari sekali. */
    fun tutup()
}

/**
 * Jendela overlay layar penuh dengan lapisan gelap, tempat sebuah lembar atau kartu dipasang.
 * Back dan ketukan di lapisan gelap memanggil [onKembali]. Jendela ini fokusable (tanpa
 * FLAG_NOT_FOCUSABLE) supaya Back sampai ke sini, dan lembar dijauhkan dari navigation bar.
 *
 * Satu objek dipakai untuk satu lembar.
 */
internal class JendelaLembar(
    context: Context,
    private val windowManager: WindowManager,
    deskripsiLapisan: String?,
    onKembali: () -> Unit,
) {
    // Service tidak punya tema tampilan seperti Activity, jadi tema aplikasi dipasang manual.
    val context = ContextThemeWrapper(context, R.style.Theme_CekHoaks)
    val akar = AkarOverlay(this.context, onKembali).apply {
        setBackgroundColor(ContextCompat.getColor(this@JendelaLembar.context, R.color.lapisan_lembar))
        // Ketukan di luar lembar (di lapisan gelap) sama dengan Back. Lembarnya sendiri clickable
        // sehingga ketukan di dalamnya tidak sampai ke sini.
        isClickable = true
        setOnClickListener { onKembali() }
        contentDescription = deskripsiLapisan
    }
    private var terpasang = false

    /** Membuat lembar dari kerangka bersama: pegangan, area gulir ([isi]), dan kaki tetap ([kaki]). */
    fun buatKerangka(@DrawableRes latar: Int, @LayoutRes isi: Int, @LayoutRes kaki: Int): View {
        val inflater = LayoutInflater.from(context)
        val kerangka = inflater.inflate(R.layout.overlay_lembar_kerangka, akar, false)
        kerangka.setBackgroundResource(latar)
        inflater.inflate(isi, kerangka.findViewById<ViewGroup>(R.id.lembar_isi), true)
        inflater.inflate(kaki, kerangka.findViewById<ViewGroup>(R.id.lembar_kaki), true)
        return kerangka
    }

    /** Memasang [isi] di dalam jendela. Hasilnya false bila sistem menolak (misalnya izin dicabut). */
    fun pasang(isi: View): Boolean {
        akar.addView(isi)
        aturJarak()
        try {
            windowManager.addView(akar, buatParamsLayarPenuh())
        } catch (e: RuntimeException) {
            Log.e(TAG, "Gagal memasang lembar", e)
            akar.removeAllViews()
            return false
        }
        terpasang = true
        // Keadaan akhir (terlihat penuh) tidak boleh bergantung pada animasi: postDelayed memaksanya
        // walau animasi tidak jalan, dibatalkan, atau skala animasi sistem 0. Animasi dimulai pada
        // frame pertama jendela karena sebelum itu view belum terpasang.
        val tampilPenuh = Runnable {
            akar.animate().cancel()
            akar.alpha = 1f
        }
        akar.alpha = 0f
        akar.doOnPreDraw { akar.animate().alpha(1f).setDuration(DURASI_MUNCUL_MS).withEndAction(tampilPenuh) }
        akar.postDelayed(tampilPenuh, DURASI_MUNCUL_MS * 3)
        return true
    }

    /** Melepas jendela seketika, supaya Bitmap yang dibuang sesudahnya tidak sempat digambar lagi. */
    fun lepas() {
        if (!terpasang) return
        terpasang = false
        akar.animate().cancel()
        try {
            windowManager.removeViewImmediate(akar)
        } catch (e: IllegalArgumentException) {
            Log.w(TAG, "Lembar sudah tidak terpasang", e)
        }
    }

    /** Menjauhkan lembar dari navigation bar dan cutout; insets = bagian layar yang tertutup elemen sistem. */
    private fun aturJarak() {
        ViewCompat.setOnApplyWindowInsetsListener(akar) { view, insets ->
            val bilah = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            // Sebagian HP tidak mengirim insets ke jendela overlay. Kalau semuanya 0, dipakai
            // tinggi navigation bar dari resource sistem sebagai cadangan.
            val tanpaInsets = bilah.left == 0 && bilah.top == 0 && bilah.right == 0 && bilah.bottom == 0
            val bawah = if (tanpaInsets) context.dimenSistem("navigation_bar_height") else bilah.bottom
            view.setPadding(bilah.left, bilah.top, bilah.right, bawah)
            insets
        }
    }

    private companion object {
        const val TAG = "CekHoaks"
        const val DURASI_MUNCUL_MS = 150L
    }
}
