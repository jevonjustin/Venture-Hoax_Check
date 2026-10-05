package com.example.cekhoaks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

/**
 * Bagian "Pengaturan server" di layar utama: kolom alamat, tombol uji koneksi, dan pilihan
 * cepat untuk koneksi USB.
 *
 * @param mintaFokus setiap kali nilainya naik, layar digulir sampai bagian ini terlihat.
 */
@Composable
fun BagianPengaturanServer(
    urlMasukan: String,
    urlTersimpan: String,
    statusUji: StatusUji,
    mintaFokus: Int,
    onUrlBerubah: (String) -> Unit,
    onUji: () -> Unit,
    onPakaiUsb: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val penggulir = remember { BringIntoViewRequester() }
    // LaunchedEffect menjalankan blok ini setiap kali nilai mintaFokus berubah.
    LaunchedEffect(mintaFokus) {
        if (mintaFokus > 0) penggulir.bringIntoView()
    }

    Card(modifier = modifier.fillMaxWidth().bringIntoViewRequester(penggulir)) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.server_judul),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = stringResource(R.string.server_penjelasan),
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedTextField(
                value = urlMasukan,
                onValueChange = onUrlBerubah,
                label = { Text(stringResource(R.string.server_label_url)) },
                placeholder = { Text(stringResource(R.string.server_contoh_url)) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { onUji() }),
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(
                    onClick = onUji,
                    enabled = statusUji != StatusUji.Menguji,
                    modifier = Modifier.weight(1f).heightIn(min = 52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = colorResource(R.color.utama)),
                ) {
                    Text(stringResource(R.string.server_tombol_uji))
                }
                OutlinedButton(
                    onClick = onPakaiUsb,
                    modifier = Modifier.weight(1f).heightIn(min = 52.dp),
                ) {
                    Text(stringResource(R.string.server_tombol_usb))
                }
            }
            if (urlMasukan == PengaturanServer.URL_USB) {
                Text(
                    text = stringResource(R.string.server_petunjuk_usb),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            HasilUji(statusUji)
            Text(
                text = if (urlTersimpan.isBlank()) {
                    stringResource(R.string.server_belum_diatur)
                } else {
                    stringResource(R.string.server_tersimpan, urlTersimpan)
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun HasilUji(statusUji: StatusUji) {
    when (statusUji) {
        StatusUji.Diam -> Unit
        StatusUji.Menguji -> Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(18.dp),
                strokeWidth = 2.dp,
                color = colorResource(R.color.utama),
            )
            Text(stringResource(R.string.server_menguji), style = MaterialTheme.typography.bodyMedium)
        }
        is StatusUji.Tersambung -> Text(
            text = stringResource(R.string.server_tersambung, statusUji.versi),
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Bold,
            color = colorResource(R.color.utama),
        )
        is StatusUji.Gagal -> Text(
            text = stringResource(statusUji.pesan),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error,
        )
    }
}
