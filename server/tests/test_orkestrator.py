"""/analisis ujung ke ujung dengan pembaca dan pencarian palsu: tingkat, ciri, cek_fakta, dan ambang teks."""

import io
import logging
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.konfigurasi import pengaturan
from app.pipeline import baca
from app.pipeline.tipe import Kandidat
from conftest import PembacaPalsu

KLAIM = "Air keran di Jakarta mengandung zat berbahaya penyebab penyakit misterius."
TEKS_HOAKS = f"{KLAIM}\nSEBARKAN ke semua keluarga sebelum dihapus!!!"
TEKS_NETRAL = (
    "Pemerintah kota mengumumkan perbaikan jalan di Jalan Merdeka pada 12-14 Oktober.\n"
    "Pengendara diimbau memakai jalur alternatif selama pekerjaan berlangsung."
)
POTONGAN_UI = "Beranda\nBagikan\nKomentar\nSuka\nBalas\nLihat terjemahan\nTulis komentar\n09.41\nKirim pesan\nBerlangganan"


@pytest.fixture(autouse=True)
def tanpa_paksa(monkeypatch):
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)
    monkeypatch.setattr(pengaturan, "ambang_teks_karakter", 20)


@pytest.fixture
def klien():
    return TestClient(main.app)


def teks_layar(monkeypatch, teks: str) -> None:
    monkeypatch.setattr(baca, "pembaca", PembacaPalsu(teks))


def kirim(klien, params=None):
    keluaran = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 10)).save(keluaran, format="JPEG")
    return klien.post("/analisis", params=params, files={"gambar": ("p.jpg", keluaran.getvalue(), "image/jpeg")})


def art(label="salah", skor=0.9, judul="[SALAH] Air keran Jakarta mengandung zat berbahaya", **kw) -> Kandidat:
    return Kandidat(
        judul=judul, sumber="TurnBackHoax", url="https://turnbackhoax.id/articles/1-air-keran", skor=skor, label=label,
        tanggal=kw.pop("tanggal", date(2025, 11, 4)), url_format_lama=kw.pop("url_format_lama", False),
        narasi="Beredar pesan air keran Jakarta mengandung zat berbahaya.",
    )


