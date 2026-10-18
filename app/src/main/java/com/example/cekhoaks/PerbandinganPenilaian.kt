package com.example.cekhoaks

import androidx.annotation.StringRes

/** Penilaian awal pengguna sebelum melihat hasil. Hanya hidup di memori untuk satu pengecekan. */
enum class Penilaian { PERCAYA, RAGU, TIDAK_PERCAYA, DILEWATI }

@StringRes
fun labelPenilaian(penilaian: Penilaian): Int = when (penilaian) {
    Penilaian.PERCAYA -> R.string.penilaian_percaya
    Penilaian.RAGU -> R.string.penilaian_ragu
    Penilaian.TIDAK_PERCAYA -> R.string.penilaian_tidak_percaya
    Penilaian.DILEWATI -> R.string.penilaian_dilewati
}

/** Penyebab tingkat hati-hati, disimpulkan di sisi aplikasi dari isi respons (kontrak API tidak berubah). */
enum class PenyebabHatiHati { CIRI, ARTIKEL_SATIR, ARTIKEL_LAIN, UMUM }

/**
 * Urutan: ada ciri -> CIRI; tanpa ciri tetapi ada artikel berlabel satir -> ARTIKEL_SATIR;
 * tanpa ciri dengan artikel lain -> ARTIKEL_LAIN; selain itu UMUM.
 */
fun penyebabHatiHati(hasil: HasilAnalisis): PenyebabHatiHati = when {
    hasil.ciri.isNotEmpty() -> PenyebabHatiHati.CIRI
    hasil.cekFakta.any { it.label == "satir" } -> PenyebabHatiHati.ARTIKEL_SATIR
    hasil.cekFakta.isNotEmpty() -> PenyebabHatiHati.ARTIKEL_LAIN
    else -> PenyebabHatiHati.UMUM
}

/** Pesan perbandingan untuk satu hasil lengkap (memilih penyebab hati-hati dari datanya). */
@StringRes
fun pesanPerbandingan(penilaian: Penilaian, hasil: HasilAnalisis): Int =
    pesanPerbandingan(penilaian, hasil.tingkat, penyebabHatiHati(hasil))

/**
 * Pesan perbandingan antara penilaian awal dan temuan sistem. [penyebab] hanya dipakai untuk
 * kombinasi hati-hati + percaya.
 */
@StringRes
fun pesanPerbandingan(
    penilaian: Penilaian,
    tingkat: Tingkat,
    penyebab: PenyebabHatiHati = PenyebabHatiHati.UMUM,
): Int = when {
    penilaian == Penilaian.DILEWATI -> R.string.banding_pesan_dilewati
    tingkat == Tingkat.TIDAK_DIKENAL -> R.string.banding_pesan_tidak_dikenal
    tingkat == Tingkat.TIDAK_DITEMUKAN -> when (penilaian) {
        Penilaian.PERCAYA -> R.string.banding_pesan_tidak_ditemukan_percaya
        Penilaian.RAGU -> R.string.banding_pesan_tidak_ditemukan_ragu
        else -> R.string.banding_pesan_tidak_ditemukan_tidak_percaya
    }
    penilaian != Penilaian.PERCAYA -> R.string.banding_pesan_ada_ciri_waspada
    tingkat == Tingkat.KUAT -> R.string.banding_pesan_kuat_percaya
    else -> when (penyebab) {
        PenyebabHatiHati.CIRI -> R.string.banding_pesan_hati_hati_percaya_ciri
        PenyebabHatiHati.ARTIKEL_SATIR -> R.string.banding_pesan_hati_hati_percaya_satir
        PenyebabHatiHati.ARTIKEL_LAIN -> R.string.banding_pesan_hati_hati_percaya_artikel
        PenyebabHatiHati.UMUM -> R.string.banding_pesan_hati_hati_percaya_umum
    }
}
