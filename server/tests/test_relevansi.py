"""Penyaringan artikel tidak berkaitan, bukti jendela kata (gambar 16), pemeriksaan_terbatas, dan banner."""

import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.konfigurasi import Pengaturan, pengaturan
from app.pipeline import baca, cocok, tingkat
from app.pipeline.tipe import CiriTerdeteksi, Kandidat
from app.skema import Tingkat
from conftest import PembacaPalsu

CFG = Pengaturan()
TEKS_GAMBAR_16 = (
    "Forwarded many times\nCUKUP VIRALKAN INI DAN DIKOPI KASIKAN KE\nRAKYAT PLOSOK PLOSOK DESA INSYA ALLAH\n"
    "PASTI TUMBANG DAN PASTI DIBENCI SAMA\nRAKYAT TERUTAMA RAKYAT KAUM PEDESAAN\nPERDALAMAN\n"
    "PDIP USUL KE PEMERINTAH AGAR\nPESANTREN DI TUTUP SELURUH INDONESIA\nAndebaNews\n7:19PM"
)


def art(label="salah", skor=0.9, relevansi=1.0, judul="Artikel contoh", narasi="") -> Kandidat:
    return Kandidat(
        judul=judul, sumber="TBH", url=f"https://example.test/{judul}", skor=skor, label=label,
        tanggal=date(2025, 1, 1), url_format_lama=False, narasi=narasi, relevansi=relevansi,
    )


def putus(kandidat, ciri=()):
    return tingkat.tentukan(list(ciri), kandidat, "Teks klaim contoh yang cukup panjang untuk diuji di sini.", CFG)


# --- relevansi leksikal ---

ARTIKEL_DB = [
    {"judul": "[SALAH] Menkeu Suahasil Terlibat Korupsi Ratusan Triliun Rupiah", "narasi": "Beredar klaim Menkeu terlibat."},
    {"judul": "Prabowo Terlibat Korupsi Pengadaan Alutsista di Kemenhan", "narasi": "Pengadaan alutsista."},
    {"judul": "Korupsi proyek jalan di daerah", "narasi": "Korupsi terlibat banyak."},
    {"judul": "Korupsi dana desa terlibat kepala desa", "narasi": "Korupsi."},
    {"judul": "Indonesia negara termiskin", "narasi": "World Bank Indonesia negara."},
]


def test_kata_isi_membuang_kata_pendek_dan_kata_sambung_tetapi_menyimpan_angka():
    assert cocok.kata_isi("Di rumah yang ada 500 triliun, tahun 2026") == {"rumah", "500", "triliun", "tahun", "2026"}


def test_kata_jarang_lebih_berbobot_dari_kata_umum():
    idf = cocok.hitung_idf(ARTIKEL_DB)
    assert idf["alutsista"] > idf["korupsi"]


def test_relevansi_artikel_yang_dibicarakan_tinggi_dan_yang_tidak_berkaitan_rendah():
    idf = cocok.hitung_idf(ARTIKEL_DB)
    teks = cocok.kata_isi("MenKeu Suhasasil Terlibat Korupsi 500 Triliun Senin 14 Sep 2026")
    sumber = cocok.relevansi_judul(teks, ARTIKEL_DB[0]["judul"], idf, len(ARTIKEL_DB))
    lain = cocok.relevansi_judul(teks, ARTIKEL_DB[1]["judul"], idf, len(ARTIKEL_DB))
    assert sumber > CFG.relevansi_minimum > lain


def test_kata_dasar_dan_berimbuhan_dianggap_sama_hanya_untuk_kata_panjang():
    assert cocok._ada("miskin", {"termiskin"}) is True
    assert cocok._ada("dana", {"danau"}) is False  # kata pendek harus persis


def test_judul_tanpa_kata_isi_tidak_disaring():
    assert cocok.relevansi_judul({"apa"}, "[SALAH] Ya", {}, 10) == 1.0


def test_pencarian_mengisi_relevansi_kandidat(tmp_path):
    from test_cocok import bangun_indeks, EmbedderPalsu, pengaturan_uji

    bangun_indeks(tmp_path)
    p = cocok.Pencarian(buat_embedder=lambda cfg, m: EmbedderPalsu())
    p.muat(pengaturan_uji(tmp_path))
    hasil = p.cari("air keran Jakarta mengandung zat berbahaya penyakit", 4)
    sumber = next(k for k in hasil if k.label == "salah")
    lain = next(k for k in hasil if k.label == "klarifikasi")
    assert 0.0 <= lain.relevansi < sumber.relevansi <= 1.0


# --- penyaringan di logika tingkat ---


def test_artikel_tidak_berkaitan_di_rentang_mirip_tidak_menaikkan_ke_hati_hati():
    p = putus([art("salah", 0.855, relevansi=0.28, judul="Prabowo Terlibat Korupsi Alutsista")])
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN and p.cek_fakta == [] and len(p.tersaring) == 1


