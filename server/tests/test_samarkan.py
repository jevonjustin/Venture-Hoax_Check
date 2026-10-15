"""Penyamaran data pribadi: nomor, email, akun, baris deret akun, dan pemetaan kutipan kembali ke teks asli."""

import pytest

from app.pipeline import samarkan
from app.pipeline.samarkan import apakah_baris_akun, kutipan_ke_asli, samarkan as samarkan_teks

# --- nomor telepon ---


@pytest.mark.parametrize("nomor", [
    "+62 812-3456-7890", "0812 3456 7890", "081234567890", "+6281234567890", "0812.3456.7890", "0813-1234-5678",
    "62 812 3456 7890", "+1 415 555 2671",
])
def test_nomor_telepon_disamarkan(nomor):
    assert samarkan_teks(f"Hubungi {nomor} segera") == "Hubungi [NOMOR] segera"


def test_nomor_terpotong_di_tepi_layar_ikut_disamarkan():
    assert "[NOMOR]" in samarkan_teks("+62 82\n3\n-Mila")


@pytest.mark.parametrize("teks", [
    "12 Oktober 2026", "08.30 WIB", "pukul 08.30\n14.15", "Rp 500.000", "Rp500.000", "Rp1.500.000.000",
    "700 kepala desa", "Tahun 2025", "08-08-2026", "10.000 orang", "1.234.567 pengguna", "tanggal 17/08/2026",
    "Sebanyak 12 orang dirawat", "kode pos 40115", "Jumlah korban 081 orang", "pada 12.16 dan 13.27 dan 14.15",
    "Dana Rp 11.000.000 dikembalikan", "11JT", "COVID-19 tapi butuh verifikasi 2 langkah",
])
def test_angka_biasa_tidak_disamarkan(teks):
    assert samarkan_teks(teks) == teks


# --- email, akun, tautan, nama ---


def test_email_dan_akun_disamarkan():
    assert samarkan_teks("kirim ke tolong.saya@mail.co.id atau @polres_merangin") == "kirim ke [EMAIL] atau [AKUN]"


def test_tautan_dan_nama_orang_tidak_disamarkan():
    teks = "Dokter Mila meminta klik bit.ly/abc123 atau https://x.weeblysite.com/ Pak Agus"
    assert samarkan_teks(teks) == teks


def test_nomor_di_dalam_tautan_tidak_disamarkan():
    teks = "buka https://wa.me/6285923171287 sekarang"
    assert samarkan_teks(teks) == teks


def test_isi_pesan_tidak_diubah():
    teks = "Selamat siang kak, kami dari kasir indomart minta tolong sebentar, ada kode 6 angka kak"
    assert samarkan_teks(teks) == teks


# --- baris akun tanpa @ ---


@pytest.mark.parametrize("baris", [
    "humaspolresmerangin fpolresmerangin polresmerangin6 humaspolresmerangin",
    "polresmerangin6",
    "user_name.official",
    "humaspolresmerangin",  # satu token tanpa angka tidak cukup; lihat tes negatif di bawah
])
def test_baris_akun_ditandai(baris):
    if baris == "humaspolresmerangin":
        assert apakah_baris_akun(baris) is False
    else:
        assert apakah_baris_akun(baris) is True


@pytest.mark.parametrize("baris", [
    "pemberitahuan selanjutnya",
    "kemungkinan diberlakukan",
    "perkembangan selanjutnya diumumkan pemerintah",
    "kementerian pertahanan republik indonesia",
    "pemerintah daerah mengumumkan kebijakan",
    "mengkonfirmasikan keberangkatan keberangkatan",
    "Halo, apa kabar",
    "Rp500.000 Rp1.000.000",
    "12.16",
    "wa.me",
    "bit.ly",
    "Aktifkan autentikasi dua faktor (2FA)",
    "COVID-19",
    "",
    # dari 18 gambar uji: pernah terkena aturan yang terlalu longgar
    "senggang Anda tanpa mengganggu",
    "1.OPERATOR",
    "15DESEMBER2020",
    "selengkapnya.",
    "vocazine.",
    "saya.",
    "disita.",
    "kemungkinan pemberlakuan selanjutnya pemberitahuan",
    "pemberitahuan pemberitahuan",
])
def test_kalimat_isi_huruf_kecil_dan_teks_biasa_bukan_baris_akun(baris):
    assert apakah_baris_akun(baris) is False


def test_deret_akun_disamarkan_per_token():
    teks = "Pilih kata sandi kuat\nhumaspolresmerangin fpolresmerangin polresmerangin6 humaspolresmerangin"
    assert samarkan_teks(teks) == "Pilih kata sandi kuat\n[AKUN] [AKUN] [AKUN] [AKUN]"


# --- kutipan_ke_asli ---

ASLI = "Hubungi +62 812-3456-7890 atau tolong.saya@mail.co.id\nSegera kirim kode ke @polres_merangin sebelum dihapus"
SAMAR = samarkan_teks(ASLI)


def test_kutipan_biasa_dipetakan_ke_teks_asli():
    assert kutipan_ke_asli("segera kirim kode", SAMAR, ASLI) == "Segera kirim kode"
    assert kutipan_ke_asli("sebelum dihapus", SAMAR, ASLI) == "sebelum dihapus"


def test_kutipan_bertoken_dipetakan_kembali_ke_data_asli():
    assert kutipan_ke_asli("Hubungi [NOMOR] atau [EMAIL]", SAMAR, ASLI) == "Hubungi +62 812-3456-7890 atau tolong.saya@mail.co.id"
    assert kutipan_ke_asli("kode ke [AKUN] sebelum", SAMAR, ASLI) == "kode ke @polres_merangin sebelum"


def test_kutipan_palsu_ditolak():
    assert kutipan_ke_asli("segera transfer uang sekarang", SAMAR, ASLI) is None
    assert kutipan_ke_asli("", SAMAR, ASLI) is None
    assert kutipan_ke_asli("   ", SAMAR, ASLI) is None


def test_kutipan_yang_ada_di_teks_samar_tetapi_tidak_di_asli_ditolak():
    # token [NOMOR] ada di teks samar, tetapi kutipan bukan di tempat nomor sungguhan berada
    assert kutipan_ke_asli("[NOMOR] [NOMOR]", SAMAR + " [NOMOR] [NOMOR]", ASLI) is None


def test_kutipan_tidak_peduli_huruf_besar_dan_spasi():
    assert kutipan_ke_asli("SEGERA   KIRIM\nKODE", SAMAR, ASLI) == "Segera kirim kode"


def test_token_penyamaran_konstan():
    assert (samarkan.TOKEN_NOMOR, samarkan.TOKEN_EMAIL, samarkan.TOKEN_AKUN) == ("[NOMOR]", "[EMAIL]", "[AKUN]")
