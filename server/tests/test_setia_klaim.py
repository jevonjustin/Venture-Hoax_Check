"""Pemeriksaan kesetiaan klaim LLM (Sesi 5.6, pipeline/setia.py). Teks tes buatan sendiri, tanpa jaringan."""

import dataclasses

import pytest

from app.konfigurasi import Pengaturan, pengaturan
from app.pipeline import llm, setia
from conftest import PembacaPalsu  # noqa: F401  (fixture llm_palsu dari conftest)
from test_tahap_b import TEKS_KLAIM, analisis_dengan_diagnostik, hasil_llm, teks_layar

CFG = Pengaturan(periksa_kesetiaan_klaim=True)

TEKS_GELANDANG = "Mantan bendahara yayasan digelandang petugas ke kantor polisi kemarin siang bersama dua pengurus"
TEKS_PENIPU = "Waspada pesan berantai yang meminta transfer dana ke rekening baru atas nama yayasan peduli"
TEKS_MENTERI = "Menteri Keuangan Suahasil menyatakan anggaran sekolah negeri naik pada tahun depan"


def kode(klaim: str, teks: str, cfg: Pengaturan = CFG):
    hasil = setia.periksa_kesetiaan(klaim, teks, cfg)
    return hasil[0] if hasil else None


def test_digelandang_diganti_digelapkan_gagal():
    klaim = "Mantan bendahara yayasan digelapkan petugas ke kantor polisi"
    assert kode(klaim, TEKS_GELANDANG) == setia.KODE_PENGGANTI
    assert kode("Mantan bendahara yayasan digelandang petugas ke kantor polisi", TEKS_GELANDANG) is None


def test_kata_penipu_ditambahkan_gagal():
    klaim = "Pesan berantai penipu meminta transfer dana ke rekening baru"
    assert kode(klaim, TEKS_PENIPU) == setia.KODE_BERAT
    assert kode("Pesan berantai penipuan meminta transfer dana", TEKS_PENIPU) == setia.KODE_BERAT
    # kata penilaian yang memang ada di teks boleh dipakai
    assert kode("Pesan penipuan meminta transfer dana", "Waspada penipuan: pesan meminta transfer dana") is None


def test_jabatan_wakil_menteri_ditambahkan_gagal():
    klaim = "Wakil Menteri Keuangan Suahasil menyatakan anggaran sekolah negeri naik"
    assert kode(klaim, TEKS_MENTERI) == setia.KODE_ENTITAS
    assert kode("Menteri Keuangan Suahasil menyatakan anggaran sekolah negeri naik", TEKS_MENTERI) is None


def test_salah_eja_nama_oleh_ocr_lolos():
    teks = "Menteri Keuangan Suhasasil menyatakan anggaran sekolah negeri naik pada tahun depan"
    assert kode("Menteri Keuangan Suahasil menyatakan anggaran sekolah negeri naik", teks) is None
    # nama yang benar-benar lain gagal
    assert kode("Menteri Keuangan Budiman menyatakan anggaran sekolah negeri naik", teks) == setia.KODE_ENTITAS


def test_singkatan_harus_ada_di_teks():
    teks = "PDIP usul pemerintah tutup pesantren seluruh Indonesia"
    assert kode("PDIP usul pemerintah menutup pesantren", teks) is None
    assert kode("PKB usul pemerintah menutup pesantren", teks) == setia.KODE_ENTITAS


def test_angka_berbeda_gagal():
    teks = "Bantuan sebesar Rp1.500.000 dibagikan kepada 200 warga desa"
    assert kode("Bantuan Rp2.500.000 dibagikan kepada warga desa", teks) == setia.KODE_ANGKA
    assert kode("Bantuan Rp1.500.000 dibagikan kepada 300 warga desa", teks) == setia.KODE_ANGKA


@pytest.mark.parametrize("klaim", [
    "Bantuan sebesar 1,5 juta dibagikan kepada warga desa",
    "Bantuan sebesar Rp 1.500.000 dibagikan kepada warga desa",
    "Bantuan sebesar 1500000 dibagikan kepada warga desa",
])
def test_angka_sama_format_beda_lolos(klaim):
    assert kode(klaim, "Bantuan sebesar Rp1,5jt dibagikan kepada warga desa") is None
    assert kode("Diskon 15 persen berlaku", "Diskon 15% berlaku hari ini") is None


