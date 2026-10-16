package com.example.cekhoaks

import android.content.Context
import android.util.AttributeSet
import android.widget.LinearLayout

/**
 * LinearLayout vertikal yang tingginya dibatasi sampai 92% ruang yang tersedia. Anak ScrollView
 * dengan layout_weight mengecil sendiri bila isinya lebih panjang, sehingga pegangan dan tombol
 * di bawahnya tetap terlihat. View biasa tidak punya tinggi maksimum bawaan, jadi dibuat di sini.
 */
class LembarTerbatas @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : LinearLayout(context, attrs) {

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        if (MeasureSpec.getMode(heightMeasureSpec) == MeasureSpec.UNSPECIFIED) {
            super.onMeasure(widthMeasureSpec, heightMeasureSpec)
            return
        }
        val maks = (MeasureSpec.getSize(heightMeasureSpec) * BATAS_TINGGI).toInt()
        super.onMeasure(widthMeasureSpec, MeasureSpec.makeMeasureSpec(maks, MeasureSpec.AT_MOST))
    }

    private companion object {
        const val BATAS_TINGGI = 0.92f
    }
}
