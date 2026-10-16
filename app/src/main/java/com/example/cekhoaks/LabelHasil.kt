package com.example.cekhoaks

import androidx.annotation.ColorRes
import androidx.annotation.StringRes

// Pemetaan nilai dari server ke resource teks/warna. Semua fungsi di sini murni (tanpa Context)
// dan selalu punya cadangan untuk nilai yang belum dikenal, supaya server yang lebih baru
// tidak membuat tampilan rusak.

// ---------- Tingkat ----------

enum class IkonTingkat { SEGITIGA_SERU, LINGKARAN_SERU, LINGKARAN_INFO }

/** bg/fg untuk banner, soft/ink untuk lencana dan kotak "Temuan sistem". */
data class PaletTingkat(
    @param:ColorRes val bg: Int,
    @param:ColorRes val fg: Int,
    @param:ColorRes val soft: Int,
    @param:ColorRes val ink: Int,
)

data class TampilanTingkat(
    @param:StringRes val judul: Int,
    @param:StringRes val keterangan: Int,
    @param:StringRes val tips: Int,
    val palet: PaletTingkat,
    val ikon: IkonTingkat,
)

private val PALET_TIDAK_DITEMUKAN = PaletTingkat(
    R.color.tingkat_tidak_ditemukan_bg,
    R.color.tingkat_tidak_ditemukan_fg,
    R.color.tingkat_tidak_ditemukan_soft,
    R.color.tingkat_tidak_ditemukan_ink,
)

/** Tingkat tak dikenal memakai tampilan netral (palet dan ikon "tidak ditemukan"). */
fun tampilanTingkat(tingkat: Tingkat): TampilanTingkat = when (tingkat) {
    Tingkat.KUAT -> TampilanTingkat(
        R.string.hasil_tingkat_kuat, R.string.hasil_keterangan_kuat, R.string.hasil_tips_kuat,
        PaletTingkat(
            R.color.tingkat_kuat_bg, R.color.tingkat_kuat_fg,
            R.color.tingkat_kuat_soft, R.color.tingkat_kuat_ink,
        ),
        IkonTingkat.SEGITIGA_SERU,
    )
    Tingkat.HATI_HATI -> TampilanTingkat(
        R.string.hasil_tingkat_hati_hati, R.string.hasil_keterangan_hati_hati, R.string.hasil_tips_hati_hati,
        PaletTingkat(
            R.color.tingkat_hati_hati_bg, R.color.tingkat_hati_hati_fg,
            R.color.tingkat_hati_hati_soft, R.color.tingkat_hati_hati_ink,
        ),
        IkonTingkat.LINGKARAN_SERU,
    )
    Tingkat.TIDAK_DITEMUKAN -> TampilanTingkat(
        R.string.hasil_tingkat_tidak_ditemukan, R.string.hasil_keterangan_tidak_ditemukan,
        R.string.hasil_tips_tidak_ditemukan, PALET_TIDAK_DITEMUKAN, IkonTingkat.LINGKARAN_INFO,
    )
    Tingkat.TIDAK_DIKENAL -> TampilanTingkat(
        R.string.hasil_tingkat_tidak_dikenal, R.string.hasil_keterangan_tidak_dikenal,
        R.string.hasil_tips_tidak_dikenal, PALET_TIDAK_DITEMUKAN, IkonTingkat.LINGKARAN_INFO,
    )
}

// ---------- Ciri ----------

/** Nama ciri: dari resource aplikasi, atau teks dari server untuk id yang belum dikenal. */
sealed interface NamaCiri {
    data class DariResource(@param:StringRes val res: Int) : NamaCiri
    data class DariServer(val teks: String) : NamaCiri
}

