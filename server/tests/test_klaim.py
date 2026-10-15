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
    teks = "Akun pengguna akan segera dinonaktifkan secara\npermanen karena terdeteksi melanggar aturan\nplatform pada 5 Mei 2026."
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
    teks = (
        "Kami sedang melakukan pengecekan data kependudukan terbaru di seluruh kota.\n"
        "Kode verifikasi sudah dikirim ke nomor itu pagi tadi."
    )
    assert klaim_heuristik(teks) == "Kami sedang melakukan pengecekan data kependudukan terbaru di seluruh kota."  # seri
    bukti = ["kode verifikasi sudah dikirim ke nomor itu"]
    assert klaim_heuristik(teks, bukti) == "Kode verifikasi sudah dikirim ke nomor itu pagi tadi."


def test_skor_minimum_mengikuti_konfigurasi():
    teks = "Pemerintah kota mengumumkan perbaikan Jalan Merdeka pada 12 Oktober 2026."
    assert klaim_heuristik(teks)
    ketat = dataclasses.replace(Pengaturan(), klaim_skor_minimum=99)
    assert klaim_heuristik(teks, cfg=ketat) == ""


def test_kalimat_terlalu_pendek_tidak_dipertimbangkan():
    assert klaim_heuristik("Jalan ditutup besok.") == ""  # 3 kata


def test_baris_ui_menjadi_pemisah_dan_baris_duplikat_tidak_membingungkan_penggabungan():
    teks = "Kata\nSuka\nKata\nkelanjutan kalimat ini yang cukup panjang untuk dihitung sebagai klaim dari pesan tadi."
    assert klaim_heuristik(teks).startswith("kelanjutan") or klaim_heuristik(teks).startswith("Kata kelanjutan")


# ----- Sesi 5.5: kata ganti kedua, orang pertama, sapaan, klaim dari bukti -----

from app.konfigurasi import Pengaturan as _Pengaturan  # noqa: E402
from app.pipeline import klaim as _klaim  # noqa: E402
from app.pipeline.tipe import CiriTerdeteksi as _Ciri  # noqa: E402


def test_kata_ganti_kedua_dikenali_tanpa_salah_pada_kata_biasa():
    for teks in ("Akun Anda dinonaktifkan", "kamu harus segera", "Jaga dirimu", "Kalian wajib hadir", "bukumu hilang"):
        assert _klaim.memuat_kata_ganti_kedua(teks), teks
    for teks in ("Tamu undangan hadir di acara ilmu pengetahuan", "Pemerintah mengumumkan aturan baru", "Jamu tradisional"):
        assert not _klaim.memuat_kata_ganti_kedua(teks), teks


def test_kalimat_dengan_anda_dilewati_dan_kalimat_berikutnya_dipilih():
    teks = "Akun Anda akan segera dinonaktifkan secara permanen oleh platform.\nPemerintah mengumumkan aturan pajak baru berlaku mulai 1 Mei 2026."
    assert klaim_heuristik(teks) == "Pemerintah mengumumkan aturan pajak baru berlaku mulai 1 Mei 2026."
    assert klaim_heuristik("Akun Anda akan segera dinonaktifkan secara permanen oleh platform.") == ""


def test_kalimat_orang_pertama_dan_sapaan_bukan_klaim_dan_dihitung():
    teks = "OK saya tunggu, sudah lebih dari 2 menit lagi ya kak sampai selesai."
    catatan: dict = {}
    assert klaim_heuristik(teks, catatan=catatan) == ""
    assert catatan == {"gugur_percakapan": 1}
    teks2 = "Kak tolong kirim bukti pembayaran sebesar 500 ribu rupiah sekarang juga ya."
    c2: dict = {}
    assert klaim_heuristik(teks2, catatan=c2) == "" and c2["gugur_percakapan"] == 1


def test_bonus_klaim_hanya_dari_ciri_tinggi():
    ciri = [_Ciri("desakan_waktu", ["a b c"], "sedang"), _Ciri("permintaan_data_rahasia", ["d e f"], "tinggi")]
    assert _klaim.bukti_untuk_klaim(ciri) == ["d e f"]


def test_skor_minimum_lebih_tinggi_bila_klaim_llm_ditolak():
    teks = "Pemerintah mengumumkan aturan pajak baru berlaku mulai 1 Mei 2026."
    assert klaim_heuristik(teks) == teks
    assert klaim_heuristik(teks, skor_minimum=99.0) == ""


def test_klaim_dari_bukti_syarat_panjang_kata_ganti_dan_ui():
    cfg = _Pengaturan()
    assert _klaim.klaim_dari_bukti("PT CIMORY FOODS INDONESIA MENITI KARIR DI CIMORY:", cfg) == "PT CIMORY FOODS INDONESIA MENITI KARIR DI CIMORY"
    assert _klaim.klaim_dari_bukti("700 Kepala Desa", cfg) == ""
    assert _klaim.klaim_dari_bukti("Akun Anda AKAN Segera Dinonaktifkan oleh sistem", cfg) == ""
    assert _klaim.klaim_dari_bukti("", cfg) == ""


def test_klaim_dari_bukti_membuang_kata_sambung_di_ujung_dan_menolak_orang_pertama():
    cfg = _Pengaturan()
    assert _klaim.klaim_dari_bukti("kebakaran hutan kalimantan mulai masuk negara brunei dan", cfg) == (
        "kebakaran hutan kalimantan mulai masuk negara brunei"
    )
    assert _klaim.klaim_dari_bukti("vaksin cacar air karena itu menyebabkan epidemi shingles di", cfg).endswith("shingles")
    assert _klaim.klaim_dari_bukti("nama saya Malia dan saya bekerja di departemen SDM di Shopee", cfg) == ""
    assert _klaim.klaim_dari_bukti("harga dan di", cfg) == ""
