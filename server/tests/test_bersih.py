import dataclasses

import pytest

from app.konfigurasi import Pengaturan
from app.pipeline import bersih
from app.pipeline.tipe import BarisTeks

TINGGI = 1000
LEBAR = 500


def baris(teks: str, y: int, tinggi_baris: int = 20) -> BarisTeks:
    """Baris dengan tengah vertikal di piksel y (gambar setinggi TINGGI)."""
    a, b = y - tinggi_baris / 2, y + tinggi_baris / 2
    return BarisTeks(teks, ((0.0, a), (200.0, a), (200.0, b), (0.0, b)), 0.99)


def jalankan(*pasangan: tuple[str, int], varian=frozenset(), tinggi=TINGGI, cfg=None):
    return bersih.bersihkan([baris(t, y) for t, y in pasangan], LEBAR, tinggi, varian, cfg)


def alasan(hasil) -> dict[str, str]:
    return {b.teks: b.alasan for b in hasil.dibuang}


def test_bilah_status_di_pita_atas_dibuang():
    hasil = jalankan(("12:09 |31,0KB/d", 20), ("LTE", 20), ("85", 20), ("14.10 ©", 20), ("Isi pesan yang penting", 400))
    assert hasil.teks == "Isi pesan yang penting"
    assert set(alasan(hasil).values()) == {bersih.ALASAN_BILAH_STATUS}


def test_pola_status_di_luar_pita_tidak_dibuang():
    hasil = jalankan(("LTE", 500), ("85", 500), ("4G", 700), ("97%", 600))
    assert hasil.dibuang == []
    assert hasil.teks.split("\n") == ["LTE", "85", "4G", "97%"]


def test_angka_polos_di_pita_atas_dianggap_status_dan_di_luar_pita_dipertahankan():
    # Perilaku yang disengaja (lihat komentar _TOKEN_ANGKA): "3" dan "13" di header gambar 08 ikut terbuang.
    assert alasan(jalankan(("3", 30), ("13", 30))) == {"3": bersih.ALASAN_BILAH_STATUS, "13": bersih.ALASAN_BILAH_STATUS}
    assert jalankan(("3", 400), ("13", 450)).dibuang == []


def test_baris_pita_atas_yang_bukan_status_dipertahankan():
    # Potongan yang dimulai dari judul: tidak ada bilah status, jangan buang apa pun.
    hasil = jalankan(("Pemerintah umumkan aturan baru 2026", 30), ("Rp 50.000", 30), ("15DESEMBER2020", 30))
    assert hasil.dibuang == []


def test_pita_atas_mengikuti_konfigurasi_bukan_angka_tetap():
    cfg = dataclasses.replace(Pengaturan(), bersih_pita_atas=0.2)
    assert jalankan(("85", 150), cfg=cfg).dibuang[0].alasan == bersih.ALASAN_BILAH_STATUS
    assert jalankan(("85", 150)).dibuang == []


def test_tanpa_tinggi_gambar_aturan_posisi_mati():
    assert jalankan(("85", 5), tinggi=0).dibuang == []


@pytest.mark.parametrize("teks", ["1,2 rb", "12K", "345 suka", "2,3 jt tayangan", "45 komentar", "1.2k likes"])
def test_angka_interaksi_dibuang(teks):
    hasil = jalankan((teks, 400))
    assert alasan(hasil) == {teks: bersih.ALASAN_INTERAKSI}


@pytest.mark.parametrize("teks", ["12 orang dirawat", "64,2%", "345", "Rp 12K", "12 komentar warganet menyebut hal ini"])
def test_angka_biasa_dan_kalimat_isi_tidak_dibuang_sebagai_interaksi(teks):
    assert jalankan((teks, 400)).dibuang == []


@pytest.mark.parametrize("teks", ["Suka", "Balas", "Bagikan", "Like", "Reply", "Share", "Ikuti", "Follow", "Kirim",
                                  "Komentar", "Suka Balas Bagikan", "Suka · Balas"])
def test_tombol_dibuang(teks):
    assert alasan(jalankan((teks, 400))) == {teks: bersih.ALASAN_TOMBOL}


@pytest.mark.parametrize("teks", [
    "Balas 1, klik tautan untuk",
    "Kirim kode verifikasi ke nomor ini",
    "Bagikan informasi ini ke semua grup keluarga sekarang juga",
    "Share sebanyak-banyaknya",
    "Ikuti petunjuk berikut",
])
def test_kalimat_isi_yang_memuat_kata_tombol_tidak_terbuang(teks):
    assert jalankan((teks, 400)).dibuang == []


