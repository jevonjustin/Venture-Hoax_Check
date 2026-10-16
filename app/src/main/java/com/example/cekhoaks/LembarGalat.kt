package com.example.cekhoaks

import android.content.Context
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import androidx.annotation.StringRes

/**
 * Lembar galat: ikon, judul, penjelasan, tombol utama sesuai [TampilanGalat.aksiUtama], tombol
 * kedua "Buka pengaturan" bila diminta, dan tombol teks "Tutup". Back dan ketukan di lapisan
 * gelap sama dengan Tutup.
 *
 * Lembar tidak menutup dirinya setelah tombol ditekan; pemilik memanggil [tutup] bila perlu.
 *
 * @param onAksi dipanggil dengan [AksiGalat] dari tombol utama atau tombol kedua.
 */
class LembarGalat(
    context: Context,
    windowManager: WindowManager,
    private val tampilan: TampilanGalat,
    private val onAksi: (AksiGalat) -> Unit,
    private val onTutup: () -> Unit,
) : LembarOverlay {

    private val jendela = JendelaLembar(
        context,
        windowManager,
        context.getString(R.string.galat_aksi_tutup),
        onKembali = { tutupDiminta() },
    )
    private var ditutup = false

    /** Memasang lembar. Hasilnya false bila sistem menolak. */
    fun tampilkan(): Boolean {
        val view = jendela.buatKerangka(
            R.drawable.bg_lembar_putih,
            R.layout.overlay_lembar_galat_isi,
            R.layout.overlay_lembar_galat_kaki,
        )
        view.findViewById<TextView>(R.id.galat_judul).setText(tampilan.judul)
        view.findViewById<TextView>(R.id.galat_isi).setText(tampilan.isi)
        view.findViewById<Button>(R.id.galat_aksi_utama).apply {
            setText(labelAksi(tampilan.aksiUtama))
            setOnClickListener { aksi(tampilan.aksiUtama) }
        }
        view.findViewById<Button>(R.id.galat_aksi_kedua).apply {
            visibility = if (tampilan.tampilkanPengaturanKedua) View.VISIBLE else View.GONE
            setOnClickListener { aksi(AksiGalat.BUKA_PENGATURAN) }
        }
        view.findViewById<Button>(R.id.galat_tutup).setOnClickListener { tutupDiminta() }

        if (!jendela.pasang(view)) {
            ditutup = true
            return false
        }
        return true
    }

    @StringRes
    private fun labelAksi(aksi: AksiGalat): Int = when (aksi) {
        AksiGalat.PILIH_ULANG -> R.string.galat_aksi_pilih_ulang
        AksiGalat.COBA_LAGI -> R.string.galat_aksi_coba_lagi
        AksiGalat.BUKA_PENGATURAN -> R.string.galat_aksi_pengaturan
    }

    private fun aksi(aksi: AksiGalat) {
        if (!ditutup) onAksi(aksi)
    }

    private fun tutupDiminta() {
        if (!ditutup) onTutup()
    }

    override fun tutup() {
        if (ditutup) return
        ditutup = true
        jendela.lepas()
    }
}
