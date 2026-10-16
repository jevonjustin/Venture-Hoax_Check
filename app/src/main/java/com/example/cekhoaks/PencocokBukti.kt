package com.example.cekhoaks

/**
 * Mencari letak setiap [bukti] di dalam [teks] untuk disorot.
 *
 * - Semua spasi, tab, dan baris baru (di teks maupun di bukti) tidak dianggap: yang dibandingkan
 *   hanya urutan karakter bukan-spasi. Server merapikan spasi bukti menjadi satu spasi, sedangkan
 *   teks asli bisa punya baris baru.
 * - Huruf besar/kecil dibedakan (case-sensitive), karena server menjamin bukti adalah potongan
 *   persis dari teks (selisihnya hanya spasi).
 * - Semua kemunculan dicari, termasuk yang berulang dan yang saling tumpang tindih.
 * - Hasilnya rentang indeks pada [teks] ASLI: dari karakter pertama sampai karakter terakhir
 *   yang cocok. Rentang yang tumpang tindih atau bersebelahan (selisih indeks 1) digabung, lalu
 *   diurutkan dari awal teks.
 * - Bukti kosong/kosong-spasi dan bukti yang tidak ketemu diabaikan; fungsi ini tidak melempar galat.
 */
fun cariSorotan(teks: String, bukti: List<String>): List<IntRange> {
    if (teks.isEmpty() || bukti.isEmpty()) return emptyList()

    // Teks tanpa spasi, beserta letak aslinya, dihitung sekali untuk semua bukti.
    val padat = StringBuilder(teks.length)
    val letakAsli = IntArray(teks.length)
    for (i in teks.indices) {
        val c = teks[i]
        if (!c.isWhitespace()) {
            letakAsli[padat.length] = i
            padat.append(c)
        }
    }
    val teksPadat = padat.toString()

    val semua = mutableListOf<IntRange>()
    for (b in bukti) {
        val kunci = b.filterNot { it.isWhitespace() }
        if (kunci.isEmpty()) continue
        var dari = teksPadat.indexOf(kunci)
        while (dari >= 0) {
            semua += letakAsli[dari]..letakAsli[dari + kunci.length - 1]
            dari = teksPadat.indexOf(kunci, dari + 1)
        }
    }
    return gabungkan(semua)
}

private fun gabungkan(rentang: List<IntRange>): List<IntRange> {
    if (rentang.isEmpty()) return emptyList()
    val urut = rentang.sortedWith(compareBy({ it.first }, { it.last }))
    val hasil = mutableListOf<IntRange>()
    var awal = urut[0].first
    var akhir = urut[0].last
    for (i in 1 until urut.size) {
        val r = urut[i]
        if (r.first <= akhir + 1) {
            if (r.last > akhir) akhir = r.last
        } else {
            hasil += awal..akhir
            awal = r.first
            akhir = r.last
        }
    }
    hasil += awal..akhir
    return hasil
}
