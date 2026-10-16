package com.example.cekhoaks

import android.content.Context
import androidx.core.content.edit

/** Penanda bahwa onboarding sudah pernah ditampilkan, supaya hanya muncul sekali. */
object StatusOnboarding {
    const val NAMA_PREFS = "status_onboarding"
    const val KUNCI_SELESAI = "selesai"

    fun selesai(context: Context): Boolean = prefs(context).getBoolean(KUNCI_SELESAI, false)

    fun tandaiSelesai(context: Context) {
        prefs(context).edit { putBoolean(KUNCI_SELESAI, true) }
    }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(NAMA_PREFS, Context.MODE_PRIVATE)
}