@pytest.mark.parametrize("teks", ["Beranda", "Home", "Masuk", "Login", "Log in", "Cari", "Menu", "Berlangganan"])
def test_menu_situs_dibuang(teks):
    assert alasan(jalankan((teks, 400))) == {teks: bersih.ALASAN_MENU}


def test_kalimat_isi_yang_memuat_kata_menu_tidak_terbuang():
    assert jalankan(("Masuk ke rumah lewat pintu belakang", 400), ("Menu hari ini nasi goreng", 450)).dibuang == []


@pytest.mark.parametrize("teks", ["2j", "5 mnt", "kemarin", "3 jam yang lalu", "35 mnt·", "2d", "Baru saja", "5 minutes ago"])
def test_penanda_waktu_berdiri_sendiri_dibuang(teks):
    assert alasan(jalankan((teks, 400))) == {teks: bersih.ALASAN_WAKTU}


@pytest.mark.parametrize("teks", ["0J", "0 mnt", "0j", "00 jam"])
def test_waktu_relatif_dimulai_dari_satu_jadi_nol_tidak_cocok(teks):
    assert jalankan((teks, 400)).dibuang == []


@pytest.mark.parametrize("teks", ["Kemarin saya melihat kejadian itu", "5 mnt lagi tiba", "2 jam perjalanan dari kota"])
def test_kalimat_dengan_penanda_waktu_tidak_terbuang(teks):
    assert jalankan((teks, 400)).dibuang == []


def test_baris_tanpa_huruf_atau_angka_dibuang():
    assert alasan(jalankan(("<", 400), ("· ·", 450))) == {"<": bersih.ALASAN_TANPA_HURUF, "· ·": bersih.ALASAN_TANPA_HURUF}


def test_deret_menu_dibuang_bila_sejajar_dengan_kata_menu():
    hasil = jalankan(("Home", 60), ("Ekonomi Bisnis", 62), ("Finansial", 65), ("Infrastruktur", 66), ("Judul berita utama", 200))
    assert hasil.teks == "Judul berita utama"
    assert alasan(hasil) == {
        "Home": bersih.ALASAN_MENU, "Ekonomi Bisnis": bersih.ALASAN_DERET_MENU,
        "Finansial": bersih.ALASAN_DERET_MENU, "Infrastruktur": bersih.ALASAN_DERET_MENU,
    }


def test_kategori_tanpa_kata_menu_tidak_dibuang():
    assert jalankan(("Ekonomi Bisnis", 60), ("Finansial", 62), ("Infrastruktur", 65)).dibuang == []


def test_deret_menu_butuh_cukup_baris_dan_sejajar():
    # Hanya dua baris sejajar (kurang dari ambang): kategori dipertahankan.
    hasil = jalankan(("Home", 60), ("Ekonomi", 62))
    assert [b.teks for b in hasil.dibuang] == ["Home"]
    # Tiga baris, tetapi tidak sejajar secara vertikal.
    hasil = jalankan(("Home", 60), ("Ekonomi", 300), ("Finansial", 600))
    assert [b.teks for b in hasil.dibuang] == ["Home"]


def test_kalimat_sejajar_dengan_menu_tidak_ikut_dibuang():
    hasil = jalankan(("Home", 60), ("Berita hari ini.", 62), ("Ekonomi", 63), ("Finansial", 64))
    assert "Berita hari ini." in hasil.teks.split("\n")


def test_nama_akun_dan_at_akun_tidak_disentuh():
    hasil = jalankan(("Ema Tri Ratnasari", 30), ("@MasBRO_back", 60), ("MasBRO", 90))
    assert hasil.dibuang == []


def test_urutan_asli_dipertahankan_dan_semua_terbuang_menghasilkan_teks_kosong():
    hasil = jalankan(("Satu", 100), ("Suka", 120), ("Dua", 140))
    assert hasil.teks == "Satu\nDua"
    assert jalankan(("Suka", 100), ("Balas", 120)).teks == ""
    assert bersih.bersihkan([], LEBAR, TINGGI).teks == ""


@pytest.mark.parametrize("teks", ["12.16", "12:16", "7:19PM", "14.15 ✓✓", "√ 09.05", "Diedit 12:16", "12.16 dibaca", "0.05"])
def test_jam_obrolan_berdiri_sendiri_dibuang_di_luar_pita(teks):
    assert alasan(jalankan((teks, 500))) == {teks: bersih.ALASAN_JAM_OBROLAN}


@pytest.mark.parametrize("teks", [
    "Pukul 12.16 saya tiba di rumah", "12.16 Rapat dimulai", "Rp 12.16", "25.61", "12.16 12.17", "Edisi 12.16 diedit ulang oleh redaksi",
])
def test_jam_yang_disertai_kata_isi_tidak_dibuang(teks):
    assert jalankan((teks, 500)).dibuang == []


