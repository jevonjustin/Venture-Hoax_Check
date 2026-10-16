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

/**
 * Pesan perbandingan antara penilaian awal dan temuan sistem. Perbandingan hanya membedakan
 * "tidak ditemukan" dari semua tingkat lain (kuat dan hati-hati diperlakukan sama).
 */
@StringRes
fun pesanPerbandingan(penilaian: Penilaian, tingkat: Tingkat): Int = when {
    penilaian == Penilaian.DILEWATI -> R.string.banding_pesan_dilewati
    tingkat == Tingkat.TIDAK_DIKENAL -> R.string.banding_pesan_tidak_dikenal
    tingkat == Tingkat.TIDAK_DITEMUKAN ->
        if (penilaian == Penilaian.PERCAYA) R.string.banding_pesan_tidak_ditemukan_percaya
        else R.string.banding_pesan_tidak_ditemukan_waspada
    else ->
        if (penilaian == Penilaian.PERCAYA) R.string.banding_pesan_ada_ciri_percaya
        else R.string.banding_pesan_ada_ciri_waspada
}