def test_parafrase_setia_lolos():
    teks = "PDIP USUL KE PEMERINTAH AGAR PESANTREN DI TUTUP SELURUH INDONESIA"
    assert kode("PDIP mengusulkan pemerintah menutup pesantren", teks) is None
    assert kode("Pemerintah diusulkan PDIP menutup pesantren", teks) is None


def test_kata_menempel_akibat_ocr_lolos():
    assert kode("Pemerintah agar pesantren ditutup", "pemerintahagar pesantren ditutup") is None


def test_laporan_alasan_hanya_kode_dan_jumlah():
    hasil = setia.periksa_kesetiaan("Wakil Menteri Keuangan Suahasil menyatakan anggaran naik", TEKS_MENTERI, CFG)
    assert isinstance(hasil[0], str) and isinstance(hasil[1], int) and hasil[1] >= 1


# --- integrasi dengan klaim_dapat_dipakai dan orkestrator ---


def test_bendera_mati_memakai_perilaku_lama():
    klaim = "Mantan bendahara yayasan digelapkan petugas ke kantor polisi"
    assert Pengaturan().periksa_kesetiaan_klaim is False
    assert llm.klaim_dapat_dipakai(klaim, TEKS_GELANDANG, Pengaturan()) is True
    assert llm.klaim_dapat_dipakai(klaim, TEKS_GELANDANG, CFG) is False
    assert llm.alasan_klaim_ditolak(klaim, TEKS_GELANDANG, Pengaturan()) is None
    assert llm.alasan_klaim_ditolak(klaim, TEKS_GELANDANG, CFG) == (setia.KODE_PENGGANTI, 1)


def test_konstanta_ambang_dapat_diubah_lewat_pengaturan():
    teks = "Mantan bendahara yayasan ditahan petugas ke kantor polisi kemarin siang"
    klaim = "Mantan bendahara yayasan ditahan petugas ke kantor polisi kemarin siang ramai tetangga sekitar disaksikan banyak kerabat jauh"
    assert kode(klaim, teks) == setia.KODE_BANYAK
    assert kode(klaim, teks, dataclasses.replace(CFG, klaim_setia_kata_baru_maks=0.9)) is None


def test_klaim_gagal_jatuh_ke_heuristik_dan_diagnostik_tanpa_teks(monkeypatch, llm_palsu, pencarian_palsu):
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)
    monkeypatch.setattr(pengaturan, "llm_aktif", True)
    teks_layar(monkeypatch, TEKS_KLAIM)
    llm_palsu.hasil = hasil_llm("Air keran di Jakarta mengandung zat berbahaya penyebab penyakit 99 warga")

    hasil, diag = analisis_dengan_diagnostik(monkeypatch)  # bendera mati
    assert diag["klaim_sumber"] == "llm" and diag["llm"]["alasan_klaim_ditolak"] is None

    monkeypatch.setattr(pengaturan, "periksa_kesetiaan_klaim", True)
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    assert diag["klaim_sumber"] == "heuristik"
    assert diag["llm"]["klaim_dipakai"] is False
    assert diag["llm"]["alasan_klaim_ditolak"] == {"kode": setia.KODE_ANGKA, "jumlah": 1}


# --- negasi ---

TEKS_NEGASI = "Pemerintah tidak menutup pesantren di seluruh Indonesia menurut keterangan resmi hari ini"


def test_negasi_dihapus_gagal():
    assert kode("Pemerintah menutup pesantren di seluruh Indonesia", TEKS_NEGASI) == setia.KODE_NEGASI


def test_negasi_ditambah_gagal():
    teks = "Pemerintah menutup pesantren di seluruh Indonesia menurut keterangan resmi hari ini"
    assert kode("Pemerintah tidak menutup pesantren di seluruh Indonesia", teks) == setia.KODE_NEGASI
    # teks punya negasi di tempat lain, klaim menambahkan negasi pada kata yang tidak bernegasi di teks
    teks2 = "Pemerintah menutup pesantren di seluruh Indonesia, warga tidak panik menurut keterangan resmi"
    assert kode("Pemerintah tidak menutup pesantren di seluruh Indonesia", teks2) == setia.KODE_NEGASI


