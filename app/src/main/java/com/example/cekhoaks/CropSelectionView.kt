package com.example.cekhoaks

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.Log
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import androidx.core.content.ContextCompat
import kotlin.math.abs

/**
 * Menampilkan tangkapan layar yang "dibekukan" dan kotak seleksi yang bisa diatur pengguna:
 * seret di luar kotak untuk menggambar kotak baru, seret di dalam kotak untuk memindahkannya,
 * dan seret sudut atau sisi untuk mengubah ukurannya.
 *
 * Perhitungan posisi kotak ada di [GeometriSeleksi]; view ini hanya menggambar dan meneruskan
 * gerakan jari.
 *
 * Pola yang diadaptasi (lisensi MIT): pembagian mode sentuhan (kotak baru, pindah, empat sudut,
 * empat sisi) dengan sudut diperiksa lebih dulu, dan batas kotak di dalam layar, dari SavinduK,
 * SnapCrop (SelectionView.kt), https://github.com/SavinduK/SnapCrop
 *
 * @param onInteraksi dipanggil dengan true saat jari mulai mengatur kotak, dan false saat selesai.
 */
@SuppressLint("ViewConstructor")
class CropSelectionView(
    context: Context,
    private val gambar: Bitmap,
    private val onInteraksi: (sedangDiatur: Boolean) -> Unit,
) : View(context) {

    private enum class Mode { DIAM, MENUNGGU_KOTAK_BARU, KOTAK_BARU, PINDAH, UBAH_UKURAN }

    private val kepadatan = resources.displayMetrics.density
    private val ukuranMin = resources.getDimension(R.dimen.pilih_kotak_min)
    private val radiusSentuh = resources.getDimension(R.dimen.pilih_area_sentuh) / 2f
    private val ambangGeser = ViewConfiguration.get(context).scaledTouchSlop

    private var area = Kotak(0f, 0f, 0f, 0f)
    private var seleksi = Kotak(0f, 0f, 0f, 0f)
    private var seleksiSaatDisentuh = seleksi
    private var mode = Mode.DIAM
    private var pegangan: Pegangan? = null
    private var xAwal = 0f
    private var yAwal = 0f

    // Objek gambar disiapkan sekali, bukan di onDraw, karena onDraw dipanggil setiap frame.
    private val kotakArea = RectF()
    private val kotakSeleksi = RectF()
    private val kotakBantu = RectF()
    private val lubang = Path()
    private val sudutKotak = 8f * kepadatan
    private val tebalGaris = 3f * kepadatan
    private val sudutPegangan = 5f * kepadatan
    private val setengahPeganganSudut = resources.getDimension(R.dimen.pilih_pegangan_sudut) / 2f
    private val setengahPeganganSisi = resources.getDimension(R.dimen.pilih_pegangan_sisi) / 2f

    private val catGambar = Paint(Paint.FILTER_BITMAP_FLAG)
    private val catGelap = Paint().apply { color = ContextCompat.getColor(context, R.color.pilih_lapisan_gelap) }
    private val catCincin = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = tebalGaris
        color = ContextCompat.getColor(context, R.color.pilih_cincin)
    }
    private val catGaris = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = tebalGaris
        color = ContextCompat.getColor(context, R.color.white)
    }
    private val catPeganganIsi = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.white)
        setShadowLayer(3f * kepadatan, 0f, 1f * kepadatan, 0x4D000000)
    }
    private val catPeganganTepi = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 2.5f * kepadatan
        color = ContextCompat.getColor(context, R.color.navy)
    }
    private val catPeganganSisi = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 4f * kepadatan
        strokeCap = Paint.Cap.ROUND
        color = ContextCompat.getColor(context, R.color.pilih_pegangan_sisi)
    }

    init {
        contentDescription = context.getString(R.string.pilih_area_deskripsi)
    }

    /** Area yang dipilih dalam piksel Bitmap tangkapan layar. */
    fun seleksiDalamPiksel(): KotakPiksel =
        GeometriSeleksi.petakanKeBitmap(seleksi, area, gambar.width, gambar.height)

    fun pilihSeluruhLayar() {
        seleksi = area
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        if (w == 0 || h == 0) return
        if (w != gambar.width || h != gambar.height) {
            // Normalnya sama persis. Jika berbeda, gambar diperkecil secara seragam dan pemetaan
            // koordinat tetap benar, tetapi gambar beku tidak lagi tepat menimpa layar asli.
            Log.w(TAG, "Ukuran view ${w}x$h berbeda dari tangkapan ${gambar.width}x${gambar.height}")
        }
        area = GeometriSeleksi.areaGambar(w, h, gambar.width, gambar.height)
        seleksi = GeometriSeleksi.kotakAwal(area, ukuranMin)
        kotakArea.set(area.kiri, area.atas, area.kanan, area.bawah)
    }

    override fun onDraw(canvas: Canvas) {
        // Jaga-jaga: Bitmap yang sudah di-recycle tidak boleh digambar lagi (aplikasi akan crash).
        if (gambar.isRecycled) return
        canvas.drawBitmap(gambar, null, kotakArea, catGambar)

        kotakSeleksi.set(seleksi.kiri, seleksi.atas, seleksi.kanan, seleksi.bawah)

        // Lapisan gelap dengan "lubang" bersudut membulat di posisi seleksi. EVEN_ODD membuat
        // bagian yang tertutup dua bentuk (layar penuh dan kotak seleksi) menjadi kosong.
        lubang.reset()
        lubang.fillType = Path.FillType.EVEN_ODD
        lubang.addRect(0f, 0f, width.toFloat(), height.toFloat(), Path.Direction.CW)
        lubang.addRoundRect(kotakSeleksi, sudutKotak, sudutKotak, Path.Direction.CW)
        canvas.drawPath(lubang, catGelap)

        // Cincin hijau tipis di luar kotak, lalu garis putih di dalam tepi kotak (rujukan: docs/prototype/prototype.html).
        val setengah = tebalGaris / 2f
        kotakBantu.set(kotakSeleksi)
        kotakBantu.inset(-setengah, -setengah)
        canvas.drawRoundRect(kotakBantu, sudutKotak + setengah, sudutKotak + setengah, catCincin)
        kotakBantu.set(kotakSeleksi)
        kotakBantu.inset(setengah, setengah)
        canvas.drawRoundRect(kotakBantu, sudutKotak - setengah, sudutKotak - setengah, catGaris)

        gambarPeganganSisi(canvas)
        gambarPeganganSudut(canvas, seleksi.kiri, seleksi.atas)
        gambarPeganganSudut(canvas, seleksi.kanan, seleksi.atas)
        gambarPeganganSudut(canvas, seleksi.kiri, seleksi.bawah)
        gambarPeganganSudut(canvas, seleksi.kanan, seleksi.bawah)
    }

    private fun gambarPeganganSudut(canvas: Canvas, x: Float, y: Float) {
        val s = setengahPeganganSudut
        kotakBantu.set(x - s, y - s, x + s, y + s)
        canvas.drawRoundRect(kotakBantu, sudutPegangan, sudutPegangan, catPeganganIsi)
        canvas.drawRoundRect(kotakBantu, sudutPegangan, sudutPegangan, catPeganganTepi)
    }

    /** Garis pendek putih di tengah setiap sisi, lebih samar dari pegangan sudut. */
    private fun gambarPeganganSisi(canvas: Canvas) {
        val setengah = setengahPeganganSisi
        val tengahX = (seleksi.kiri + seleksi.kanan) / 2f
        val tengahY = (seleksi.atas + seleksi.bawah) / 2f
        canvas.drawLine(tengahX - setengah, seleksi.atas, tengahX + setengah, seleksi.atas, catPeganganSisi)
        canvas.drawLine(tengahX - setengah, seleksi.bawah, tengahX + setengah, seleksi.bawah, catPeganganSisi)
        canvas.drawLine(seleksi.kiri, tengahY - setengah, seleksi.kiri, tengahY + setengah, catPeganganSisi)
        canvas.drawLine(seleksi.kanan, tengahY - setengah, seleksi.kanan, tengahY + setengah, catPeganganSisi)
    }

    // ClickableViewAccessibility: view ini tidak punya aksi klik. Pengguna pembaca layar memakai
    // tombol "Pilih seluruh layar" dan "Cek Sekarang".
    @SuppressLint("ClickableViewAccessibility")
    override fun onTouchEvent(event: MotionEvent): Boolean {
        val x = event.x
        val y = event.y
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                xAwal = x
                yAwal = y
                seleksiSaatDisentuh = seleksi
                pegangan = GeometriSeleksi.peganganDiTitik(seleksi, x, y, radiusSentuh)
                mode = when {
                    pegangan != null -> Mode.UBAH_UKURAN
                    seleksi.berisi(x, y) -> Mode.PINDAH
                    // Kotak baru baru dibuat setelah jari benar-benar bergeser, supaya ketukan
                    // tidak sengaja di luar kotak tidak menghapus seleksi yang sudah ada.
                    else -> Mode.MENUNGGU_KOTAK_BARU
                }
                if (mode != Mode.MENUNGGU_KOTAK_BARU) onInteraksi(true)
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = x - xAwal
                val dy = y - yAwal
                when (mode) {
                    Mode.MENUNGGU_KOTAK_BARU -> if (abs(dx) > ambangGeser || abs(dy) > ambangGeser) {
                        mode = Mode.KOTAK_BARU
                        onInteraksi(true)
                        seleksi = GeometriSeleksi.kotakBaru(xAwal, yAwal, x, y, area, ukuranMin)
                    }
                    Mode.KOTAK_BARU -> seleksi = GeometriSeleksi.kotakBaru(xAwal, yAwal, x, y, area, ukuranMin)
                    Mode.PINDAH -> seleksi = GeometriSeleksi.geser(seleksiSaatDisentuh, dx, dy, area)
                    Mode.UBAH_UKURAN -> pegangan?.let {
                        seleksi = GeometriSeleksi.ubahUkuran(seleksiSaatDisentuh, it, dx, dy, area, ukuranMin)
                    }
                    Mode.DIAM -> Unit
                }
                invalidate()
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                val sedangMengatur = mode != Mode.DIAM && mode != Mode.MENUNGGU_KOTAK_BARU
                mode = Mode.DIAM
                pegangan = null
                if (sedangMengatur) onInteraksi(false)
            }
        }
        return true
    }

    companion object {
        private const val TAG = "CekHoaks"
    }
}
