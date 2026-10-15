"""Varian keterangan tingkat: ciri saja, artikel mirip, satir, konflik label, dan rujukan. Semuanya dipindai
pemeriksa kata terlarang yang sama dengan test_template.py."""

import pytest

from app.pipeline import template
from app.skema import Tingkat
from test_template import cari_pelanggaran

VARIAN_DIHARAPKAN = [
    (Tingkat.HATI_HATI, "ciri_saja"), (Tingkat.HATI_HATI, "mirip"), (Tingkat.HATI_HATI, "satir"),
    (Tingkat.HATI_HATI, "konflik"), (Tingkat.TIDAK_DITEMUKAN, "rujukan"),
]


def test_semua_varian_keterangan_tingkat_ada_dan_berbeda_satu_sama_lain():
    assert set(template.VARIAN_TINGKAT) == set(VARIAN_DIHARAPKAN)
    teks = [template.keterangan_tingkat(t, v) for t, v in VARIAN_DIHARAPKAN]
    assert len(set(teks)) == len(teks)


@pytest.mark.parametrize("tingkat,varian", VARIAN_DIHARAPKAN)
def test_varian_keterangan_tingkat_bebas_kata_terlarang(tingkat, varian):
    assert cari_pelanggaran(template.keterangan_tingkat(tingkat, varian)) == []


def test_varian_tidak_dikenal_atau_kosong_memakai_keterangan_bawaan():
    assert template.keterangan_tingkat(Tingkat.KUAT) == template.TINGKAT[Tingkat.KUAT][1]
    assert template.keterangan_tingkat(Tingkat.KUAT, "ngawur") == template.TINGKAT[Tingkat.KUAT][1]
    assert template.keterangan_tingkat(Tingkat.HATI_HATI, "ngawur") == template.TINGKAT[Tingkat.HATI_HATI][1]


def test_keterangan_hati_hati_tidak_mengklaim_artikel_tidak_ada_dan_tidak_menyebut_beberapa_ciri():
    for varian in ("ciri_saja", "mirip", "satir", "konflik"):
        teks = template.keterangan_tingkat(Tingkat.HATI_HATI, varian).lower()
        assert "belum ada artikel cek fakta yang cocok" not in teks and "beberapa ciri" not in teks
    assert template.keterangan_tingkat(Tingkat.HATI_HATI, "ciri_saja") == template.TINGKAT[Tingkat.HATI_HATI][1]


def test_varian_konflik_menyebut_kesimpulan_berbeda_dan_mengajak_membaca_keduanya():
    teks = template.keterangan_tingkat(Tingkat.HATI_HATI, "konflik").lower()
    assert "kesimpulan berbeda" in teks and "dibaca langsung" in teks


def test_varian_satir_menjelaskan_satir_dan_tidak_menyatakan_salah():
    teks = template.keterangan_tingkat(Tingkat.HATI_HATI, "satir").lower()
    assert "satir" in teks and "parodi" in teks and "hoaks" not in teks


def test_varian_rujukan_tetap_menyebut_bukan_jaminan():
    assert "bukan jaminan" in template.keterangan_tingkat(Tingkat.TIDAK_DITEMUKAN, "rujukan").lower()


def test_semua_varian_ikut_dipindai_lewat_semua_teks():
    for teks in template.VARIAN_TINGKAT.values():
        assert teks in template.semua_teks()
