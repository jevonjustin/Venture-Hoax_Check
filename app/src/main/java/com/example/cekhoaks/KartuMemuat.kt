package com.example.cekhoaks

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager

/**
 * Kartu di tengah layar: "Sedang dianalisis" dengan tombol Batal. Muncul bila pengguna sudah
 * memilih di lembar penilaian tetapi analisis belum selesai. Batal, Back, dan ketukan di lapisan
 * gelap memanggil [onBatal]; pemilik yang membatalkan permintaan HTTP dan menutup kartu.
 */
class KartuMemuat(
    context: Context,
    windowManager: WindowManager,
    private val onBatal: () -> Unit,
) : LembarOverlay {

    private val jendela = JendelaLembar(
        context,
        windowManager,
        context.getString(R.string.memuat_batal_deskripsi),
        onKembali = { batal() },
    )
    private var ditutup = false

    /** Memasang kartu. Hasilnya false bila sistem menolak. */
    fun tampilkan(): Boolean {
        val kartu = LayoutInflater.from(jendela.context).inflate(R.layout.overlay_kartu_memuat, jendela.akar, false)
        kartu.findViewById<View>(R.id.memuat_batal).setOnClickListener { batal() }
        if (!jendela.pasang(kartu)) {
            ditutup = true
            return false
        }
        return true
    }

    private fun batal() {
        if (!ditutup) onBatal()
    }

    override fun tutup() {
        if (ditutup) return
        ditutup = true
        jendela.lepas()
    }
}