def test_artikel_tidak_berkaitan_tidak_tampil_tetapi_yang_berkaitan_tetap():
    p = putus([
        art("salah", 0.896, 1.0, judul="Sumber"),
        art("salah", 0.862, 0.69, judul="Komdigi Negara Termiskin Kedua"),
        art("salah", 0.861, 0.34, judul="Pelatih Guinea"),
    ])
    assert p.tingkat is Tingkat.KUAT
    assert [k.judul for k in p.cek_fakta] == ["Sumber", "Komdigi Negara Termiskin Kedua"]
    assert [k.judul for k in p.tersaring] == ["Pelatih Guinea"]


def test_peringkat_satu_di_atas_ambang_cocok_lolos_tanpa_syarat_relevansi():
    p = putus([art("salah", 0.90, relevansi=0.0)])
    assert p.tingkat is Tingkat.KUAT and len(p.cek_fakta) == 1 and p.tersaring == []


def test_bukan_peringkat_satu_tetap_harus_relevan_walau_skor_di_atas_ambang_cocok():
    p = putus([art("lainnya", 0.95, 1.0, judul="A"), art("salah", 0.89, 0.1, judul="B")])
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN
    assert [k.judul for k in p.cek_fakta] == ["A"] and [k.judul for k in p.tersaring] == ["B"]


def test_peringkat_satu_di_bawah_ambang_cocok_juga_harus_relevan():
    p = putus([art("salah", 0.87, relevansi=0.2)])
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN


def test_artikel_konflik_tidak_relevan_tidak_dihitung_sebagai_konflik():
    p = putus([art("salah", 0.90, 1.0, judul="Salah"), art("klarifikasi", 0.89, 0.05, judul="Lain")])
    assert p.tingkat is Tingkat.KUAT


def test_artikel_tersaring_dan_ciri_tetap_hati_hati_ciri_saja():
    ciri = [CiriTerdeteksi("ajakan_menyebarkan", ["Sebarkan"], "tinggi")]
    p = putus([art("salah", 0.86, 0.1)], ciri)
    assert (p.tingkat, p.varian) == (Tingkat.HATI_HATI, tingkat.VARIAN_CIRI_SAJA)


def test_ambang_relevansi_dari_konfigurasi():
    kandidat = [art("salah", 0.86, 0.5)]
    assert tingkat.tentukan([], kandidat, "teks", Pengaturan(relevansi_minimum=0.6)).tingkat is Tingkat.TIDAK_DITEMUKAN
    assert tingkat.tentukan([], kandidat, "teks", Pengaturan(relevansi_minimum=0.4)).varian == tingkat.VARIAN_MIRIP


# --- bukti jendela kata (gambar 16) ---

ARTIKEL_PDIP = art(
    "salah", 0.914, judul="[SALAH] PDIP USUL KE PEMERINTAH AGAR PESANTREN DITUTUP SELURUH INDONESIA",
    # Narasi asli di database memuat seluruh pesan berantainya, termasuk kalimat pembuka yang bukan klaim.
    narasi="CUKUP VIRALKAN INI DAN DIKOPI KASIKAN KE RAKYAT PLOSOK PLOSOK DESA INSYA ALLAH PASTI TUMBANG DAN PASTI "
    "DIBENCI SAMA RAKYAT KAUM PEDESAAN PERDALAMAN PDIP USUL KE PEMERINTAH AGAR PESANTREN DI TUTUP SELURUH INDONESIA "
    "Tutup pesantren seluruh Indonesia",
)


def test_teks_kapital_tanpa_titik_menghasilkan_jendela_yang_mirip_artikel_bukan_potongan_awal():
    bukti = cocok.kalimat_serupa(TEKS_GAMBAR_16, ARTIKEL_PDIP)
    assert bukti.startswith("PDIP USUL KE PEMERINTAH")
    assert "SELURUH INDONESIA" in bukti and "VIRALKAN" not in bukti and "AndebaNews" not in bukti
    assert "…" not in bukti and len(bukti) <= CFG.ciri_bukti_maks_karakter
    assert bukti in " ".join(TEKS_GAMBAR_16.split())  # potongan persis (modulo spasi)


def test_bukti_pernah_dibantah_gambar_16_lewat_logika_tingkat():
    p = tingkat.tentukan([], [ARTIKEL_PDIP], TEKS_GAMBAR_16, CFG)
    assert p.tingkat is Tingkat.KUAT
    assert p.ciri_dibantah.bukti[0].startswith("PDIP USUL KE PEMERINTAH")


def test_kalimat_pendek_dikembalikan_utuh_tanpa_dipangkas_tepinya():
    teks = "Air keran di Jakarta mengandung zat berbahaya."
    artikel = art(judul="Air keran Jakarta mengandung zat berbahaya", narasi="")
    assert cocok.kalimat_serupa(teks, artikel) == teks


# --- pemeriksaan_terbatas ---

TEKS_LAYAR = "Air keran di Jakarta mengandung zat berbahaya penyebab penyakit misterius. Sebarkan ke semua keluarga."


@pytest.fixture
def klien(monkeypatch):
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)
    monkeypatch.setattr(baca, "pembaca", PembacaPalsu(TEKS_LAYAR))
    return TestClient(main.app)


