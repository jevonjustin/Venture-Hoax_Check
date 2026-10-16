package com.example.cekhoaks

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.Json

// Bentuk data yang dikirim server, sesuai docs/API.md. Anotasi @Serializable membuat
// plugin kotlinx.serialization menulis kode pembaca JSON untuk kelas ini saat build.
// @SerialName menghubungkan nama field JSON (snake_case) dengan nama properti Kotlin.

/**
 * Tingkat hasil. [TIDAK_DIKENAL] adalah cadangan untuk nilai yang belum dikenal versi aplikasi ini
 * (misalnya server yang lebih baru menambah tingkat); UI menampilkannya secara netral.
 */
@Serializable(with = TingkatSerializer::class)
enum class Tingkat(val kode: String) {
    KUAT("kuat"),
    HATI_HATI("hati_hati"),
    TIDAK_DITEMUKAN("tidak_ditemukan"),
    TIDAK_DIKENAL("tidak_dikenal"),
}

/** Membaca tingkat dari string; nilai apa pun yang tidak dikenal menjadi [Tingkat.TIDAK_DIKENAL]. */
object TingkatSerializer : KSerializer<Tingkat> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.example.cekhoaks.Tingkat", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): Tingkat {
        val kode = decoder.decodeString()
        return Tingkat.entries.firstOrNull { it != Tingkat.TIDAK_DIKENAL && it.kode == kode }
            ?: Tingkat.TIDAK_DIKENAL
    }

    override fun serialize(encoder: Encoder, value: Tingkat) = encoder.encodeString(value.kode)
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
    /** True jika url berformat lama yang sudah mati; UI menggantinya dengan pencarian judul di web. */
    @SerialName("url_format_lama") val urlFormatLama: Boolean = false,
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
    /** Bagian pemeriksaan yang tidak berjalan ("cek_fakta", "ai"); kosong jika semuanya berjalan. */
    @SerialName("pemeriksaan_terbatas") val pemeriksaanTerbatas: List<String> = emptyList(),
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
    const val GALAT_SERVER = "galat_server"
    const val GALAT_HTTP = "galat_http"
}

/** Field baru dari server diabaikan, supaya versi server yang lebih baru tidak membuat aplikasi gagal. */
val jsonApi = Json { ignoreUnknownKeys = true }
