package com.example.cekhoaks

import androidx.annotation.StringRes

/** Teks ramah untuk pengguna. Teks dari server (field "pesan") tidak pernah ditampilkan. */
@StringRes
fun JenisGagal.pesan(): Int = when (this) {
    JenisGagal.UrlBelumDiatur -> R.string.galat_url_belum_diatur
    is JenisGagal.TidakTerjangkau -> R.string.galat_tidak_terjangkau
    JenisGagal.WaktuHabis -> R.string.galat_waktu_habis
    JenisGagal.CleartextDiblokir -> R.string.galat_cleartext
    JenisGagal.ResponsTidakDikenali -> R.string.galat_respons_tidak_dikenali
    is JenisGagal.GalatServer -> when (kode) {
        KodeGalat.TEKS_TIDAK_TERBACA -> R.string.galat_teks_tidak_terbaca
        KodeGalat.TERLALU_BESAR -> R.string.galat_terlalu_besar
        KodeGalat.GAMBAR_KOSONG, KodeGalat.BUKAN_GAMBAR -> R.string.galat_gambar_rusak
        else -> R.string.galat_server
    }
}

/** Galat yang kemungkinan besar diperbaiki dengan memeriksa alamat server di aplikasi. */
val JenisGagal.perluPengaturan: Boolean
    get() = this == JenisGagal.UrlBelumDiatur || this is JenisGagal.TidakTerjangkau
