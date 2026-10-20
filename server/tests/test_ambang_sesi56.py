"""Perilaku baru Sesi 5.6 di balik Pengaturan (bawaan mati = perilaku lama): kuat lewat kombinasi skor dan
relevansi, batas lolos tanpa syarat peringkat 1, dan toleransi salah eja OCR pada relevansi."""

import dataclasses
from datetime import date

import pytest

from app.konfigurasi import Pengaturan
from app.pipeline import cocok, tingkat
from app.pipeline.tipe import Kandidat
from app.skema import Tingkat

TEKS = "Ratusan kepala desa ditangkap polisi karena korupsi dana desa di Jawa Tengah. Sebarkan."
JUDUL_PANJANG = "[SALAH] Ratusan Kepala Desa Ditangkap Polisi karena Korupsi Dana"  # 6 kata isi ada di teks
JUDUL_PENDEK = "[SALAH] Kepala Desa Ditangkap"  # 3 kata isi

BAWAAN = Pengaturan()
KOMBINASI = dataclasses.replace(BAWAAN, kuat_kombinasi_aktif=True, kuat_kombinasi_skor=0.855)


def art(skor, relevansi, label="salah", judul=JUDUL_PANJANG) -> Kandidat:
    return Kandidat(
        judul=judul, sumber="TBH", url=f"https://example.test/{label}-{skor}-{relevansi}", skor=skor, label=label,
        tanggal=date(2025, 1, 1), url_format_lama=False, narasi="", relevansi=relevansi,
    )


def putus(kandidat, cfg):
    return tingkat.tentukan([], kandidat, TEKS, cfg)


# --- kombinasi skor dan relevansi ---


def test_bawaan_kombinasi_mati_sama_dengan_perilaku_lama():
    assert BAWAAN.kuat_kombinasi_aktif is False
    p = putus([art(0.86, 0.9)], BAWAAN)
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_MIRIP
    assert p.ciri_dibantah.keyakinan == "sedang"


def test_kombinasi_menaikkan_mirip_relevan_ke_kuat():
    p = putus([art(0.86, 0.9)], KOMBINASI)
    assert p.tingkat is Tingkat.KUAT and p.varian == ""
    assert p.ciri_dibantah.keyakinan == "tinggi"


@pytest.mark.parametrize(
    "skor,relevansi,judul",
    [
        (0.85, 0.9, JUDUL_PANJANG),  # skor di bawah kuat_kombinasi_skor
        (0.86, 0.69, JUDUL_PANJANG),  # relevansi di bawah kuat_kombinasi_relevansi
        (0.86, 1.0, JUDUL_PENDEK),  # judul pendek: hanya 3 kata isi judul ada di teks
    ],
)
def test_kombinasi_tidak_berlaku_di_bawah_syarat(skor, relevansi, judul):
    p = putus([art(skor, relevansi, judul=judul)], KOMBINASI)
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_MIRIP


def test_kombinasi_batas_tepat_dihitung_cocok():
    cfg = dataclasses.replace(KOMBINASI, kuat_kombinasi_skor=0.86, kuat_kombinasi_relevansi=0.70)
    assert putus([art(0.86, 0.70)], cfg).tingkat is Tingkat.KUAT


def test_kombinasi_tetap_kalah_oleh_konflik():
    p = putus([art(0.87, 0.9, label="benar", judul="Kepala desa ditangkap: penjelasan"), art(0.86, 0.9)], KOMBINASI)
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_KONFLIK


def test_kombinasi_tidak_berlaku_untuk_label_lain():
    for label in ("benar", "klarifikasi", "satir", "lainnya"):
        p = putus([art(0.87, 1.0, label=label)], KOMBINASI)
        assert p.tingkat is not Tingkat.KUAT


def test_kombinasi_memilih_penentu_yang_cocok_bila_yang_teratas_tidak():
    # Peringkat 1 relevan tetapi judul pendek; peringkat 2 memenuhi kombinasi: penentunya peringkat 2.
    p = putus([art(0.87, 1.0, judul=JUDUL_PENDEK), art(0.86, 0.9)], KOMBINASI)
    assert p.tingkat is Tingkat.KUAT
    assert p.cek_fakta[0].skor == 0.87  # tampilan tetap urut skor


def test_kombinasi_tidak_mengubah_artikel_tak_relevan():
    # relevansi di bawah relevansi_minimum: tersaring lebih dulu, kombinasi tidak dinilai
    p = putus([art(0.87, 0.3)], dataclasses.replace(KOMBINASI, kuat_kombinasi_relevansi=0.2))
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN


# --- batas lolos tanpa syarat untuk peringkat 1 ---


def test_bawaan_lolos_mengikuti_ambang_cocok():
    assert BAWAAN.relevansi_lolos_skor is None
    p = putus([art(0.885, 0.05)], BAWAAN)  # tidak relevan, tetapi peringkat 1 >= 0,88: lolos (perilaku lama)
    assert p.tingkat is Tingkat.KUAT


def test_lolos_090_menyaring_peringkat_satu_tak_relevan_di_bawahnya():
    cfg = dataclasses.replace(BAWAAN, relevansi_lolos_skor=0.90)
    p = putus([art(0.885, 0.05)], cfg)
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN and len(p.tersaring) == 1
    # yang relevan tidak terpengaruh, dan skor >= batas tetap lolos
    assert putus([art(0.885, 0.5)], cfg).tingkat is Tingkat.KUAT
    assert putus([art(0.90, 0.05)], cfg).tingkat is Tingkat.KUAT