def kirim(klien, params=None):
    keluaran = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 10)).save(keluaran, format="JPEG")
    return klien.post("/analisis", params=params, files={"gambar": ("p.jpg", keluaran.getvalue(), "image/jpeg")})


def test_pencarian_berjalan_pemeriksaan_terbatas_kosong(klien):
    assert kirim(klien).json()["pemeriksaan_terbatas"] == []


@pytest.mark.parametrize("status", ["nonaktif", "tidak_tersedia", "belum_dimuat"])
def test_pencarian_tidak_berjalan_ditandai_cek_fakta(klien, pencarian_palsu, status):
    pencarian_palsu.status = status
    isi = kirim(klien).json()
    assert isi["pemeriksaan_terbatas"] == ["cek_fakta"]
    assert isi["tingkat"] == "hati_hati"  # logika tingkat tidak berubah


def test_pencarian_gagal_saat_dipakai_ditandai_cek_fakta(klien, pencarian_palsu):
    def rusak(teks, k):
        raise RuntimeError("gagal")

    pencarian_palsu.cari = rusak
    assert kirim(klien).json()["pemeriksaan_terbatas"] == ["cek_fakta"]


def test_mode_paksa_selalu_kosong_walau_pencarian_mati(klien, pencarian_palsu):
    pencarian_palsu.status = "nonaktif"
    for paksa in ("kuat", "hati_hati", "tidak_ditemukan"):
        assert kirim(klien, params={"paksa": paksa}).json()["pemeriksaan_terbatas"] == []


def test_pemeriksaan_terbatas_tidak_memuat_nama_penyedia_atau_isi_apa_pun(klien, pencarian_palsu):
    pencarian_palsu.status = "tidak_tersedia"
    assert set(kirim(klien).json()["pemeriksaan_terbatas"]) <= {"cek_fakta", "ai"}


# --- banner: alamat adaptor virtual ---

IPCONFIG_EN = """
Windows IP Configuration

Ethernet adapter vEthernet (WSL (Hyper-V firewall)):

   Connection-specific DNS Suffix  . :
   IPv4 Address. . . . . . . . . . . : 172.17.32.1
   Subnet Mask . . . . . . . . . . . : 255.255.240.0

Wireless LAN adapter Wi-Fi:

   IPv4 Address. . . . . . . . . . . : 10.20.189.110
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 10.20.189.1
"""

IPCONFIG_ID = """
Konfigurasi IP Windows

Adaptor Ethernet vEthernet (Default Switch):

   Alamat IPv4. . . . . . . . . . . : 172.20.0.1

Adaptor Wireless LAN Wi-Fi:

   Alamat IPv4. . . . . . . . . . . : 192.168.43.55
"""


def test_urai_ipconfig_inggris_dan_indonesia():
    assert main.urai_ipconfig(IPCONFIG_EN) == {
        "172.17.32.1": "vEthernet (WSL (Hyper-V firewall))", "10.20.189.110": "Wi-Fi",
    }
    peta = main.urai_ipconfig(IPCONFIG_ID)
    assert main.adaptor_virtual(peta["172.20.0.1"]) and not main.adaptor_virtual(peta["192.168.43.55"])


@pytest.mark.parametrize("nama,virtual", [
    ("vEthernet (WSL)", True), ("VirtualBox Host-Only Network", True), ("Docker NAT", True),
    ("Wi-Fi", False), ("Ethernet", False), ("Ethernet 2", False), ("", False),
])
def test_adaptor_virtual(nama, virtual):
    assert main.adaptor_virtual(nama) is virtual


def test_banner_menyembunyikan_adaptor_virtual_dan_melabeli_yang_nyata(monkeypatch, capsys):
    monkeypatch.setattr(main, "alamat_ipv4_lokal", lambda: ["10.20.189.110", "172.17.32.1"])
    monkeypatch.setattr(main, "_nama_adaptor", lambda: main.urai_ipconfig(IPCONFIG_EN))
    main._cetak_alamat()
    keluar = capsys.readouterr().out
    assert "http://10.20.189.110:8000   <- Wi-Fi" in keluar
    assert "172.17.32.1" not in keluar and "1 alamat adaptor virtual disembunyikan" in keluar


def test_banner_tanpa_ipconfig_menampilkan_semua_alamat_tanpa_label(monkeypatch, capsys):
    monkeypatch.setattr(main, "alamat_ipv4_lokal", lambda: ["10.0.0.5", "172.17.32.1"])
    monkeypatch.setattr(main, "_nama_adaptor", lambda: {})
    main._cetak_alamat()
    keluar = capsys.readouterr().out
    assert "http://10.0.0.5:8000" in keluar and "http://172.17.32.1:8000" in keluar


def test_banner_hanya_adaptor_virtual_tetap_menampilkannya_dengan_penanda(monkeypatch, capsys):
    monkeypatch.setattr(main, "alamat_ipv4_lokal", lambda: ["172.17.32.1"])
    monkeypatch.setattr(main, "_nama_adaptor", lambda: main.urai_ipconfig(IPCONFIG_EN))
    main._cetak_alamat()
    assert "(adaptor virtual)" in capsys.readouterr().out
