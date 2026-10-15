"""Ciri permintaan_data_rahasia: permintaan kode, data rahasia, atau uang. Kalimat larangan tidak boleh ditandai."""

import pytest

from app.pipeline import ciri, template
from app.skema import ID_CIRI_TERKUNCI
from test_template import cari_pelanggaran

ID = "permintaan_data_rahasia"

# Teks mentah gambar uji (disalin dari hasil baca; hanya untuk tes).
GAMBAR_01 = (
    "Diteruskan\n.Selamat siang kak ,Maaf ganggu,kami dari kasir\nindomart, minta tolong sebentar,tadi ada\n"
    "pelanggan kami beli voucher game,kami salah\ninvut nomor jadi sms nya terikirim ke nomor kakak\n"
    "Sms dari whatsapp yg ada tulisan thailand nya\nkak,karna ada kode 6 angka kak untuk kode\n"
    "voucher game fishinggo kk\nBisa dikirim SMS ny kak\n12.16\n"
    "Maaf kk kami tadi salah invut no jadi terkirim ke no\nkk kode game kami itu msk melalui SMS Wa\n"
    "bisniss ada kode game kami kami 6angka tlng\nkerja sama nya kk"
)
GAMBAR_06 = (
    "BSI PROSE...\nOK saya tunggu, sudah lebih\ndari 2 menit\nAlya named the group BSI PROSES\nREFFUND 11JT.\n"
    "Alya\nMaaf kak bnyak transaksi\nsoalnya\nOK perlu berapa menit lagi\nAlya\nMaaf kak ini qris lagi\n"
    "bermsalah bisa unlock ke\noVo\nDari tadi kami cek ga ada\npemberitahuannya yg masuk"
)
GAMBAR_08 = (
    "Saya mau buat grup INFO UPDATE\nAda yang bisa dibantu dok?\nCOVID-19 tapi butu verifikasi 2 langkah\n"
    "agar menghindari yang tidak di inginkan d...\nKodenya sudah masuk teh\nKode apa ya dok\n"
    "COVID-19 tapi butu verifikasi 2\nlangkah agar menghindari yang\ntidak di inginkan dan menjaga\n"
    "keamanan grup jadi nanti klw ada\nkode masuk disitu lewat sms kirim\nkesiniya. A\nCek di pesan SMS"
)
GAMBAR_07 = (
    "Waspada Akun Facebook\nDiretas, Modus Pinjam\nUang Via Inbox\nLangkah yang harus dilakukan\njika akun diretas\n"
    "Buat pengumuman di media sosial\nlainnya tentang akun Sobat\nyang diretas\nLog in kembali dan reset password\n"
    "menggunakan forgot password\nPilih kata sandi kuat\nyang sulit ditebak\nAktifkan autentikasi\n"
    "dua faktor (2FA)\nhumaspolresmerangin\nfpolresmerangin\npolresmerangin6\nhumaspolresmerangin"
)


def hasil(teks: str):
    return {c.id: c for c in ciri.deteksi_regex(teks)}.get(ID)


def test_id_terkunci_memuat_ciri_baru_dan_template_lengkap():
    assert ID in ID_CIRI_TERKUNCI and ID in ciri.ID_BISA_DITANDAI and len(ID_CIRI_TERKUNCI) == 9
    assert template.NAMA[ID] == "Permintaan kode, data rahasia, atau uang"
    assert cari_pelanggaran(template.PENJELASAN[ID]) == [] and cari_pelanggaran(template.NAMA[ID]) == []


@pytest.mark.parametrize("nama,teks", [("01", GAMBAR_01), ("06", GAMBAR_06), ("08", GAMBAR_08)])
def test_gambar_penipuan_ditandai(nama, teks):
    c = hasil(teks)
    assert c is not None and c.kekuatan == "kuat" and c.bukti, nama


def test_bukti_gambar_08_dan_06_menunjuk_permintaan():
    assert any("verifikasi 2 langkah" in b.lower() or "kode masuk" in b.lower() for b in hasil(GAMBAR_08).bukti)
    assert any("unlock" in b.lower() or "qris" in b.lower() or "reffund" in b.lower() for b in hasil(GAMBAR_06).bukti)


