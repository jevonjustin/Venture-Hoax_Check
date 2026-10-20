package com.example.cekhoaks

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Outline
import android.graphics.Paint
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.ViewOutlineProvider
import android.widget.FrameLayout
import androidx.core.content.ContextCompat
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Tombol cek (persegi bersudut bulat dengan tiga lingkaran konsentris) yang dipasang di atas aplikasi lain oleh [FloatingButtonService].
 * View ini hanya membedakan ketukan dan geseran. Posisi jendelanya diatur oleh service.
 *
 * Pola yang diadaptasi (lisensi MIT): pembedaan ketukan dan geseran dengan touch slop memakai
 * rawY dan posisi awal saat jari turun, dari SavinduK, SnapCrop, https://github.com/SavinduK/SnapCrop
 *
 * @param onKetuk dipanggil saat tombol diketuk (bukan digeser).
 * @param onSentuhanMulai dipanggil saat jari mulai menyentuh tombol.
 * @param onGeser dipanggil selama tombol digeser, dengan jarak vertikal (px) dari titik awal sentuhan.
 */
// ClickableViewAccessibility: tanganiSentuhan memanggil performClick saat ketukan, jadi klik
// tetap bisa dipicu pembaca layar (TalkBack).
@SuppressLint("ViewConstructor", "ClickableViewAccessibility")
class FloatingButtonView(
    context: Context,
    private val onKetuk: () -> Unit,
    private val onSentuhanMulai: () -> Unit,
    private val onGeser: (selisihY: Int) -> Unit,
) : FrameLayout(context) {

    // Jarak minimum (px) jari harus bergerak sebelum dianggap menggeser. Nilainya dari sistem,
    // sama dengan yang dipakai daftar dan tombol bawaan Android.
    private val ambangGeser = ViewConfiguration.get(context).scaledTouchSlop
    private var yAwalJari = 0f
    private var sedangDigeser = false

    init {
        val ukuran = resources.getDimensionPixelSize(R.dimen.tombol_cek_ukuran)
        val ruangBayangan = resources.getDimensionPixelSize(R.dimen.tombol_cek_ruang_bayangan)

        // Jendela overlay seukuran isinya (WRAP_CONTENT), jadi bayangan butuh ruang tambahan
        // di sekeliling tombol agar tidak terpotong.
        setPadding(ruangBayangan, ruangBayangan, ruangBayangan, ruangBayangan)
        clipToPadding = false

        val radiusSudut = ukuran * RASIO_SUDUT
        val tombolCek = object : View(context) {
            private val kuas = Paint(Paint.ANTI_ALIAS_FLAG)
            private val lingkaran = listOf(
                RASIO_LINGKARAN_LUAR to ContextCompat.getColor(context, R.color.tombol_cek_lingkaran_luar),
                RASIO_LINGKARAN_TENGAH to ContextCompat.getColor(context, R.color.tombol_cek_lingkaran_tengah),
                RASIO_LINGKARAN_DALAM to ContextCompat.getColor(context, R.color.tombol_cek_lingkaran_dalam),
            )

            override fun onDraw(canvas: Canvas) {
                super.onDraw(canvas)
                val cx = width / 2f
                val cy = height / 2f
                for ((rasio, warna) in lingkaran) {
                    kuas.color = warna
                    canvas.drawCircle(cx, cy, width * rasio / 2f, kuas)
                }
            }

            override fun setPressed(pressed: Boolean) {
                super.setPressed(pressed)
                val skala = if (pressed) SKALA_DITEKAN else 1f
                animate().scaleX(skala).scaleY(skala).setDuration(DURASI_ANIMASI_MS).start()
            }
        }.apply {
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = radiusSudut
                setColor(ContextCompat.getColor(context, R.color.tombol_cek_latar))
                setStroke(
                    resources.getDimensionPixelSize(R.dimen.tombol_cek_garis),
                    ContextCompat.getColor(context, R.color.tombol_cek_garis),
                )
            }
            // Elevation menghasilkan bayangan. Outline bawaan latar transparan tidak memberi
            // bayangan, jadi bentuk bayangan (persegi bersudut bulat) ditentukan sendiri.
            elevation = resources.getDimension(R.dimen.tombol_cek_bayangan)
            outlineProvider = object : ViewOutlineProvider() {
                override fun getOutline(view: View, outline: Outline) {
                    outline.setRoundRect(0, 0, view.width, view.height, radiusSudut)
                }
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val warnaBayangan = ContextCompat.getColor(context, R.color.tombol_cek_bayangan)
                outlineAmbientShadowColor = warnaBayangan
                outlineSpotShadowColor = warnaBayangan
            }
            contentDescription = context.getString(R.string.tombol_cek_deskripsi)
            isClickable = true
            isFocusable = true
            setOnClickListener { onKetuk() }
            setOnTouchListener(::tanganiSentuhan)
        }

        addView(tombolCek, LayoutParams(ukuran, ukuran, Gravity.CENTER))
    }

    private fun tanganiSentuhan(view: View, event: MotionEvent): Boolean {
        // rawY adalah posisi jari di layar. Koordinat biasa (y) relatif terhadap view, padahal
        // jendela tombol ikut berpindah saat digeser, sehingga nilainya akan ikut bergeser.
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                yAwalJari = event.rawY
                sedangDigeser = false
                view.isPressed = true
                onSentuhanMulai()
            }
            MotionEvent.ACTION_MOVE -> {
                val selisih = event.rawY - yAwalJari
                if (!sedangDigeser && abs(selisih) > ambangGeser) {
                    sedangDigeser = true
                    view.isPressed = false
                }
                if (sedangDigeser) onGeser(selisih.roundToInt())
            }
            MotionEvent.ACTION_UP -> {
                view.isPressed = false
                if (!sedangDigeser) view.performClick()
                sedangDigeser = false
            }
            MotionEvent.ACTION_CANCEL -> {
                view.isPressed = false
                sedangDigeser = false
            }
        }
        return true
    }

    companion object {
        private const val SKALA_DITEKAN = 0.88f
        private const val DURASI_ANIMASI_MS = 100L

        // Proporsi terhadap ukuran tombol, dari prototipe (tombol 58dp).
        private const val RASIO_SUDUT = 0.38f
        private const val RASIO_LINGKARAN_LUAR = 0.62f
        private const val RASIO_LINGKARAN_TENGAH = 0.40f
        private const val RASIO_LINGKARAN_DALAM = 0.20f
    }
}
