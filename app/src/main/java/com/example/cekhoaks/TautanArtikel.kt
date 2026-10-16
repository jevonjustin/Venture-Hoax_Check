package com.example.cekhoaks

import java.net.URLEncoder
import java.time.DateTimeException
import java.time.LocalDate

/** Alamat pencarian web untuk [judul]; dipakai saat tautan asli artikel tidak bisa dibuka. */
fun urlPencarian(judul: String): String =
    "https://www.google.com/search?q=" + URLEncoder.encode(judul.trim(), "UTF-8")

/** True jika url dari server layak dibuka: tidak kosong dan bukan url format lama yang sudah mati. */
fun tautanAsliAktif(a: ArtikelCekFakta): Boolean = !a.urlFormatLama && a.url.isNotBlank()

/** Tujuan tombol artikel: url dari server, atau pencarian judul bila tautan asli tidak bisa dipakai. */
fun tautanArtikel(a: ArtikelCekFakta): String = if (tautanAsliAktif(a)) a.url else urlPencarian(a.judul)

/**
 * Mengubah tanggal ISO 8601 ("2025-11-04" atau "2025-11-04T10:00:00Z") menjadi "4 November 2025".
 * [namaBulan] adalah 12 nama bulan dari strings.xml (Januari dulu), supaya fungsi ini bebas dari
 * Context dan bisa diuji. Hasilnya null jika tanggal null, tidak valid, atau [namaBulan] tidak berisi 12 nama.
 */
fun formatTanggal(iso: String?, namaBulan: List<String>): String? {
    if (iso == null || namaBulan.size != 12) return null
    val bagianTanggal = iso.trim().take(10)
    val tanggal = try {
        LocalDate.parse(bagianTanggal)
    } catch (_: DateTimeException) {
        return null
    }
    return "${tanggal.dayOfMonth} ${namaBulan[tanggal.monthValue - 1]} ${tanggal.year}"
}
