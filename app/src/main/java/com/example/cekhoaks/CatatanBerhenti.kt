package com.example.cekhoaks

import android.content.Context
import androidx.core.content.edit

/**
 * Tanda bahwa sesi rekam layar dihentikan sistem (misalnya HP dikunci). Disimpan di
 * SharedPreferences supaya layar utama bisa menampilkan keterangan sampai tombol cek diaktifkan lagi.
 */
object CatatanBerhenti {
    const val NAMA_PREFS = "catatan_berhenti"
    const val KUNCI_BERHENTI = "sesi_berhenti"

    fun tandai(context: Context) {
        prefs(context).edit { putBoolean(KUNCI_BERHENTI, true) }
    }

    fun hapus(context: Context) {
        prefs(context).edit { remove(KUNCI_BERHENTI) }
    }

    fun ada(context: Context): Boolean = prefs(context).getBoolean(KUNCI_BERHENTI, false)

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(NAMA_PREFS, Context.MODE_PRIVATE)
}
