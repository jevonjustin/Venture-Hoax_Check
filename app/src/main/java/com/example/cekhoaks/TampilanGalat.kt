package com.example.cekhoaks

import androidx.annotation.StringRes

/** Tindakan tombol utama di lembar galat. */
enum class AksiGalat {
    /** Kembali ke layar pilih area (mengambil layar baru). */
    PILIH_ULANG,

    /** Kirim ulang potongan yang sama. */
    COBA_LAGI,

    /** Buka pengaturan server di aplikasi. */
    BUKA_PENGATURAN,
}

/** Isi lembar galat. [tampilkanPengaturanKedua]: tampilkan juga tombol "Buka pengaturan" di samping tombol utama. */
data class TampilanGalat(
    @param:StringRes val judul: Int,
    @param:StringRes val isi: Int,
    val aksiUtama: AksiGalat,
    val tampilkanPengaturanKedua: Boolean = false,
)

private val GAMBAR_TIDAK_UTUH = TampilanGalat(
    R.string.galat_judul_gambar, R.string.galat_isi_gambar, AksiGalat.PILIH_ULANG,
)

/** Teks dari server (field "pesan") tidak pernah ditampilkan; yang dipakai hanya kode galatnya. */
fun tampilanGalat(jenis: JenisGagal): TampilanGalat = when (jenis) {
    JenisGagal.UrlBelumDiatur -> TampilanGalat(
        R.string.galat_judul_url, R.string.galat_isi_url, AksiGalat.BUKA_PENGATURAN,
    )
    is JenisGagal.TidakTerjangkau -> TampilanGalat(
        R.string.galat_judul_tidak_terjangkau, R.string.galat_isi_tidak_terjangkau, AksiGalat.COBA_LAGI,
        tampilkanPengaturanKedua = true,
    )
    JenisGagal.WaktuHabis -> TampilanGalat(
        R.string.galat_judul_waktu_habis, R.string.galat_isi_waktu_habis, AksiGalat.COBA_LAGI,
    )
    JenisGagal.CleartextDiblokir -> TampilanGalat(
        R.string.galat_judul_cleartext, R.string.galat_isi_cleartext, AksiGalat.BUKA_PENGATURAN,
    )
    JenisGagal.ResponsTidakDikenali -> TampilanGalat(
        R.string.galat_judul_respons, R.string.galat_isi_respons, AksiGalat.BUKA_PENGATURAN,
    )
    is JenisGagal.GalatServer -> when (jenis.kode) {
        KodeGalat.TEKS_TIDAK_TERBACA -> TampilanGalat(
            R.string.galat_judul_teks, R.string.galat_isi_teks, AksiGalat.PILIH_ULANG,
        )
        KodeGalat.TERLALU_BESAR -> TampilanGalat(
            R.string.galat_judul_besar, R.string.galat_isi_besar, AksiGalat.PILIH_ULANG,
        )
        KodeGalat.GAMBAR_KOSONG, KodeGalat.BUKAN_GAMBAR -> GAMBAR_TIDAK_UTUH
        // galat_server, galat_http, kode tak dikenal, dan null (isi bukan format galat kontrak).
        else -> TampilanGalat(
            R.string.galat_judul_server, R.string.galat_isi_server, AksiGalat.COBA_LAGI,
        )
    }
}

/** Galat lokal: potongan gagal disandikan menjadi JPEG, jadi tidak ada yang bisa dikirim ulang. */
fun tampilanGalatPenyandian(): TampilanGalat = GAMBAR_TIDAK_UTUH
