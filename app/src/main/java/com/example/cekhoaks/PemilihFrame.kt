package com.example.cekhoaks

/**
 * Logika pemilihan frame untuk satu tangkapan layar, dipisah dari ImageReader agar bisa diuji
 * di JVM. Semua method dipanggil dari satu thread yang sama (thread tangkap di [PengambilLayar]).
 *
 * - Saat idle, frame yang masuk langsung ditutup, jadi isi layar tidak dipegang di memori.
 * - Setelah [mulai], frame terbaru disimpan. Frame lama hanya ditutup jika frame baru benar-benar
 *   ada, karena pendengar ImageReader bisa dipanggil tanpa frame baru (null).
 * - Frame dipakai paling cepat [jedaMinMs] setelah [mulai], dan yang dipakai adalah frame terbaru
 *   saat itu, supaya frame transisi saat tombol menghilang tidak terpakai.
 * - Layar yang diam tidak menghasilkan frame. Jika sampai [batasTungguMs] belum ada frame,
 *   pemanggil diminta memaksa frame baru satu kali, lalu ditunggu lagi selama [batasCadanganMs]
 *   sebelum dinyatakan gagal.
 */
class PemilihFrame<F : AutoCloseable>(
    private val jam: Jam,
    private val jedaMinMs: Long = JEDA_MIN_MS,
    private val batasTungguMs: Long = BATAS_TUNGGU_MS,
    private val batasCadanganMs: Long = BATAS_CADANGAN_MS,
) {

    fun interface Jam {
        fun sekarangMs(): Long
    }

    /** Hanya waktu dan jumlah, tanpa isi gambar. Dipakai untuk log. */
    data class InfoFrame(
        /** Waktu tiba frame yang dipakai, dihitung dari [mulai]; null jika tidak ada frame. */
        val tibaMs: Long?,
        /** Waktu keputusan diambil, dihitung dari [mulai]. */
        val selesaiMs: Long,
        val jumlahFrame: Int,
        val cadanganDipakai: Boolean,
    )

    sealed interface Keputusan<out F> {
        /** Frame dipakai. Pemanggil wajib menutupnya setelah selesai. */
        data class Pakai<out F>(val frame: F, val info: InfoFrame) : Keputusan<F>

        /** Panggil [periksa] lagi setelah [setelahMs]. */
        data class PeriksaLagi(val setelahMs: Long) : Keputusan<Nothing>

        /** Paksa layar virtual menghasilkan frame baru, lalu panggil [periksa] lagi setelah [setelahMs]. */
        data class PaksaFrameBaru(val setelahMs: Long) : Keputusan<Nothing>

        data class Gagal(val info: InfoFrame) : Keputusan<Nothing>

        /** Tidak ada permintaan yang sedang berjalan, misalnya karena sudah selesai lebih dulu. */
        data object TidakMenunggu : Keputusan<Nothing>
    }

    private var menunggu = false
    private var mulaiMs = 0L
    private var batasMs = 0L
    private var cadanganDipakai = false
    private var frame: F? = null
    private var tibaMs = 0L
    private var jumlahFrame = 0

    val sedangMenunggu: Boolean get() = menunggu

    /** Memulai satu permintaan. Dipanggil tepat setelah tombol cek disembunyikan. */
    fun mulai(): Keputusan<F> {
        frame?.close()
        frame = null
        menunggu = true
        mulaiMs = jam.sekarangMs()
        batasMs = mulaiMs + batasTungguMs
        cadanganDipakai = false
        jumlahFrame = 0
        return Keputusan.PeriksaLagi(jedaMinMs)
    }

    /**
     * Dipanggil setiap pendengar ImageReader berjalan, dengan hasil acquireLatestImage (bisa null).
     * Mengembalikan keputusan Pakai jika frame ini langsung dipakai.
     */
    fun frameMasuk(baru: F?): Keputusan.Pakai<F>? {
        // Panggilan tanpa frame baru: frame yang sudah tersimpan tetap dipertahankan.
        if (baru == null) return null
        if (!menunggu) {
            baru.close()
            return null
        }
        frame?.close()
        frame = baru
        tibaMs = jam.sekarangMs() - mulaiMs
        jumlahFrame++
        // Jeda minimum sudah lewat: frame ini sudah pasti digambar setelah tombol hilang.
        return if (tibaMs >= jedaMinMs) pakai() else null
    }

    /** Dipanggil oleh timer sesuai keputusan PeriksaLagi atau PaksaFrameBaru sebelumnya. */
    fun periksa(): Keputusan<F> {
        if (!menunggu) return Keputusan.TidakMenunggu
        val sekarang = jam.sekarangMs()
        val berjalan = sekarang - mulaiMs
        if (berjalan < jedaMinMs) return Keputusan.PeriksaLagi(jedaMinMs - berjalan)
        if (frame != null) return pakai()
        if (sekarang < batasMs) return Keputusan.PeriksaLagi(batasMs - sekarang)
        if (!cadanganDipakai) {
            cadanganDipakai = true
            batasMs = sekarang + batasCadanganMs
            return Keputusan.PaksaFrameBaru(batasCadanganMs)
        }
        val info = InfoFrame(null, berjalan, jumlahFrame, cadanganDipakai)
        selesai()
        return Keputusan.Gagal(info)
    }

    /**
     * Membatalkan permintaan yang sedang berjalan (layar diputar atau sesi dihentikan) dan
     * menutup frame yang tersimpan. Mengembalikan true jika memang ada permintaan yang dibatalkan.
     */
    fun batalkan(): Boolean {
        if (!menunggu) return false
        frame?.close()
        selesai()
        return true
    }

    private fun pakai(): Keputusan.Pakai<F> {
        val dipakai = checkNotNull(frame)
        val info = InfoFrame(tibaMs, jam.sekarangMs() - mulaiMs, jumlahFrame, cadanganDipakai)
        // Kepemilikan frame pindah ke pemanggil, jadi tidak ditutup di sini.
        frame = null
        selesai()
        return Keputusan.Pakai(dipakai, info)
    }

    private fun selesai() {
        menunggu = false
        frame = null
    }

    companion object {
        /** Tombol disembunyikan tanpa animasi; jeda ini memberi waktu beberapa frame untuk menggambar ulang layar. */
        const val JEDA_MIN_MS = 150L
        const val BATAS_TUNGGU_MS = 1000L
        const val BATAS_CADANGAN_MS = 300L
    }
}
