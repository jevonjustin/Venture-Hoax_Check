import dataclasses
import re

import pytest

from app.konfigurasi import Pengaturan
from app.pipeline import klaim
from app.pipeline.klaim import klaim_heuristik, pisah_kalimat


def rapi(teks: str) -> str:
    return re.sub(r"\s+", " ", teks).strip()


def test_klaim_diambil_apa_adanya_dari_teks():
    teks = "ONLY NEWS\n@akun\nPemerintah kota mengumumkan perbaikan Jalan Merdeka pada 12 Oktober 2026.\nTerima kasih."
    hasil = klaim_heuristik(teks)
    assert hasil == "Pemerintah kota mengumumkan perbaikan Jalan Merdeka pada 12 Oktober 2026."
    assert hasil in rapi(teks)


def test_hasil_selalu_substring_teks_kecuali_elipsis():
    teks = "Resmi berubah aturan tilang kendaraan terbaru mulai April 2025, kini motor dan mobil langsung disita. " * 4
    cfg = dataclasses.replace(Pengaturan(), klaim_maks_karakter=60)
    hasil = klaim_heuristik(teks, cfg=cfg)
    assert hasil.endswith("…") and len(hasil) <= 61
    assert hasil[:-1] in rapi(teks)
    assert hasil[:-1].split()[-1] in teks.split()  # dipotong di batas kata, bukan di tengah kata


def test_kalimat_yang_terbelah_lintas_baris_digabung():
    teks = "Akun Anda akan segera dinonaktifkan secara\npermanen karena terdeteksi melanggar aturan\nplatform pada 5 Mei 2026."
    assert klaim_heuristik(teks) == rapi(teks)


def test_kata_sambung_di_ujung_baris_menyambungkan_ke_baris_berikutnya():
    teks = "PDIP USUL KE PEMERINTAH AGAR\nPESANTREN DI TUTUP SELURUH INDONESIA"
    assert klaim_heuristik(teks) == "PDIP USUL KE PEMERINTAH AGAR PESANTREN DI TUTUP SELURUH INDONESIA"


def test_baris_pendek_tidak_disambung_tanpa_alasan():
    teks = "ONLY NEWS\nIndonesia jadi negara termiskin tertinggi dunia tahun 2026."
    assert klaim_heuristik(teks) == "Indonesia jadi negara termiskin tertinggi dunia tahun 2026."


def test_baris_metadata_tanggal_menjadi_batas():
    assert pisah_kalimat("Judul berita di sini\nSenin, 14 Sep 2026 21:00 WIB\nIsi berita dimulai dari sini.")[1].startswith("Senin")


@pytest.mark.parametrize("teks,jumlah", [
    ("Denda Rp1.000.000 berlaku mulai besok. Tolong dicek.", 2),
    ("Rapat pukul 12.16 dihadiri banyak orang. Selesai sore.", 2),
    ("Lihat www.contoh.com/info.html untuk keterangan. Terima kasih banyak.", 2),
    ("Dr. Budi menyatakan bahwa dll. akan menyusul. Selesai.", 2),
    ("Pembayaran a.n. Siti Rahma s.d. Mei 2026 sudah masuk. Cek lagi.", 2),
    ("Kata Prof. Rudi itu tidak benar. Begitu.", 2),
    ("Satu kalimat! Dua kalimat? Tiga kalimat.", 3),
    ("tanpa titik di akhir", 1),
])
def test_titik_bukan_batas_kalimat_pada_angka_tautan_dan_singkatan(teks, jumlah):
    assert len(pisah_kalimat(teks)) == jumlah, pisah_kalimat(teks)


def test_titik_diikuti_huruf_kecil_bukan_batas():
    assert len(pisah_kalimat("Pemerintah menyatakan hal itu dst. dan seterusnya sampai selesai.")) == 1


def test_pertanyaan_tidak_dipilih():
    assert klaim_heuristik("Benarkah pemerintah akan menutup semua sekolah mulai besok?") == ""


def test_baris_ui_tidak_dipilih():
    assert klaim_heuristik("Baca selengkapnya di sini\nSuka Balas Bagikan\n1,2 rb komentar") == ""


def test_teks_tanpa_pernyataan_menghasilkan_string_kosong():
    assert klaim_heuristik("") == ""
    assert klaim_heuristik("OK\nHalo kak\nSiap") == ""
    assert klaim_heuristik("https://contoh.com/abc/def/ghi/jkl/mno") == ""
    assert klaim_heuristik("12 34 56 78 90 12 34") == ""  # hampir semuanya bukan huruf


def test_kalimat_dengan_pernyataan_menang_atas_seruan_kosong():
    teks = "Wow luar biasa sekali kawan semua!\nPemerintah akan menutup jalan tol pada 5 Mei 2026."
    assert klaim_heuristik(teks) == "Pemerintah akan menutup jalan tol pada 5 Mei 2026."


def test_tumpang_tindih_dengan_bukti_ciri_menaikkan_skor():
    teks = "Kami sedang melakukan pengecekan data kependudukan terbaru.\nKode verifikasi sudah dikirim ke nomor itu."
    assert klaim_heuristik(teks) == "Kami sedang melakukan pengecekan data kependudukan terbaru."  # seri: yang lebih awal
    bukti = ["kode verifikasi sudah dikirim ke nomor itu"]
    assert klaim_heuristik(teks, bukti) == "Kode verifikasi sudah dikirim ke nomor itu."


def test_skor_minimum_mengikuti_konfigurasi():
    teks = "Pemerintah kota mengumumkan perbaikan Jalan Merdeka pada 12 Oktober 2026."
    assert klaim_heuristik(teks)
    ketat = dataclasses.replace(Pengaturan(), klaim_skor_minimum=99)
    assert klaim_heuristik(teks, cfg=ketat) == ""


def test_kalimat_terlalu_pendek_tidak_dipertimbangkan():
    assert klaim_heuristik("Jalan ditutup besok.") == ""  # 3 kata


def test_ekstrak_klaim_dummy_masih_ada_untuk_analisis():
    assert callable(klaim.ekstrak_klaim)


def test_baris_ui_menjadi_pemisah_dan_baris_duplikat_tidak_membingungkan_penggabungan():
    teks = "Kata\nSuka\nKata\nkelanjutan kalimat ini yang cukup panjang untuk dihitung sebagai klaim dari pesan tadi."
    assert klaim_heuristik(teks).startswith("kelanjutan") or klaim_heuristik(teks).startswith("Kata kelanjutan")