def test_gambar_07_infografis_edukasi_2fa_tidak_ditandai():
    assert hasil(GAMBAR_07) is None


@pytest.mark.parametrize("teks", [
    "kirimkan kode yang masuk ke SMS kamu",
    "Tolong sebutkan kode OTP yang baru masuk",
    "Boleh minta kodenya kak?",
    "Masukkan PIN di link berikut agar akun aktif",
    "Silakan kirimkan kata sandi akun Anda untuk verifikasi",
    "Mohon kirim kode verifikasi 6 digit yang Anda terima",
    "Untuk cairkan hadiah wajib transfer biaya admin Rp 250.000 dulu",
    "Dana refund dialihkan ke DANA karena QRIS error",
    "Anda harus bayar denda 8% di awal sebelum proses transfer",
])
def test_pola_permintaan_kuat_ditandai(teks):
    assert hasil(teks) is not None, teks


@pytest.mark.parametrize("teks", [
    "JANGAN BERIKAN kode OTP kepada siapa pun!",
    "Jangan bagikan PIN dan kata sandi Anda ke orang lain.",
    "Waspada penipuan: pelaku meminta kode OTP lewat telepon.",
    "Pihak bank tidak pernah meminta kode OTP atau PIN nasabah.",
    "Kode OTP bersifat rahasia dan dilarang diberikan kepada siapa pun, termasuk pihak bank.",
    "Hindari mengirimkan kode verifikasi ke nomor tidak dikenal.",
    "Aktifkan autentikasi dua faktor (2FA) untuk melindungi akun.",
    "Kami tidak akan pernah menanyakan kata sandi atau PIN Anda.",
    "Kirim pin lokasi rumah ke grup ya",
    "Berita hari ini membahas harga cabai dan beras di pasar induk.",
    "Bagikan kode QR ini ke teman",
    "Reset password menggunakan forgot password lalu pilih kata sandi kuat",
])
def test_kalimat_larangan_edukasi_dan_teks_biasa_tidak_ditandai(teks):
    assert hasil(teks) is None, teks


def test_larangan_hanya_berlaku_di_dekat_kecocokan():
    teks = "Jangan percaya begitu saja. " + "Lorem ipsum dolor sit amet " * 5 + "Tolong kirimkan kode OTP sekarang."
    assert hasil(teks) is not None


def test_larangan_di_kalimat_lain_tidak_membatalkan_permintaan():
    assert hasil("Jangan panik ya. Tolong sebutkan kode OTP sekarang.") is not None


# ----- Sesi 5.5: larangan hanya berlaku dalam klausa yang sama -----


@pytest.mark.parametrize("teks", [
    "Mohon kirimkan kode tersebut, jangan diberikan ke orang lain",
    "Jangan kasih tau siapa-siapa, tolong kirim OTP-nya ke saya",
    "Jangan lupa kirim kode OTP-nya ya",
    "Jangan ragu, kirimkan kodenya sekarang",
    "Jangan sampai lupa kirimkan kode verifikasinya segera",
    "Jangan sungkan, sebutkan kode OTP yang masuk",
    "Jangan sampai telat, kirim kodenya sekarang",
    "Jangan lama-lama kirim kode OTP nya kak",
    "Jangan kasih tau siapa-siapa\ntolong kirim OTP-nya ke saya",
])
def test_larangan_di_klausa_lain_atau_kata_pendorong_tidak_membatalkan_permintaan(teks):
    assert hasil(teks) is not None, teks


@pytest.mark.parametrize("teks", [
    "Waspada, bank tidak pernah meminta kode OTP",
    "JANGAN BERIKAN kode OTP kepada siapa pun",
    "Jangan sekali-kali mau memberikan kode OTP ke siapa pun",
    "Kode OTP ini rahasia. Jangan berikan kode OTP ke siapa pun.",
])
def test_larangan_di_klausa_yang_sama_tetap_membatalkan(teks):
    assert hasil(teks) is None, teks
