package com.example.cekhoaks

import android.graphics.Bitmap
import androidx.core.graphics.scale
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.roundToInt

/** Mengubah potongan layar menjadi JPEG di memori, tanpa menulis apa pun ke disk. */
object PenyandiJpeg {

    const val SISI_MAKS_PX = 2000
    const val KUALITAS = 90

    /**
     * Ukuran setelah diperkecil secara proporsional agar sisi terpanjang tidak melebihi [sisiMaks].
     * Gambar yang sudah cukup kecil tidak diubah. Hasilnya minimal 1 x 1 piksel.
     */
    fun ukuranTarget(lebar: Int, tinggi: Int, sisiMaks: Int = SISI_MAKS_PX): Pair<Int, Int> {
        val terpanjang = max(lebar, tinggi)
        if (terpanjang <= sisiMaks) return lebar to tinggi
        val skala = sisiMaks.toDouble() / terpanjang
        return max(1, (lebar * skala).roundToInt()) to max(1, (tinggi * skala).roundToInt())
    }

    /**
     * Menyandikan [bitmap] menjadi JPEG, lalu SELALU membuang (recycle) [bitmap], baik berhasil
     * maupun gagal. Pemanggil tidak boleh memakai [bitmap] lagi. Hasilnya null jika gagal.
     * Jalankan di luar main thread karena proses ini berat untuk gambar besar.
     */
    fun sandikanLaluBuang(bitmap: Bitmap): ByteArray? {
        var kecil: Bitmap? = null
        try {
            val (lebar, tinggi) = ukuranTarget(bitmap.width, bitmap.height)
            val sumber = if (lebar == bitmap.width && tinggi == bitmap.height) {
                bitmap
            } else {
                bitmap.scale(lebar, tinggi).also { kecil = it }
            }
            val keluaran = ByteArrayOutputStream()
            if (!sumber.compress(Bitmap.CompressFormat.JPEG, KUALITAS, keluaran)) return null
            return keluaran.toByteArray()
        } catch (_: OutOfMemoryError) {
            return null
        } finally {
            kecil?.takeIf { it !== bitmap }?.recycle()
            bitmap.recycle()
        }
    }
}
