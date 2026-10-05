package com.example.cekhoaks

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

// Bentuk data yang dikirim server, sesuai docs/API.md. Anotasi @Serializable membuat
// plugin kotlinx.serialization menulis kode pembaca JSON untuk kelas ini saat build.
// @SerialName menghubungkan nama field JSON (snake_case) dengan nama properti Kotlin.

@Serializable
enum class Tingkat {
    @SerialName("kuat") KUAT,
    @SerialName("hati_hati") HATI_HATI,
    @SerialName("tidak_ditemukan") TIDAK_DITEMUKAN,
}

@Serializable
data class Ciri(
    val id: String,
    val nama: String,
    val bukti: List<String>,
    val penjelasan: String,
    val keyakinan: String,
)

@Serializable
data class ArtikelCekFakta(
    val judul: String,
    val sumber: String,
    val url: String,
    @SerialName("skor_kemiripan") val skorKemiripan: Double,
    val label: String,
    /** Tanggal terbit (ISO 8601), atau null jika tidak diketahui. */
    val tanggal: String? = null,
)

@Serializable
data class HasilAnalisis(
    @SerialName("id_permintaan") val idPermintaan: String,
    val tingkat: Tingkat,
    @SerialName("klaim_utama") val klaimUtama: String? = null,
    val ciri: List<Ciri>,
    @SerialName("cek_fakta") val cekFakta: List<ArtikelCekFakta>,
    @SerialName("teks_terbaca") val teksTerbaca: String,
    @SerialName("durasi_ms") val durasiMs: Long,
)

@Serializable
data class StatusServer(val status: String, val versi: String)

@Serializable
data class IsiGalat(val kode: String, val pesan: String)

@Serializable
data class ResponsGalat(val galat: IsiGalat)

/** Kode galat dari server yang ditangani khusus oleh aplikasi. */
object KodeGalat {
    const val GAMBAR_KOSONG = "gambar_kosong"
    const val BUKAN_GAMBAR = "bukan_gambar"
    const val TERLALU_BESAR = "terlalu_besar"
    const val TEKS_TIDAK_TERBACA = "teks_tidak_terbaca"
}

/** Field baru dari server diabaikan, supaya versi server yang lebih baru tidak membuat aplikasi gagal. */
val jsonApi = Json { ignoreUnknownKeys = true }
