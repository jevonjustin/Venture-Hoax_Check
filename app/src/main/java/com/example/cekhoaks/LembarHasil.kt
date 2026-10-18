package com.example.cekhoaks

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Typeface
import android.text.Spannable
import android.text.SpannableString
import android.text.style.BackgroundColorSpan
import android.text.style.StyleSpan
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.annotation.ColorRes
import androidx.core.content.ContextCompat
import androidx.core.net.toUri
import androidx.core.view.ViewCompat
import androidx.core.view.isEmpty
import androidx.core.widget.ImageViewCompat

/**
 * Lembar hasil: banner tingkat, keterangan pemeriksaan terbatas, ringkasan, inti pesan, artikel
 * cek fakta, ciri beserta bukti, perbandingan dengan penilaian awal, teks yang terbaca, dan tips.
 * Isinya digulir; tombol Tutup tetap di bawah. Back dan ketukan di lapisan gelap sama dengan Tutup.
 *
 * Lembar tidak menyimpan apa pun selain [hasil] dan [penilaian] yang diberikan pemiliknya.
 *
 * @param penilaian penilaian awal pengguna, atau [Penilaian.DILEWATI]; hanya untuk perbandingan.
 * @param onTutup dipanggil saat Tutup, Back, lapisan gelap, atau setelah tautan artikel dibuka.
 *   Lembar tidak menutup dirinya; pemilik memanggil [tutup].
 */
