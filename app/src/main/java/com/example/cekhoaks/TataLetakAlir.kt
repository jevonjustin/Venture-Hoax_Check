package com.example.cekhoaks

import android.content.Context
import android.util.AttributeSet
import android.view.ViewGroup
import androidx.core.view.isGone

/**
 * Tata letak yang menyusun anak dari kiri ke kanan dan pindah baris bila tidak muat
 * (dipakai untuk chip ringkasan dan chip bukti). Jarak antar-anak dalam piksel.
 */
class TataLetakAlir @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : ViewGroup(context, attrs) {

    var jarakHorizontal = 0
    var jarakVertikal = 0

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val lebarMaks = MeasureSpec.getSize(widthMeasureSpec) - paddingLeft - paddingRight
        val batasiLebar = MeasureSpec.getMode(widthMeasureSpec) != MeasureSpec.UNSPECIFIED
        var x = 0
        var y = 0
        var tinggiBaris = 0
        var lebarTerpakai = 0
        for (i in 0 until childCount) {
            val anak = getChildAt(i)
            if (anak.isGone) continue
            val spekLebar = if (batasiLebar) {
                MeasureSpec.makeMeasureSpec(lebarMaks.coerceAtLeast(0), MeasureSpec.AT_MOST)
            } else {
                MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED)
            }
            anak.measure(spekLebar, MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED))
            if (batasiLebar && x > 0 && x + anak.measuredWidth > lebarMaks) {
                y += tinggiBaris + jarakVertikal
                x = 0
                tinggiBaris = 0
            }
            x += anak.measuredWidth + jarakHorizontal
            tinggiBaris = maxOf(tinggiBaris, anak.measuredHeight)
            lebarTerpakai = maxOf(lebarTerpakai, x - jarakHorizontal)
        }
        val tinggi = y + tinggiBaris + paddingTop + paddingBottom
        setMeasuredDimension(
            resolveSize(lebarTerpakai + paddingLeft + paddingRight, widthMeasureSpec),
            resolveSize(tinggi, heightMeasureSpec),
        )
    }

    override fun onLayout(changed: Boolean, l: Int, t: Int, r: Int, b: Int) {
        val lebarMaks = r - l - paddingLeft - paddingRight
        var x = 0
        var y = 0
        var tinggiBaris = 0
        for (i in 0 until childCount) {
            val anak = getChildAt(i)
            if (anak.isGone) continue
            if (x > 0 && x + anak.measuredWidth > lebarMaks) {
                y += tinggiBaris + jarakVertikal
                x = 0
                tinggiBaris = 0
            }
            val kiri = paddingLeft + x
            val atas = paddingTop + y
            anak.layout(kiri, atas, kiri + anak.measuredWidth, atas + anak.measuredHeight)
            x += anak.measuredWidth + jarakHorizontal
            tinggiBaris = maxOf(tinggiBaris, anak.measuredHeight)
        }
    }
}
