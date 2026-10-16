package com.example.cekhoaks

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.graphics.createBitmap
import androidx.core.net.toUri
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * Hanya di build debug: menampilkan lembar hasil/galat dari berkas fixture tanpa server.
 *
 * Contoh lewat adb:
 * `adb shell am start -n com.example.cekhoaks/.AktivitasFixture --es fixture kuat
 *   [--es penilaian percaya|ragu|tidak_percaya|dilewati] [--es mode hasil|penilaian|memuat]`
 * Tanpa extra, tampil daftar tombol berisi semua fixture.
 */
class AktivitasFixture : Activity() {

    private lateinit var daftar: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        bangunDaftar()
        tanganiIntent(intent)
    }

    // singleTask: am start berikutnya masuk ke sini, bukan membuat instance baru.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        tanganiIntent(intent)
    }

    override fun onDestroy() {
        // Overlay memakai konteks aplikasi, jadi harus ditutup manual agar tidak bocor.
        tutupSemua()
        super.onDestroy()
    }

    private fun tanganiIntent(intent: Intent) {
        val nama = intent.getStringExtra("fixture") ?: return
        val penilaian = when (intent.getStringExtra("penilaian")) {
            "percaya" -> Penilaian.PERCAYA
            "ragu" -> Penilaian.RAGU
            "tidak_percaya" -> Penilaian.TIDAK_PERCAYA
            else -> Penilaian.DILEWATI
        }
        tampilkan(nama, penilaian, intent.getStringExtra("mode") ?: "hasil")
    }

    private fun bangunDaftar() {
        val dp = resources.displayMetrics.density
        fun px(nilai: Int) = (nilai * dp).toInt()
        daftar = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(px(16), px(16), px(16), px(16))
        }
        daftar.addView(TextView(this).apply {
            setText(R.string.fixture_petunjuk)
            textSize = 16f
            setTextColor(Color.BLACK)
        })
        namaFixture().forEach { nama ->
            daftar.addView(
                Button(this).apply {
                    text = nama
                    isAllCaps = false
                    minHeight = px(56)
                    setOnClickListener { tampilkan(nama, Penilaian.DILEWATI, "hasil") }
                },
                LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                    .apply { topMargin = px(8) },
            )
        }
        setContentView(ScrollView(this).apply { addView(daftar) })
    }

    private fun namaFixture(): List<String> =
        (assets.list("fixture") ?: emptyArray()).filter { it.endsWith(".json") }
            .map { it.removeSuffix(".json") }.sorted()

    private fun tutupSemua() = PenampilFixture.tutupSemua()

    private fun pesan(teks: String) {
        daftar.addView(TextView(this).apply {
            text = teks
            textSize = 16f
            setTextColor(Color.RED)
        }, 1)
    }

    private fun tampilkan(nama: String, penilaian: Penilaian, mode: String) {
        tutupSemua()
        if (!Settings.canDrawOverlays(this)) {
            pesan(getString(R.string.fixture_izin_belum))
            startActivity(
                Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, "package:$packageName".toUri()),
            )
            return
        }
        val teks = try {
            assets.open("fixture/$nama.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
        } catch (e: java.io.IOException) {
            pesan(getString(R.string.fixture_tidak_ada, nama))
            return
        }
        val ctx = applicationContext
        val wm = ctx.getSystemService(WindowManager::class.java)

        // Isi akhir yang ditampilkan setelah tahap memuat/penilaian (jika ada).
        val tampilAkhir: (Penilaian) -> Unit
        try {
            val jenis = jenisGagalDari(jsonApi.parseToJsonElement(teks).jsonObject)
            if (jenis != null) {
                tampilAkhir = { _ -> tampilkanGalat(ctx, wm, jenis) }
            } else {
                val hasil = jsonApi.decodeFromString(HasilAnalisis.serializer(), teks)
                tampilAkhir = { p -> tampilkanHasil(ctx, wm, hasil, p) }
            }
        } catch (e: Exception) {
            pesan(getString(R.string.fixture_gagal_baca, "$nama (${e.message})"))
            return
        }

        when (mode) {
            "penilaian" -> tampilkanPenilaian(ctx, wm, tampilAkhir)
            "memuat" -> {
                val kartu = KartuMemuat(ctx, wm, onBatal = { tutupSemua() })
                kartu.tampilkan()
                PenampilFixture.daftarkan(kartu)
                PenampilFixture.tunda(2000) {
                    tutupSemua()
                    tampilAkhir(penilaian)
                }
            }
            else -> tampilAkhir(penilaian)
        }
    }

    /** Memetakan fixture galat ke [JenisGagal]; null berarti fixture sukses. */
    private fun jenisGagalDari(obj: JsonObject): JenisGagal? {
        val jenis = obj["_jenis"]?.jsonPrimitive?.contentOrNull
        if (jenis != null) {
            return when (jenis) {
                "tidak_terjangkau" -> JenisGagal.TidakTerjangkau("fixture")
                "waktu_habis" -> JenisGagal.WaktuHabis
                "url_belum_diatur" -> JenisGagal.UrlBelumDiatur
                "respons_tidak_dikenali" -> JenisGagal.ResponsTidakDikenali
                "cleartext" -> JenisGagal.CleartextDiblokir
                else -> error("_jenis tidak dikenal: $jenis")
            }
        }
        val galat = obj["galat"]?.jsonObject ?: return null
        val status = obj["_status_http"]?.jsonPrimitive?.int ?: 500
        return JenisGagal.GalatServer(status, galat["kode"]?.jsonPrimitive?.contentOrNull)
    }

    private fun tampilkanHasil(ctx: Context, wm: WindowManager, hasil: HasilAnalisis, p: Penilaian) {
        tutupSemua()
        val lembar = LembarHasil(ctx, wm, hasil, p, onTutup = { tutupSemua() })
        lembar.tampilkan()
        PenampilFixture.daftarkan(lembar)
    }

    private fun tampilkanGalat(ctx: Context, wm: WindowManager, jenis: JenisGagal) {
        tutupSemua()
        val lembar = LembarGalat(
            ctx, wm, tampilanGalat(jenis),
            onAksi = { aksi -> Log.d(TAG, "Aksi galat (tidak dijalankan): $aksi") },
            onTutup = { tutupSemua() },
        )
        lembar.tampilkan()
        PenampilFixture.daftarkan(lembar)
    }

    private fun tampilkanPenilaian(ctx: Context, wm: WindowManager, akhir: (Penilaian) -> Unit) {
        // Thumbnail palsu; dimiliki dan di-recycle oleh lembar saat ditutup.
        val gambar = createBitmap(400, 200, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.LTGRAY) }
        val lembar = LembarPenilaian(
            ctx, wm, gambar,
            onPilih = { p -> tutupSemua(); akhir(p) },
            onBatal = { tutupSemua() },
        )
        lembar.tampilkan()
        PenampilFixture.daftarkan(lembar)
        lembar.aturStatus(StatusAnalisis.BERJALAN)
        PenampilFixture.tunda(1500) { lembar.aturStatus(StatusAnalisis.SELESAI) }
    }

    private companion object {
        const val TAG = "AktivitasFixture"
    }
}

/** Pemegang overlay fixture yang sedang tampil (debug saja), supaya bisa ditutup saat fixture baru dibuka. */
object PenampilFixture {
    private val handler = Handler(Looper.getMainLooper())
    private val aktif = mutableListOf<LembarOverlay>()

    fun daftarkan(lembar: LembarOverlay) {
        aktif += lembar
    }

    fun tunda(ms: Long, aksi: () -> Unit) {
        handler.postDelayed(aksi, ms)
    }

    fun tutupSemua() {
        handler.removeCallbacksAndMessages(null)
        val salinan = aktif.toList()
        aktif.clear()
        salinan.forEach { it.tutup() }
    }
}