def test_kecocokan_salah_menghasilkan_kuat_dengan_pernah_dibantah_dan_artikel(monkeypatch, klien, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    pencarian_palsu.kandidat = [art(skor=0.9123)]
    isi = kirim(klien).json()
    assert isi["tingkat"] == "kuat"
    assert isi["ciri"][0]["id"] == "pernah_dibantah"
    dibantah = isi["ciri"][0]
    assert dibantah["keyakinan"] == "tinggi" and dibantah["bukti"] == ["Air keran di Jakarta mengandung zat berbahaya"]
    assert dibantah["bukti"][0] in KLAIM and KLAIM in isi["teks_terbaca"]
    assert {"ajakan_menyebarkan", "desakan_waktu"} <= {c["id"] for c in isi["ciri"]}
    assert isi["cek_fakta"] == [{
        "judul": "[SALAH] Air keran Jakarta mengandung zat berbahaya", "sumber": "TurnBackHoax",
        "url": "https://turnbackhoax.id/articles/1-air-keran", "skor_kemiripan": 0.9123, "label": "salah",
        "tanggal": "2025-11-04", "url_format_lama": False,
    }]
    assert isi["klaim_utama"]


def test_kueri_pencarian_memakai_teks_bersih(monkeypatch, klien, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    isi = kirim(klien).json()
    assert pencarian_palsu.kueri == [isi["teks_terbaca"]] == [TEKS_HOAKS]


def test_url_format_lama_dan_tanggal_kosong_diteruskan(monkeypatch, klien, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    pencarian_palsu.kandidat = [art(url_format_lama=True, tanggal=None)]
    artikel = kirim(klien).json()["cek_fakta"][0]
    assert artikel["url_format_lama"] is True and artikel["tanggal"] is None


def test_konflik_label_menjadi_hati_hati_dengan_dua_artikel(monkeypatch, klien, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    pencarian_palsu.kandidat = [art("klarifikasi", 0.91, judul="[KLARIFIKASI] Air keran aman"), art("salah", 0.90)]
    isi = kirim(klien).json()
    assert isi["tingkat"] == "hati_hati"
    assert [a["label"] for a in isi["cek_fakta"]] == ["klarifikasi", "salah"]
    assert isi["ciri"][0]["id"] == "pernah_dibantah" and isi["ciri"][0]["keyakinan"] == "sedang"


def test_ciri_tanpa_kecocokan_hati_hati_bukan_kuat(monkeypatch, klien):
    teks_layar(monkeypatch, TEKS_HOAKS)
    isi = kirim(klien).json()
    assert isi["tingkat"] == "hati_hati" and isi["cek_fakta"] == []
    assert "pernah_dibantah" not in {c["id"] for c in isi["ciri"]}


def test_teks_netral_tanpa_kecocokan_tidak_ditemukan(monkeypatch, klien):
    teks_layar(monkeypatch, TEKS_NETRAL)
    isi = kirim(klien).json()
    assert isi["tingkat"] == "tidak_ditemukan" and isi["ciri"] == [] and isi["cek_fakta"] == []
    assert isi["klaim_utama"] and "Jalan Merdeka" in isi["klaim_utama"]


def test_artikel_non_salah_tampil_sebagai_rujukan_tanpa_menaikkan_tingkat(monkeypatch, klien, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_NETRAL)
    pencarian_palsu.kandidat = [art("klarifikasi", 0.93, judul="[KLARIFIKASI] Perbaikan Jalan Merdeka")]
    isi = kirim(klien).json()
    assert isi["tingkat"] == "tidak_ditemukan" and isi["cek_fakta"][0]["label"] == "klarifikasi"


def test_artikel_di_bawah_ambang_mirip_tidak_tampil(monkeypatch, klien, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_NETRAL)
    pencarian_palsu.kandidat = [art("salah", 0.80)]
    isi = kirim(klien).json()
    assert isi["tingkat"] == "tidak_ditemukan" and isi["cek_fakta"] == []


def test_pencarian_tidak_tersedia_tidak_menggagalkan_analisis(monkeypatch, klien, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    pencarian_palsu.status = "tidak_tersedia"
    r = kirim(klien)
    assert r.status_code == 200 and r.json()["tingkat"] == "hati_hati"


# --- ambang teks_tidak_terbaca dari teks bersih ---


def test_potongan_yang_hanya_berisi_ui_menjadi_teks_tidak_terbaca(monkeypatch, klien, caplog):
    teks_layar(monkeypatch, POTONGAN_UI)
    assert sum(c.isalnum() for c in POTONGAN_UI) > pengaturan.ambang_teks_karakter  # teks mentah lolos ambang lama
    caplog.set_level(logging.INFO)
    r = kirim(klien)
    assert r.status_code == 422 and r.json()["galat"]["kode"] == "teks_tidak_terbaca"
    assert "Beranda" not in "\n".join(m.getMessage() for m in caplog.records)


def test_ui_ditambah_teks_isi_yang_cukup_tetap_lolos(monkeypatch, klien):
    teks_layar(monkeypatch, POTONGAN_UI + "\n" + TEKS_NETRAL)
    r = kirim(klien)
    assert r.status_code == 200 and "Jalan Merdeka" in r.json()["teks_terbaca"]


def test_ambang_dihitung_dari_teks_bersih_dengan_ambang_yang_sama(monkeypatch, klien):
    teks_layar(monkeypatch, "Jalan Merdeka ditutup besok")  # 24 huruf-angka
    assert kirim(klien).status_code == 200
    monkeypatch.setattr(pengaturan, "ambang_teks_karakter", 25)
    assert kirim(klien).json()["galat"]["kode"] == "teks_tidak_terbaca"


def test_mode_paksa_melewati_ambang_teks_bersih(monkeypatch, klien):
    teks_layar(monkeypatch, POTONGAN_UI)
    assert kirim(klien, params={"paksa": "hati_hati"}).status_code == 200
