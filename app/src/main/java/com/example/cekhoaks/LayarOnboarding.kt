package com.example.cekhoaks

import androidx.activity.compose.BackHandler
import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

private class HalamanOnboarding(
    @param:DrawableRes val ikon: Int,
    @param:StringRes val judul: Int,
    @param:StringRes val isi: Int,
    val rataTengah: Boolean,
)

private val daftarHalaman = listOf(
    HalamanOnboarding(R.drawable.ic_onboarding_tanya, R.string.onboarding_1_judul, R.string.onboarding_1_isi, true),
    HalamanOnboarding(R.drawable.ic_onboarding_pilih, R.string.onboarding_2_judul, R.string.onboarding_2_isi, true),
    HalamanOnboarding(R.drawable.ic_onboarding_hasil, R.string.onboarding_3_judul, R.string.onboarding_3_isi, true),
    // Halaman privasi berupa daftar butir, jadi rata kiri agar mudah dibaca.
    HalamanOnboarding(R.drawable.ic_onboarding_privasi, R.string.onboarding_4_judul, R.string.onboarding_4_isi, false),
)

/**
 * Layar pengantar 4 halaman. [onSelesai] dipanggil saat "Mulai" atau "Lewati" diketuk;
 * [onTutup] dipanggil saat Back ditekan di halaman pertama setelah dibuka ulang dari layar utama.
 */
@Composable
fun LayarOnboarding(
    dibukaUlang: Boolean,
    onSelesai: () -> Unit,
    onTutup: () -> Unit,
) {
    val jumlah = daftarHalaman.size
    val pagerState = rememberPagerState(pageCount = { jumlah })
    val scope = rememberCoroutineScope()
    val halaman = pagerState.currentPage
    val terakhir = halaman == jumlah - 1

    // Back mundur satu halaman; di halaman pertama hanya ditangani bila dibuka ulang dari layar utama.
    // Saat pertama kali dipakai, Back di halaman pertama keluar dari aplikasi seperti biasa.
    BackHandler(enabled = halaman > 0 || dibukaUlang) {
        if (halaman > 0) {
            scope.launch { pagerState.animateScrollToPage(halaman - 1) }
        } else {
            onTutup()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(colorResource(R.color.latar_lembar))
            .systemBarsPadding()
            .padding(start = 32.dp, end = 32.dp, top = 24.dp, bottom = 24.dp),
    ) {
        Box(modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            if (!terakhir) {
                TextButton(
                    onClick = onSelesai,
                    modifier = Modifier.align(Alignment.CenterEnd).heightIn(min = 48.dp),
                ) {
                    Text(
                        text = stringResource(R.string.onboarding_lewati),
                        color = colorResource(R.color.teks_redup),
                        fontSize = 15.sp,
                    )
                }
            }
        }

        HorizontalPager(
            state = pagerState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
        ) { indeks ->
            IsiHalaman(daftarHalaman[indeks])
        }

        Spacer(Modifier.height(16.dp))
        IndikatorTitik(halaman = halaman, jumlah = jumlah, modifier = Modifier.align(Alignment.CenterHorizontally))
        Spacer(Modifier.height(24.dp))

        Button(
            onClick = {
                if (terakhir) onSelesai() else scope.launch { pagerState.animateScrollToPage(halaman + 1) }
            },
            modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp),
            shape = RoundedCornerShape(27.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = colorResource(R.color.navy),
                contentColor = Color.White,
            ),
        ) {
            Text(
                text = stringResource(if (terakhir) R.string.onboarding_mulai else R.string.onboarding_lanjut),
                fontSize = 16.sp,
                fontWeight = FontWeight.ExtraBold,
            )
        }
    }
}

@Composable
private fun IsiHalaman(halaman: HalamanOnboarding) {
    // verticalScroll supaya isi tetap terbaca penuh pada ukuran huruf besar.
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = if (halaman.rataTengah) Alignment.CenterHorizontally else Alignment.Start,
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.CenterHorizontally)
                .size(120.dp)
                .clip(CircleShape)
                .background(colorResource(R.color.navy_lembut)),
            contentAlignment = Alignment.Center,
        ) {
            // Gambar hiasan: maknanya sudah ada di judul dan isi.
            Image(
                painter = painterResource(halaman.ikon),
                contentDescription = null,
                modifier = Modifier.size(56.dp),
            )
        }
        Spacer(Modifier.height(28.dp))
        val rata = if (halaman.rataTengah) TextAlign.Center else TextAlign.Start
        Text(
            text = stringResource(halaman.judul),
            fontSize = 26.sp,
            lineHeight = 32.sp,
            fontWeight = FontWeight.ExtraBold,
            color = colorResource(R.color.teks_judul),
            textAlign = rata,
        )
        Spacer(Modifier.height(14.dp))
        Text(
            text = stringResource(halaman.isi),
            fontSize = 15.sp,
            lineHeight = 22.sp,
            color = colorResource(R.color.teks_isi),
            textAlign = rata,
        )
    }
}

@Composable
private fun IndikatorTitik(halaman: Int, jumlah: Int, modifier: Modifier = Modifier) {
    val deskripsi = stringResource(R.string.onboarding_halaman_deskripsi, halaman + 1, jumlah)
    Row(
        modifier = modifier.clearAndSetSemantics { contentDescription = deskripsi },
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        repeat(jumlah) { i ->
            val aktif = i == halaman
            Box(
                modifier = Modifier
                    .width(if (aktif) 22.dp else 8.dp)
                    .height(8.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(
                        colorResource(if (aktif) R.color.navy else R.color.tombol_nonaktif_latar),
                    ),
            )
        }
    }
}