/** Id ciri terkunci (docs/API.md) memakai nama dari aplikasi; id lain memakai [namaServer]; kosong → "Ciri lain". */
fun namaCiri(id: String, namaServer: String): NamaCiri {
    val res = when (id.trim().lowercase()) {
        "permintaan_data_rahasia" -> R.string.ciri_nama_permintaan_data_rahasia
        "ajakan_menyebarkan" -> R.string.ciri_nama_ajakan_menyebarkan
        "desakan_waktu" -> R.string.ciri_nama_desakan_waktu
        "kapital_tanda_seru" -> R.string.ciri_nama_kapital_tanda_seru
        "link_mencurigakan" -> R.string.ciri_nama_link_mencurigakan
        "sumber_tidak_jelas" -> R.string.ciri_nama_sumber_tidak_jelas
        "judul_clickbait" -> R.string.ciri_nama_judul_clickbait
        "bahasa_provokatif" -> R.string.ciri_nama_bahasa_provokatif
        "pernah_dibantah" -> R.string.ciri_nama_pernah_dibantah
        else -> null
    }
    return when {
        res != null -> NamaCiri.DariResource(res)
        namaServer.isNotBlank() -> NamaCiri.DariServer(namaServer.trim())
        else -> NamaCiri.DariResource(R.string.ciri_nama_lain)
    }
}

/** Mengubah [NamaCiri] menjadi teks; [ambilString] biasanya `context::getString`. */
fun NamaCiri.teks(ambilString: (Int) -> String): String = when (this) {
    is NamaCiri.DariResource -> ambilString(res)
    is NamaCiri.DariServer -> teks
}

/** Teks keyakinan ("tinggi"/"sedang"); nilai lain null dan tidak ditampilkan. Tanpa angka persen. */
@StringRes
fun teksKeyakinan(keyakinan: String): Int? = when (keyakinan.trim().lowercase()) {
    "tinggi" -> R.string.hasil_keyakinan_tinggi
    "sedang" -> R.string.hasil_keyakinan_sedang
    else -> null
}

// ---------- Label artikel cek fakta ----------

enum class GayaLabel { MERAH, NETRAL }

data class LabelArtikel(
    @param:StringRes val teks: Int,
    val gaya: GayaLabel,
    @param:ColorRes val latar: Int,
    @param:ColorRes val warnaTeks: Int,
)

/**
 * Label artikel (keputusan D9). "benar", "lainnya", dan nilai tak dikenal tampil sebagai "RUJUKAN"
 * karena UI tidak boleh menyatakan sebuah informasi benar; judul artikel tetap tampil.
 */
fun labelArtikel(label: String): LabelArtikel {
    val merah = { teks: Int ->
        LabelArtikel(teks, GayaLabel.MERAH, R.color.tingkat_kuat_soft, R.color.tingkat_kuat_ink)
    }
    val netral = { teks: Int ->
        LabelArtikel(teks, GayaLabel.NETRAL, R.color.navy_lembut, R.color.navy)
    }
    // Server memakai strip().lower(), jadi nilai dinormalkan dulu.
    return when (label.trim().lowercase()) {
        "salah" -> merah(R.string.hasil_label_salah)
        "penipuan" -> merah(R.string.hasil_label_penipuan)
        "klarifikasi" -> netral(R.string.hasil_label_klarifikasi)
        "satir" -> netral(R.string.hasil_label_satir)
        "belum_terbukti" -> netral(R.string.hasil_label_belum_terbukti)
        else -> netral(R.string.hasil_label_rujukan)
    }
}

// ---------- Pemeriksaan terbatas ----------

/** Kalimat per nilai, tanpa duplikat, mengikuti urutan dari server. Nilai tak dikenal memakai kalimat umum. */
fun kalimatPemeriksaanTerbatas(daftar: List<String>): List<Int> = daftar.map {
    when (it.trim().lowercase()) {
        "cek_fakta" -> R.string.hasil_terbatas_cek_fakta
        "ai" -> R.string.hasil_terbatas_ai
        else -> R.string.hasil_terbatas_lain
    }
}.distinct()

/** Arti bagi hasil: lebih tegas bila tingkat "tidak ditemukan". */
@StringRes
fun artiPemeriksaanTerbatas(tingkat: Tingkat): Int =
    if (tingkat == Tingkat.TIDAK_DITEMUKAN) R.string.hasil_terbatas_arti_tidak_ditemukan
    else R.string.hasil_terbatas_arti

/** True jika pencarian artikel cek fakta tidak berjalan (untuk chip ringkasan). */
fun cekFaktaTerbatas(daftar: List<String>): Boolean = "cek_fakta" in daftar
