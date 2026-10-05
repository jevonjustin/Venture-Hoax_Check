package com.example.cekhoaks

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.util.Log
import android.view.ContextThemeWrapper
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import androidx.annotation.StringRes
import androidx.core.content.ContextCompat
import androidx.core.graphics.scale
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Kartu kecil di bagian atas layar selama dan setelah pengecekan, dengan tiga keadaan:
 * menunggu (tombol Batal), hasil sementara, dan galat (tombol Tutup, kadang "Buka pengaturan").
 *
 * Kartu memegang Bitmap thumbnail miliknya sendiri, terpisah dari potongan yang dikirim,
 * dan membuangnya (recycle) saat ditutup. Setiap objek hanya dipakai untuk satu pengecekan.
 */
class KartuAnalisis(
    context: Context,
    private val windowManager: WindowManager,
    private val thumbnail: Bitmap?,
    private val onBatal: () -> Unit,
    private val onTutup: () -> Unit,
    private val onBukaPengaturan: () -> Unit,
) {
    private val context = ContextThemeWrapper(context, R.style.Theme_CekHoaks)
    private var akar: View? = null
    private var menunggu = true
    private var ditutup = false

    /** Memasang kartu dalam keadaan menunggu. Jika gagal, thumbnail langsung dibuang dan hasilnya false. */
    // InflateParams: jendela overlay tidak punya view induk; ukurannya diatur lewat LayoutParams jendela.
    @SuppressLint("InflateParams")
    fun tampilkan(): Boolean {
        val view = LayoutInflater.from(context).inflate(R.layout.overlay_kartu_analisis, null)
        // Memotong isi kartu dan thumbnail mengikuti sudut membulat dari latarnya.
        view.findViewById<View>(R.id.kartu).clipToOutline = true
        view.findViewById<View>(R.id.kartu_bingkai_thumbnail).clipToOutline = true
        view.findViewById<ImageView>(R.id.kartu_thumbnail).setImageBitmap(thumbnail)
        view.findViewById<Button>(R.id.kartu_tombol_utama).setOnClickListener {
            if (menunggu) onBatal() else onTutup()
        }
        view.findViewById<Button>(R.id.kartu_tombol_pengaturan).setOnClickListener { onBukaPengaturan() }

        try {
            windowManager.addView(view, buatLayoutParams())
        } catch (e: RuntimeException) {
            Log.e(TAG, "Gagal memasang kartu status", e)
            ditutup = true
            thumbnail?.recycle()
            return false
        }
        akar = view
        aturMenunggu()
        view.alpha = 0f
        view.animate().alpha(1f).setDuration(DURASI_MUNCUL_MS)
        return true
    }

    fun tampilkanHasil(hasil: HasilAnalisis) {
        val (judul, warna) = when (hasil.tingkat) {
            Tingkat.KUAT -> R.string.hasil_tingkat_kuat to R.color.tingkat_kuat
            Tingkat.HATI_HATI -> R.string.hasil_tingkat_hati_hati to R.color.tingkat_hati_hati
            Tingkat.TIDAK_DITEMUKAN -> R.string.hasil_tingkat_tidak_ditemukan to R.color.utama
        }
        val isi = if (hasil.ciri.isEmpty()) {
            context.getString(R.string.hasil_tanpa_ciri)
        } else {
            context.getString(R.string.hasil_jumlah_ciri, hasil.ciri.size)
        }
        aturSelesai(context.getString(judul), warna, isi, tampilkanPengaturan = false)
    }

    fun tampilkanGalat(jenis: JenisGagal) =
        tampilkanGalat(jenis.pesan(), jenis.perluPengaturan)

    fun tampilkanGalat(@StringRes pesan: Int, tampilkanPengaturan: Boolean = false) {
        aturSelesai(
            context.getString(R.string.galat_judul),
            R.color.teks_utama,
            context.getString(pesan),
            tampilkanPengaturan,
        )
    }

    /** Melepas jendela dan membuang thumbnail. Aman dipanggil lebih dari sekali. */
    fun tutup() {
        if (ditutup) return
        ditutup = true
        val view = akar
        akar = null
        if (view != null) {
            try {
                // Dilepas seketika agar thumbnail yang dibuang di bawah tidak sempat digambar lagi.
                windowManager.removeViewImmediate(view)
            } catch (e: IllegalArgumentException) {
                Log.w(TAG, "Kartu status sudah tidak terpasang", e)
            }
            view.findViewById<ImageView>(R.id.kartu_thumbnail).setImageDrawable(null)
        }
        thumbnail?.recycle()
    }

    private fun aturMenunggu() {
        val view = akar ?: return
        menunggu = true
        view.findViewById<TextView>(R.id.kartu_judul).apply {
            setText(R.string.kartu_menunggu_judul)
            setTextColor(ContextCompat.getColor(context, R.color.teks_utama))
        }
        view.findViewById<TextView>(R.id.kartu_isi).setText(R.string.kartu_menunggu_isi)
        view.findViewById<Button>(R.id.kartu_tombol_utama).apply {
            setText(R.string.kartu_batal)
            contentDescription = context.getString(R.string.kartu_batal_deskripsi)
        }
        aturTampil(view, R.id.kartu_redup, true)
        aturTampil(view, R.id.kartu_putar, true)
        aturTampil(view, R.id.kartu_pemisah_tombol, false)
        aturTampil(view, R.id.kartu_tombol_pengaturan, false)
    }

    private fun aturSelesai(judul: String, warnaJudul: Int, isi: String, tampilkanPengaturan: Boolean) {
        val view = akar ?: return
        menunggu = false
        view.findViewById<TextView>(R.id.kartu_judul).apply {
            text = judul
            setTextColor(ContextCompat.getColor(context, warnaJudul))
        }
        view.findViewById<TextView>(R.id.kartu_isi).text = isi
        view.findViewById<Button>(R.id.kartu_tombol_utama).apply {
            setText(R.string.kartu_tutup)
            contentDescription = null
        }
        aturTampil(view, R.id.kartu_redup, false)
        aturTampil(view, R.id.kartu_putar, false)
        aturTampil(view, R.id.kartu_pemisah_tombol, tampilkanPengaturan)
        aturTampil(view, R.id.kartu_tombol_pengaturan, tampilkanPengaturan)
    }

    private fun aturTampil(akar: View, id: Int, tampil: Boolean) {
        akar.findViewById<View>(id).visibility = if (tampil) View.VISIBLE else View.GONE
    }

    private fun buatLayoutParams() = WindowManager.LayoutParams(
        WindowManager.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.WRAP_CONTENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        // NOT_FOCUSABLE: keyboard dan tombol Back tetap milik aplikasi di bawahnya, dan sentuhan
        // di luar jendela kartu diteruskan ke aplikasi itu.
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
        PixelFormat.TRANSLUCENT,
    ).apply {
        gravity = Gravity.TOP
        // Jendela overlay ditata di bawah status bar, jadi y dihitung dari tepi bawah status bar.
        y = context.resources.getDimensionPixelSize(R.dimen.kartu_jarak_atas) -
            context.resources.getDimensionPixelSize(R.dimen.kartu_ruang_bayangan)
    }

    companion object {
        private const val TAG = "CekHoaks"
        private const val DURASI_MUNCUL_MS = 150L

        /**
         * Salinan kecil potongan untuk thumbnail, dengan sisi terpendek sebesar [ukuranPx]
         * (cukup untuk centerCrop). Selalu berupa Bitmap baru, supaya potongan asli boleh
         * dibuang tanpa memengaruhi kartu. Hasilnya null jika memori tidak cukup.
         */
        fun buatThumbnail(potongan: Bitmap, ukuranPx: Int): Bitmap? = try {
            val skala = ukuranPx.toFloat() / min(potongan.width, potongan.height)
            if (skala >= 1f) {
                potongan.copy(Bitmap.Config.ARGB_8888, false)
            } else {
                potongan.scale(
                    (potongan.width * skala).roundToInt().coerceAtLeast(1),
                    (potongan.height * skala).roundToInt().coerceAtLeast(1),
                )
            }
        } catch (e: OutOfMemoryError) {
            Log.w(TAG, "Memori tidak cukup untuk thumbnail", e)
            null
        }
    }
}