@pytest.mark.parametrize("teks", ["Show translation", "Lihat terjemahan", "See translation", "Bersponsor", "Sponsored", "Iklan"])
def test_terjemahan_dan_sponsor_sebagai_baris_tunggal_dibuang(teks):
    assert alasan(jalankan((teks, 400))) == {teks: bersih.ALASAN_TERJEMAHAN}


@pytest.mark.parametrize("teks", ["Iklan ini menyesatkan banyak orang", "Sponsored by pemerintah daerah", "Lihat terjemahan resmi dokumen"])
def test_kalimat_yang_hanya_mirip_label_terjemahan_atau_sponsor_tidak_terbuang(teks):
    assert jalankan((teks, 400)).dibuang == []


def test_baca_juga_hanya_varian_ukur():
    pasangan = [("Baca juga: Pemerintah umumkan aturan baru soal tilang kendaraan bermotor di seluruh Indonesia", 400),
                ("Lihat selengkapnya", 450)]
    assert jalankan(*pasangan).dibuang == []
    hasil = jalankan(*pasangan, varian=frozenset({bersih.VARIAN_BACA_JUGA}))
    assert {b.alasan for b in hasil.dibuang} == {bersih.ALASAN_BACA_JUGA} and hasil.teks == ""
    assert jalankan(("Baca ulang pesannya", 500), ("selengkapnya.", 520), varian=frozenset({bersih.VARIAN_BACA_JUGA})).dibuang == []


BANNER_TERPECAH = [
    "Pesan dan panggilan terenkripsi secara end-to-end. Tidak seorang",
    "pun di luar chat ini yang dapat membaca atau mendengarkannya,",
    "bahkan WhatsApp. Ketuk untuk info selengkapnya.",
]


def test_banner_whatsapp_terpecah_beberapa_baris_dibuang():
    hasil = jalankan(("Diteruskan", 200), *[(t, 250 + 20 * i) for i, t in enumerate(BANNER_TERPECAH)], ("Selamat siang kak", 400))
    assert hasil.teks == "Diteruskan\nSelamat siang kak"
    assert set(alasan(hasil).values()) == {bersih.ALASAN_BANNER}


def test_banner_whatsapp_variasi_kata_dan_bahasa_inggris():
    hasil = jalankan(
        ("Pesan dan panggilan dienkripsi secara", 100), ("end-to-end. Tidak seorang pun di luar chat", 120),
        ("ini, termasuk WhatsApp, yang dapat membaca atau mendengarkannya. Ketuk untuk info", 140), ("selengkapnya.", 160),
        ("Chat ini dengan akun bisnis. Ketuk untuk info selengkapnya.", 200),
        ("Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read", 250),
        ("or listen to them. Tap to learn more.", 270),
        ("Halo kak", 400),
    )
    assert hasil.teks == "Halo kak"


def test_banner_tidak_membuang_baris_yang_bercampur_dengan_isi():
    baris_campur = "Awas penipuan! Pesan dan panggilan terenkripsi secara end-to-end. Ketuk untuk info selengkapnya."
    hasil = jalankan((baris_campur, 100), ("Ketuk untuk info selengkapnya.", 200), ("Pesan dan panggilan terenkripsi", 300))
    assert hasil.dibuang == [] or all(b.teks != baris_campur for b in hasil.dibuang)
    assert baris_campur in hasil.teks
    assert "Ketuk untuk info selengkapnya." in hasil.teks  # tanpa awal banner, bukan banner


def test_varian_tidak_dikenal_ditolak():
    with pytest.raises(ValueError):
        jalankan(("a", 1), varian=frozenset({"ngawur"}))


@pytest.mark.parametrize("teks", [
    "Bukan kontak", "Bukan kontak · Tidak ada grup yang sama", "Bukan kontak - Tidak ada grup yang sama", "Tidak ada grup yang sama",
    "Fitur keamanan", "Ketik pesan", "Ketik pesan...", "Tulis komentar", "Type a message", "Message", "Write a comment",
])
def test_ui_aplikasi_pesan_dibuang_bila_seluruh_baris_cocok(teks):
    assert alasan(jalankan((teks, 500))) == {teks: bersih.ALASAN_UI_PESAN}


@pytest.mark.parametrize("teks", [
    "Bukan kontak saya yang mengirim ini", "Fitur keamanan baru diumumkan hari ini", "Ketik pesan ini ke semua teman",
    "Message me for details", "Tidak ada grup yang sama dengan itu", "Pesan",
])
def test_kalimat_isi_yang_memuat_teks_ui_pesan_tidak_terbuang(teks):
    assert jalankan((teks, 500)).dibuang == []