def test_negasi_sama_lolos():
    assert kode("Pemerintah tidak menutup pesantren di seluruh Indonesia", TEKS_NEGASI) is None
    assert kode("Pemerintah tak menutup pesantren", TEKS_NEGASI) is None  # penanda berbeda, kata sama


def test_negasi_di_bagian_teks_lain_lolos():
    teks = "Pemerintah menutup pesantren di seluruh Indonesia. Warga tidak perlu panik dan belum ada korban"
    assert kode("Pemerintah menutup pesantren di seluruh Indonesia", teks) is None


# --- negasi: jangkauan klausa, kemunculan lain, dan penanda informal (T8c) ---

def test_negasi_tidak_melewati_kata_sambung_dan_koma():
    teks = "Dibutuhkan operator gudang dengan gaji besar tanpa pengalaman. Hanya bawa berkas sendiri, bayar biaya seragam sebelum mulai kerja"
    klaim = "Dibutuhkan operator gudang dengan gaji besar tanpa pengalaman, dengan biaya seragam sebelum mulai kerja"
    assert kode(klaim, teks) is None
    # negasi benar-benar dihapus dari kata yang dinegasikan tetap gagal
    teks2 = "Lowongan operator gudang tanpa pengalaman tersedia sekarang"
    assert kode("Lowongan operator gudang pengalaman tersedia sekarang", teks2) == setia.KODE_NEGASI


def test_negasi_kemunculan_lain_tanpa_negasi_cukup():
    teks = "Banjir rendam kampung bantaran. Belum ada warga yang mengungsi. Warga bantaran diminta waspada"
    assert kode("Banjir rendam kampung bantaran dan warga diminta waspada", teks) is None
    # satu-satunya kemunculan kata isi bernegasi, klaim membuang negasi: gagal
    teks2 = "Banjir rendam kampung bantaran, belum ada korban jiwa"
    assert kode("Banjir rendam kampung bantaran dan korban jiwa", teks2) == setia.KODE_NEGASI


def test_negasi_kata_turunan_berbeda_arti_tidak_dihitung():
    teks = "Petani memakai aplikasi cuaca untuk menentukan waktu tanam karena curah hujan tidak menentu"
    assert kode("Petani memakai aplikasi cuaca untuk menentukan waktu tanam", teks) is None


def test_negasi_informal_ga_dikenali():
    teks = "Akun resmi bilang harga tiket ga jadi naik"
    assert kode("Harga tiket tidak naik", teks) is None
    assert kode("Harga tiket naik", teks) == setia.KODE_NEGASI


# --- nama: bulan angka/singkatan dan nama bertanda hubung (T8c) ---

def test_bulan_dari_tanggal_angka_dan_singkatan_lolos():
    assert setia.bulan_di("diunggah Rabu (15/4/2026) dan berlaku per 1 Nov 2015") == {4, 11}
    assert kode("Unggahan beredar Rabu 15 April 2026", "Unggahan beredar Rabu (15/4/2026) di media sosial") is None
    assert kode("Tarif berlaku 1 November 2015", "Tarif berlaku per 1 Nov 2015 menurut aturan") is None
    # bulan yang tidak ada di teks tetap gagal
    assert kode("Unggahan beredar Rabu 15 Mei 2026", "Unggahan beredar Rabu (15/4/2026) di media sosial") == setia.KODE_ENTITAS


def test_nama_bertanda_hubung_diperiksa_per_bagian():
    teks = "Peneliti temukan sinyal Wi-Fi paling kencang di rumah tetangga yang kata sandinya tidak diketahui"
    assert kode("Peneliti temukan sinyal Wi-Fi paling kencang di rumah tetangga", teks) is None
    assert kode("Peneliti temukan sinyal Bluetooth paling kencang di rumah tetangga", teks) == setia.KODE_ENTITAS
    assert kode("Peneliti temukan sinyal Wi-Zon paling kencang di rumah tetangga", teks) == setia.KODE_ENTITAS