class LembarHasil(
    context: Context,
    windowManager: WindowManager,
    private val hasil: HasilAnalisis,
    private val penilaian: Penilaian,
    private val onTutup: () -> Unit,
) : LembarOverlay {

    private val jendela = JendelaLembar(
        context,
        windowManager,
        context.getString(R.string.hasil_tutup),
        onKembali = { tutupDiminta() },
    )
    private val ctx get() = jendela.context
    private var ditutup = false

    /** Memasang lembar. Hasilnya false bila sistem menolak. */
    fun tampilkan(): Boolean {
        val view = jendela.buatKerangka(
            R.drawable.bg_lembar_hasil,
            R.layout.overlay_lembar_hasil_isi,
            R.layout.overlay_lembar_hasil_kaki,
        )
        val tampil = tampilanTingkat(hasil.tingkat)

        isiBanner(view, tampil)
        isiPemeriksaanTerbatas(view)
        isiChip(view)
        isiIntiPesan(view)
        isiArtikel(view)
        isiCiri(view, tampil.palet)
        isiPerbandingan(view, tampil)
        isiTeksTerbaca(view)
        view.findViewById<TextView>(R.id.hasil_tips_isi).setText(tampil.tips)

        // Judul bagian ditandai sebagai heading agar pembaca layar bisa melompat antar-bagian.
        listOf(
            R.id.hasil_terbatas_judul, R.id.hasil_inti_judul, R.id.hasil_artikel_judul, R.id.hasil_ciri_judul,
            R.id.hasil_banding_judul, R.id.hasil_teks_judul, R.id.hasil_tips_judul,
        ).forEach { ViewCompat.setAccessibilityHeading(view.findViewById(it), true) }

        view.findViewById<Button>(R.id.hasil_tutup).setOnClickListener { tutupDiminta() }

        if (!jendela.pasang(view)) {
            ditutup = true
            return false
        }
        return true
    }

    private fun warna(@ColorRes res: Int) = ContextCompat.getColor(ctx, res)

    private fun isiBanner(view: View, tampil: TampilanTingkat) {
        val palet = tampil.palet
        view.findViewById<View>(R.id.hasil_banner).backgroundTintList = ColorStateList.valueOf(warna(palet.bg))
        val ikon = view.findViewById<ImageView>(R.id.hasil_banner_ikon)
        ikon.setImageResource(
            when (tampil.ikon) {
                IkonTingkat.SEGITIGA_SERU -> R.drawable.ic_tingkat_segitiga
                IkonTingkat.LINGKARAN_SERU -> R.drawable.ic_tingkat_lingkaran_seru
                IkonTingkat.LINGKARAN_INFO -> R.drawable.ic_tingkat_info
            },
        )
        ImageViewCompat.setImageTintList(ikon, ColorStateList.valueOf(warna(palet.fg)))
        view.findViewById<TextView>(R.id.hasil_banner_label).setTextColor(warna(palet.fg))
        view.findViewById<TextView>(R.id.hasil_banner_judul).apply {
            setText(tampil.judul)
            setTextColor(warna(palet.fg))
        }
        view.findViewById<TextView>(R.id.hasil_banner_keterangan).apply {
            setText(tampil.keterangan)
            setTextColor(warna(palet.fg))
        }
    }

    private fun isiPemeriksaanTerbatas(view: View) {
        if (hasil.pemeriksaanTerbatas.isEmpty()) return
        view.findViewById<View>(R.id.hasil_terbatas).visibility = View.VISIBLE
        val daftar = view.findViewById<LinearLayout>(R.id.hasil_terbatas_daftar)
        for (kalimat in kalimatPemeriksaanTerbatas(hasil.pemeriksaanTerbatas)) {
            daftar.addView(buatTeks(ctx.getString(kalimat), 14f, R.color.teks_isi).apply { setPadding(0, dp(6), 0, 0) })
        }
        view.findViewById<TextView>(R.id.hasil_terbatas_arti).setText(artiPemeriksaanTerbatas(hasil.tingkat))
    }

    private fun isiChip(view: View) {
        val chip = view.findViewById<TataLetakAlir>(R.id.hasil_chip)
        chip.jarakHorizontal = dp(8)
        chip.jarakVertikal = dp(8)
        chip.addView(
            buatChip(
                if (hasil.ciri.isEmpty()) ctx.getString(R.string.hasil_chip_tanpa_ciri)
                else ctx.getString(R.string.hasil_chip_ciri, hasil.ciri.size),
            ),
        )
        chip.addView(
            buatChip(
                when {
                    cekFaktaTerbatas(hasil.pemeriksaanTerbatas) -> ctx.getString(R.string.hasil_chip_cek_fakta_terbatas)
                    hasil.cekFakta.isEmpty() -> ctx.getString(R.string.hasil_chip_tanpa_artikel)
                    else -> ctx.getString(R.string.hasil_chip_artikel, hasil.cekFakta.size)
                },
            ),
        )
    }

    private fun buatChip(teks: String): TextView = buatTeks(teks, 14f, R.color.navy, tebal = true).apply {
        setBackgroundResource(R.drawable.bg_chip_ringkasan)
        setPadding(dp(12), dp(7), dp(12), dp(7))
    }

    private fun isiIntiPesan(view: View) {
        val klaim = hasil.klaimUtama?.trim()
        if (klaim.isNullOrEmpty()) return
        view.findViewById<View>(R.id.hasil_inti).visibility = View.VISIBLE
        view.findViewById<TextView>(R.id.hasil_inti_isi).text = ctx.getString(R.string.hasil_kutipan, klaim)
    }

    private fun isiArtikel(view: View) {
        if (hasil.cekFakta.isEmpty()) return
        view.findViewById<View>(R.id.hasil_artikel).visibility = View.VISIBLE
        val daftar = view.findViewById<LinearLayout>(R.id.hasil_artikel_daftar)
        val namaBulan = ctx.resources.getStringArray(R.array.bulan_nama).toList()
        for (artikel in hasil.cekFakta) {
            val item = LayoutInflater.from(ctx).inflate(R.layout.item_artikel, daftar, false)

            val label = labelArtikel(artikel.label)
            item.findViewById<TextView>(R.id.artikel_label).apply {
                setText(label.teks)
                setTextColor(warna(label.warnaTeks))
                backgroundTintList = ColorStateList.valueOf(warna(label.latar))
            }
            item.findViewById<TextView>(R.id.artikel_judul).text = artikel.judul
            val tanggal = formatTanggal(artikel.tanggal, namaBulan)
            item.findViewById<TextView>(R.id.artikel_sumber).text =
                if (tanggal != null) ctx.getString(R.string.hasil_artikel_sumber_terbit, artikel.sumber, tanggal)
                else artikel.sumber

            // Tautan asli yang sudah mati diganti pencarian judul di web, dengan catatan.
            val tautanAktif = tautanAsliAktif(artikel)
            if (artikel.urlFormatLama) item.findViewById<View>(R.id.artikel_catatan).visibility = View.VISIBLE
            item.findViewById<Button>(R.id.artikel_tombol).apply {
                setText(if (tautanAktif) R.string.hasil_artikel_buka else R.string.hasil_artikel_cari)
                setOnClickListener { bukaTautan(tautanArtikel(artikel), artikel.judul) }
            }
            daftar.addView(item)
        }
    }

    /**
     * Membuka [url] di browser. Hanya http dan https yang dibuka; selain itu dialihkan ke
     * pencarian judul. Setelah browser dibuka, lembar ditutup lewat [onTutup] karena jendela
     * overlay akan menutupi browser bila dibiarkan.
     */
    private fun bukaTautan(url: String, judul: String) {
        val skema = url.toUri().scheme?.lowercase()
        val tujuan = if (skema == "http" || skema == "https") url else urlPencarian(judul)
        try {
            // Aplikasi yang punya izin tampil di atas aplikasi lain boleh membuka Activity dari service.
            ctx.startActivity(Intent(Intent.ACTION_VIEW, tujuan.toUri()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: ActivityNotFoundException) {
            Log.w(TAG, "Tidak ada aplikasi untuk membuka tautan", e)
            return
        } catch (e: SecurityException) {
            Log.w(TAG, "Tautan tidak boleh dibuka", e)
            return
        }
        tutupDiminta()
    }

    private fun isiCiri(view: View, palet: PaletTingkat) {
        if (hasil.ciri.isEmpty()) return
        view.findViewById<View>(R.id.hasil_ciri).visibility = View.VISIBLE
        val daftar = view.findViewById<LinearLayout>(R.id.hasil_ciri_daftar)
        for (ciri in hasil.ciri) {
            val item = LayoutInflater.from(ctx).inflate(R.layout.item_ciri, daftar, false)

            item.findViewById<View>(R.id.ciri_lencana).backgroundTintList = ColorStateList.valueOf(warna(palet.soft))
            ImageViewCompat.setImageTintList(
                item.findViewById(R.id.ciri_lencana_ikon),
                ColorStateList.valueOf(warna(palet.ink)),
            )
            item.findViewById<TextView>(R.id.ciri_nama).text = namaCiri(ciri.id, ciri.nama).teks(ctx::getString)
            teksKeyakinan(ciri.keyakinan)?.let { res ->
                item.findViewById<TextView>(R.id.ciri_keyakinan).apply {
                    setText(res)
                    visibility = View.VISIBLE
                }
            }

            val bukti = item.findViewById<TataLetakAlir>(R.id.ciri_bukti)
            bukti.jarakHorizontal = dp(6)
            bukti.jarakVertikal = dp(6)
            for (kutipan in ciri.bukti.map { it.trim() }.filter { it.isNotEmpty() }) {
                bukti.addView(
                    buatTeks(ctx.getString(R.string.hasil_kutipan, kutipan), 14f, R.color.teks_judul, tebal = true).apply {
                        setBackgroundResource(R.drawable.bg_chip_bukti)
                        setPadding(dp(10), dp(5), dp(10), dp(5))
                    },
                )
            }
            if (bukti.isEmpty()) bukti.visibility = View.GONE

            item.findViewById<TextView>(R.id.ciri_penjelasan).apply {
                text = ciri.penjelasan
                if (ciri.penjelasan.isBlank()) visibility = View.GONE
            }
            daftar.addView(item)
        }
    }

    private fun isiPerbandingan(view: View, tampil: TampilanTingkat) {
        val palet = tampil.palet
        view.findViewById<TextView>(R.id.hasil_banding_awal).setText(labelPenilaian(penilaian))
        view.findViewById<View>(R.id.hasil_banding_kotak_temuan).backgroundTintList =
            ColorStateList.valueOf(warna(palet.soft))
        view.findViewById<TextView>(R.id.hasil_banding_label_temuan).setTextColor(warna(palet.ink))
        view.findViewById<TextView>(R.id.hasil_banding_temuan).apply {
            setText(tampil.judul)
            setTextColor(warna(palet.ink))
        }
        view.findViewById<TextView>(R.id.hasil_banding_pesan).setText(pesanPerbandingan(penilaian, hasil))
    }

    private fun isiTeksTerbaca(view: View) {
        if (hasil.teksTerbaca.isBlank()) {
            view.findViewById<View>(R.id.hasil_teks).visibility = View.GONE
            return
        }
        // Sorotan = semua bukti dari semua ciri; bukti yang tidak ketemu di teks diabaikan diam-diam.
        val sorotan = cariSorotan(hasil.teksTerbaca, hasil.ciri.flatMap { it.bukti })
        val teks = SpannableString(hasil.teksTerbaca)
        for (rentang in sorotan) {
            val awal = rentang.first.coerceIn(0, teks.length)
            val akhir = (rentang.last + 1).coerceIn(awal, teks.length)
            if (akhir <= awal) continue
            teks.setSpan(BackgroundColorSpan(warna(R.color.chip_bukti)), awal, akhir, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
            teks.setSpan(StyleSpan(Typeface.BOLD), awal, akhir, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        view.findViewById<TextView>(R.id.hasil_teks_terbaca).text = teks
        if (sorotan.isEmpty()) view.findViewById<View>(R.id.hasil_teks_catatan).visibility = View.GONE

        // Awalnya terlipat. Deskripsi baris berganti sesuai tindakan berikutnya.
        val header = view.findViewById<View>(R.id.hasil_teks_header)
        val isi = view.findViewById<View>(R.id.hasil_teks_isi)
        val panah = view.findViewById<View>(R.id.hasil_teks_panah)
        header.contentDescription = ctx.getString(R.string.hasil_teks_tampilkan_deskripsi)
        header.setOnClickListener {
            val terbuka = isi.visibility != View.VISIBLE
            isi.visibility = if (terbuka) View.VISIBLE else View.GONE
            panah.rotation = if (terbuka) 180f else 0f
            header.contentDescription = ctx.getString(
                if (terbuka) R.string.hasil_teks_sembunyikan_deskripsi else R.string.hasil_teks_tampilkan_deskripsi,
            )
        }
    }

    private fun buatTeks(teks: String, ukuranSp: Float, @ColorRes warnaRes: Int, tebal: Boolean = false): TextView =
        TextView(ctx).apply {
            text = teks
            textSize = ukuranSp
            setTextColor(warna(warnaRes))
            if (tebal) setTypeface(typeface, Typeface.BOLD)
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        }

    private fun dp(nilai: Int) = (nilai * ctx.resources.displayMetrics.density).toInt()

    private fun tutupDiminta() {
        if (!ditutup) onTutup()
    }

    override fun tutup() {
        if (ditutup) return
        ditutup = true
        jendela.lepas()
    }

    private companion object {
        const val TAG = "CekHoaks"
    }
}
