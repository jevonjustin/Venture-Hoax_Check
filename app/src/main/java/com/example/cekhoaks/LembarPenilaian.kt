package com.example.cekhoaks

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageView
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import androidx.annotation.StringRes
import androidx.core.content.ContextCompat
import androidx.core.graphics.scale
import androidx.core.widget.ImageViewCompat
import kotlin.math.min
import kotlin.math.roundToInt

/** Keadaan analisis yang ditampilkan pada pil status di lembar penilaian. */
enum class StatusAnalisis { BERJALAN, SELESAI, TERKENDALA }

/**
 * Lembar penilaian awal: tampil segera setelah "Cek Sekarang" selagi analisis berjalan di latar.
 * Pengguna memilih Percaya, Ragu-ragu, atau Tidak percaya lalu "Lihat Hasil", atau "Lewati".
 * Back dan ketukan di lapisan gelap membatalkan pengecekan ([onBatal]).
 *
 * Lembar memegang Bitmap thumbnail miliknya sendiri, terpisah dari potongan yang dikirim, dan
 * membuangnya (recycle) saat ditutup. Setiap objek hanya dipakai untuk satu pengecekan.
 *
 * @param onPilih dipanggil dengan penilaian pengguna, atau [Penilaian.DILEWATI] untuk "Lewati".
 *   Lembar tidak menutup dirinya; pemilik memanggil [tutup] sesudahnya.
 * @param onBatal dipanggil saat Back atau lapisan gelap diketuk.
 */
class LembarPenilaian(
    context: Context,
    windowManager: WindowManager,
    private val thumbnail: Bitmap?,
    private val onPilih: (Penilaian) -> Unit,
    private val onBatal: () -> Unit,
) : LembarOverlay {

    private val jendela = JendelaLembar(
        context,
        windowManager,
        context.getString(R.string.penilaian_tutup_deskripsi),
        onKembali = { batal() },
    )
    private var kerangka: View? = null
    private var ditutup = false
    private var sudahMemilih = false
    private var penilaianTerpilih: Penilaian? = null

    /** Memasang lembar. Jika gagal, thumbnail langsung dibuang dan hasilnya false. */
    fun tampilkan(): Boolean {
        val view = jendela.buatKerangka(
            R.drawable.bg_lembar_putih,
            R.layout.overlay_lembar_penilaian_isi,
            R.layout.overlay_lembar_penilaian_kaki,
        )
        val gambar = view.findViewById<ImageView>(R.id.penilaian_thumbnail)
        if (thumbnail != null) {
            view.findViewById<View>(R.id.penilaian_bingkai).clipToOutline = true
            gambar.setImageBitmap(thumbnail)
        } else {
            view.findViewById<View>(R.id.penilaian_bingkai).visibility = View.GONE
        }

        val tombolLihat = view.findViewById<Button>(R.id.penilaian_lihat_hasil)
        view.findViewById<RadioGroup>(R.id.penilaian_opsi).setOnCheckedChangeListener { _, id ->
            penilaianTerpilih = when (id) {
                R.id.penilaian_opsi_percaya -> Penilaian.PERCAYA
                R.id.penilaian_opsi_ragu -> Penilaian.RAGU
                R.id.penilaian_opsi_tidak_percaya -> Penilaian.TIDAK_PERCAYA
                else -> null
            }
            tombolLihat.isEnabled = penilaianTerpilih != null
            tombolLihat.setTextColor(
                ContextCompat.getColor(
                    jendela.context,
                    if (tombolLihat.isEnabled) R.color.white else R.color.tombol_nonaktif_teks,
                ),
            )
        }
        tombolLihat.setOnClickListener { penilaianTerpilih?.let(::pilih) }
        view.findViewById<Button>(R.id.penilaian_lewati).setOnClickListener { pilih(Penilaian.DILEWATI) }

        if (!jendela.pasang(view)) {
            ditutup = true
            thumbnail?.recycle()
            return false
        }
        kerangka = view
        aturStatus(StatusAnalisis.BERJALAN)
        return true
    }

    /** Memperbarui pil status. Tidak berpengaruh bila lembar sudah ditutup. */
    fun aturStatus(status: StatusAnalisis) {
        val view = kerangka ?: return
        val putar = view.findViewById<ProgressBar>(R.id.penilaian_putar)
        val ikon = view.findViewById<ImageView>(R.id.penilaian_ikon)
        val teks = view.findViewById<TextView>(R.id.penilaian_status)
        @StringRes val label: Int
        when (status) {
            StatusAnalisis.BERJALAN -> {
                label = R.string.penilaian_status_berjalan
                putar.visibility = View.VISIBLE
                ikon.visibility = View.GONE
            }
            StatusAnalisis.SELESAI -> {
                label = R.string.penilaian_status_selesai
                tampilkanIkon(ikon, R.drawable.ic_centang, putar)
            }
            StatusAnalisis.TERKENDALA -> {
                label = R.string.penilaian_status_terkendala
                tampilkanIkon(ikon, R.drawable.ic_seru_kecil, putar)
            }
        }
        teks.setText(label)
    }

    private fun tampilkanIkon(ikon: ImageView, drawable: Int, putar: View) {
        putar.visibility = View.GONE
        ikon.setImageResource(drawable)
        ImageViewCompat.setImageTintList(
            ikon,
            ColorStateList.valueOf(ContextCompat.getColor(jendela.context, R.color.tingkat_tidak_ditemukan_ink)),
        )
        ikon.visibility = View.VISIBLE
    }

    private fun pilih(penilaian: Penilaian) {
        if (ditutup || sudahMemilih) return
        sudahMemilih = true
        onPilih(penilaian)
    }

    private fun batal() {
        if (ditutup || sudahMemilih) return
        onBatal()
    }

    /** Melepas jendela dan membuang thumbnail. Aman dipanggil lebih dari sekali. */
    override fun tutup() {
        if (ditutup) return
        ditutup = true
        // Dilepas seketika agar thumbnail yang dibuang di bawah tidak sempat digambar lagi.
        jendela.lepas()
        kerangka?.findViewById<ImageView>(R.id.penilaian_thumbnail)?.setImageDrawable(null)
        kerangka = null
        thumbnail?.recycle()
    }

    companion object {
        private const val TAG = "CekHoaks"

        /**
         * Salinan kecil potongan untuk thumbnail, dengan sisi terpendek sebesar [ukuranPx].
         * Selalu berupa Bitmap baru, supaya potongan asli boleh dibuang tanpa memengaruhi lembar.
         * Hasilnya null jika memori tidak cukup.
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
