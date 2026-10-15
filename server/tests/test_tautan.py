"""Penggabungan tautan yang terpecah lintas baris."""

import pytest

from app.pipeline.tautan import gabung_tautan_terpecah as gabung


def test_gambar_05_https_dan_domain_di_baris_berikutnya_digabung():
    teks = "Tekan tautan: https://\nkonfirmasipenonaktifan2025.weeblysite.com/\nUntuk melakukan verifikasi"
    assert gabung(teks) == "Tekan tautan: https://konfirmasipenonaktifan2025.weeblysite.com/\nUntuk melakukan verifikasi"


@pytest.mark.parametrize("teks,hasil", [
    ("Buka http://\ncontoh.co.id/promo", "Buka http://contoh.co.id/promo"),
    ("Kunjungi www.\ncontoh.com", "Kunjungi www.contoh.com"),
    ("Klik https://\nbit.ly/abc123 sekarang", "Klik https://bit.ly/abc123\nsekarang"),
    ("Klik https://\n/halaman/promo", "Klik https://" + "/halaman/promo"),
])
def test_potongan_url_belum_selesai_digabung_dengan_domain_atau_jalur(teks, hasil):
    assert gabung(teks) == hasil


@pytest.mark.parametrize("teks", [
    "Silakan buka https://\nSilakan klik tautan di atas",
    "Tautannya ada di https://\nkomentar pertama",
    "Gunakan https://\n12 Oktober 2026",
    "https://",
    "https://\n",
    "Teks biasa\nbaris kedua.com",
    "Lihat contoh.com\nuntuk keterangan",
    "Kata-kata https://contoh.com/halaman\nlanjutan kalimat",
    "Ketik www.\nHalo semua",
])
def test_https_diikuti_kalimat_biasa_atau_url_lengkap_tidak_digabung(teks):
    assert gabung(teks) == teks


def test_baris_domain_tanpa_potongan_di_atasnya_tidak_disentuh():
    teks = "Situs resmi\nkemenkes.go.id\nHubungi kami"
    assert gabung(teks) == teks


def test_beberapa_tautan_terpecah_sekaligus():
    teks = "A https://\nsatu.com\nB https://\ndua.id/x"
    assert gabung(teks) == "A https://satu.com\nB https://dua.id/x"


def test_teks_kosong_dan_satu_baris():
    assert gabung("") == ""
    assert gabung("tanpa tautan") == "tanpa tautan"
