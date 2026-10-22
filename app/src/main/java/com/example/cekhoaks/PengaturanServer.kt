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
     * Merapikan alamat yang diketik pengguna menjadi bentuk baku "skema://host[:port]", atau null
     * jika tidak valid. Path, query, dan info login tidak diterima.
     *
     * - Tanpa skema: host lokal (IP privat, 127.0.0.1, localhost) diberi http://, host lain https://.
     * - Port 8000 ditambahkan hanya untuk http:// ke host lokal yang tidak menyebut port.
     * - Port yang ditulis pengguna dibiarkan, termasuk port bawaan seperti :80.
     */
    fun normalisasiUrl(masukan: String): String? {
        val dipangkas = masukan.trim()
        // Skema dicek sebelum garis miring akhir dibuang, supaya "http://" tidak terbaca sebagai host "http".
        val adaSkema = "://" in dipangkas
        val bersih = dipangkas.trimEnd('/')
        if (bersih.isEmpty() || bersih.any { it.isWhitespace() } || (adaSkema && "://" !in bersih)) return null
        val skemaSementara = if (adaSkema) bersih else "http://$bersih"
        val hostSementara = skemaSementara.toHttpUrlOrNull()?.host ?: return null
        val denganSkema = when {
            adaSkema -> bersih
            hostLokal(hostSementara) -> "http://$bersih"
            else -> "https://$bersih"
        }
        val url = denganSkema.toHttpUrlOrNull() ?: return null
        val tanpaTambahan = url.encodedPath == "/" && url.query == null && url.fragment == null &&
            url.username.isEmpty() && url.password.isEmpty()
        if (!tanpaTambahan) return null

        // HttpUrl mengisi port bawaan (80/443) jika port tidak ditulis, jadi dicek dari teks aslinya.
        val otoritas = denganSkema.substringAfter("://").substringBefore('/')
        val portDitulis = Regex(""":[0-9]+$""").containsMatchIn(otoritas)
        val host = if (':' in url.host) "[${url.host}]" else url.host
        return when {
            portDitulis -> "${url.scheme}://$host:${url.port}"
            url.scheme == "http" && hostLokal(url.host) -> "http://$host:$PORT_LOKAL"
            else -> "${url.scheme}://$host"
        }
    }

    private const val PORT_LOKAL = 8000

    /** True untuk 127.0.0.1, localhost, dan IPv4 privat (10.x, 172.16-31.x, 192.168.x). */
    private fun hostLokal(host: String): Boolean {
        if (host == "localhost" || host == "127.0.0.1") return true
        val oktet = host.split('.').map { it.toIntOrNull() ?: return false }
        if (oktet.size != 4 || oktet.any { it !in 0..255 }) return false
        return oktet[0] == 10 ||
            (oktet[0] == 172 && oktet[1] in 16..31) ||
            (oktet[0] == 192 && oktet[1] == 168)
    }
}