def test_lolos_menurun_ke_mirip_yang_relevan():
    cfg = dataclasses.replace(BAWAAN, relevansi_lolos_skor=0.90)
    p = putus([art(0.885, 0.05), art(0.86, 0.5)], cfg)
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_MIRIP


# --- toleransi salah eja OCR pada relevansi ---

IDF = {"menkeu": 3.0, "fiktiwan": 5.0, "korupsi": 1.0}
TOLERAN = dataclasses.replace(BAWAAN, relevansi_toleransi_ocr=True)


def test_bawaan_toleransi_mati():
    kata = cocok.kata_isi("Menkeu Fiktlwam korupsi")
    assert BAWAAN.relevansi_toleransi_ocr is False
    assert cocok.relevansi_judul(kata, "Menkeu Fiktiwan korupsi", IDF, 10, BAWAAN) == pytest.approx(4 / 9)


def test_toleransi_menerima_salah_eja_nama():
    kata = cocok.kata_isi("Menkeu Fiktlwam korupsi")
    assert cocok.relevansi_judul(kata, "Menkeu Fiktiwan korupsi", IDF, 10, TOLERAN) == pytest.approx(1.0)
    assert cocok.kata_judul_di_teks(kata, "Menkeu Fiktiwan korupsi", TOLERAN) == 3
    assert cocok.kata_judul_di_teks(kata, "Menkeu Fiktiwan korupsi", BAWAAN) == 2


@pytest.mark.parametrize(
    "judul,teks",
    [
        ("pajak", "pajek"),  # 5 huruf, jarak 1: diterima
        ("presiden", "presidan"),  # >= 7 huruf, jarak 1
        ("presiden", "prisidan"),  # >= 7 huruf, jarak 2
    ],
)
def test_toleransi_batas_diterima(judul, teks):
    assert cocok.kata_judul_di_teks({teks}, judul, TOLERAN) == 1


@pytest.mark.parametrize(
    "judul,teks",
    [
        ("desa", "desi"),  # 4 huruf: harus persis
        ("pajak", "pojek"),  # 5 huruf, jarak 2
        ("presiden", "prasudan"),  # jarak 3
        ("2026", "2025"),  # tahun: harus persis
        ("rp500ribu", "rp600ribu"),  # memuat angka
    ],
)
def test_toleransi_batas_ditolak(judul, teks):
    assert cocok.kata_judul_di_teks({teks}, judul, TOLERAN) == 0


def test_pencarian_memakai_toleransi_dari_pengaturan_global(monkeypatch):
    from app import konfigurasi

    kata = cocok.kata_isi("Menkeu Fiktlwam korupsi")
    monkeypatch.setattr(konfigurasi.pengaturan, "relevansi_toleransi_ocr", True)
    assert cocok.relevansi_judul(kata, "Menkeu Fiktiwan korupsi", IDF, 10) == pytest.approx(1.0)


# --- profil akhir: jalur server sama dengan alat evaluasi ---


def test_server_dan_alat_evaluasi_memakai_konfigurasi_profil_akhir_yang_sama(monkeypatch, tmp_path):
    import importlib.util
    from pathlib import Path

    from app import konfigurasi

    jalur = Path(__file__).resolve().parents[1] / "alat" / "uji_analisis" / "evaluasi_berlabel.py"
    spec = importlib.util.spec_from_file_location("evaluasi_berlabel_profil", jalur)
    alat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alat)
    # main() alat menimpa Pengaturan global; dikembalikan monkeypatch setelah tes.
    for k, v in dataclasses.asdict(Pengaturan()).items():
        monkeypatch.setattr(konfigurasi.pengaturan, k, v)
    assert alat.main(["--akar", str(tmp_path), "--log", "", "--profil", "akhir", "ringkas-token"]) == 0
    assert dataclasses.asdict(konfigurasi.pengaturan) == dataclasses.asdict(konfigurasi.muat({}))
    # String profil akhir laporan T7 (penyetelan dev) termasuk di profil akhir server; teks kembali ke 20
    # (keputusan produk setelah set uji, RANCANGAN §11).
    t7 = alat.urai_ambang(
        "toleransi_ocr=ya,kombinasi=ya,kombinasi_skor=0.855,kombinasi_relevansi=0.70,kombinasi_kata=4,lolos=0.90,teks=20"
    )
    assert t7.items() <= konfigurasi.PROFIL_AMBANG["akhir"].items()


def test_pencarian_server_menghitung_relevansi_dengan_pengaturan_saat_dimuat(tmp_path):
    from test_cocok import pencarian_siap

    teks = "Beredar pesan air keran Jakrta mengandng zat berbahaya penyebab penyakit"
    judul = "[SALAH] Air keran Jakarta mengandung zat berbahaya"

    def relevansi(p):
        return next(k.relevansi for k in p.cari(teks, 4) if k.judul == judul)

    toleran, _ = pencarian_siap(tmp_path / "toleran", relevansi_toleransi_ocr=True)
    persis, _ = pencarian_siap(tmp_path / "persis")
    assert relevansi(toleran) == pytest.approx(1.0)
    assert relevansi(persis) < 1.0
