package com.example.cekhoaks

import android.content.Context
import androidx.core.content.edit
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/** Alamat server analisis, disimpan di SharedPreferences (penyimpanan kecil key-value milik aplikasi). */
object PengaturanServer {

    /** Alamat untuk koneksi USB setelah `adb reverse tcp:8000 tcp:8000`. */
    const val URL_USB = "http://127.0.0.1:8000"

    private const val NAMA_PREFS = "pengaturan_server"
    private const val KUNCI_URL = "url"

    /** Alamat tersimpan, atau string kosong jika belum diatur. */
    fun baca(context: Context): String =
        context.getSharedPreferences(NAMA_PREFS, Context.MODE_PRIVATE).getString(KUNCI_URL, "").orEmpty()

    fun simpan(context: Context, url: String) {
        context.getSharedPreferences(NAMA_PREFS, Context.MODE_PRIVATE).edit { putString(KUNCI_URL, url) }
    }

    /**
     * Merapikan alamat yang diketik pengguna menjadi bentuk baku "http://host:port", atau null
     * jika tidak valid. Tanpa skema, dianggap http://. Path, query, dan info login tidak diterima.
     */
    fun normalisasiUrl(masukan: String): String? {
        val bersih = masukan.trim()
        if (bersih.isEmpty() || bersih.any { it.isWhitespace() }) return null
        val denganSkema = if ("://" in bersih) bersih else "http://$bersih"
        val url = denganSkema.toHttpUrlOrNull() ?: return null
        val tanpaTambahan = url.encodedPath == "/" && url.query == null && url.fragment == null &&
            url.username.isEmpty() && url.password.isEmpty()
        if (!tanpaTambahan) return null
        return url.toString().removeSuffix("/")
    }
}
