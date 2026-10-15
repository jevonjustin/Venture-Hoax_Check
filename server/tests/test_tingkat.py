"""Logika tingkat: semua cabang, termasuk konflik label (unggul jelas, berdekatan, kalah)."""

from datetime import date

import pytest

from app.konfigurasi import Pengaturan
from app.pipeline import tingkat
from app.pipeline.tipe import CiriTerdeteksi, Kandidat
from app.skema import Tingkat

TEKS = "Air keran di Jakarta mengandung zat berbahaya penyebab penyakit misterius.\nSebarkan ke semua keluarga."
CFG = Pengaturan()  # ambang_cocok 0,88; ambang_mirip 0,85; selisih_konflik 0,02


def art(label: str, skor: float, judul: str = "Air keran Jakarta mengandung zat berbahaya", **kw) -> Kandidat:
    return Kandidat(
        judul=judul, sumber="TurnBackHoax", url=f"https://example.test/{label}-{skor}", skor=skor, label=label,
        tanggal=date(2025, 11, 4), url_format_lama=False, narasi=kw.pop("narasi", "Beredar pesan air keran Jakarta."),
        **kw,
    )


CIRI = [CiriTerdeteksi("ajakan_menyebarkan", ["Sebarkan ke semua keluarga"], "tinggi")]


def putus(kandidat, ciri=(), cfg=CFG):
    return tingkat.tentukan(list(ciri), kandidat, TEKS, cfg)


# --- kuat ---


@pytest.mark.parametrize("label", ["salah", "penipuan"])
def test_kuat_bila_salah_atau_penipuan_di_atas_ambang_cocok(label):
    p = putus([art(label, 0.90)])
    assert p.tingkat is Tingkat.KUAT and p.varian == ""
    assert p.ciri_dibantah.id == "pernah_dibantah" and p.ciri_dibantah.keyakinan == "tinggi"
    assert p.ciri_dibantah.bukti == ["Air keran di Jakarta mengandung zat berbahaya"]  # bagian yang sama dengan artikel


def test_tepat_di_ambang_cocok_dihitung_cocok():
    assert putus([art("salah", 0.88)]).tingkat is Tingkat.KUAT


def test_kuat_tidak_bergantung_pada_ciri():
    assert putus([art("salah", 0.9)], CIRI).tingkat is Tingkat.KUAT
    assert putus([art("salah", 0.9)]).tingkat is Tingkat.KUAT


# --- konflik label: unggul jelas, berdekatan, kalah ---


@pytest.mark.parametrize("label", ["benar", "klarifikasi", "satir"])
def test_unggul_jelas_dari_artikel_berlabel_lain_tetap_kuat(label):
    p = putus([art("salah", 0.92), art(label, 0.89)])  # selisih 0,03 > 0,02
    assert p.tingkat is Tingkat.KUAT and p.ciri_dibantah.keyakinan == "tinggi"


@pytest.mark.parametrize("label", ["benar", "klarifikasi", "satir"])
def test_berdekatan_menjadi_hati_hati_varian_konflik(label):
    p = putus([art("salah", 0.90), art(label, 0.88)])  # selisih tepat 0,02 dihitung berdekatan
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_KONFLIK
    assert p.ciri_dibantah.keyakinan == "sedang"  # sistem sendiri tidak yakin saat ada kesimpulan berbeda
    assert {k.label for k in p.cek_fakta} == {"salah", label}


@pytest.mark.parametrize("label", ["benar", "klarifikasi", "satir"])
def test_kalah_dari_artikel_berlabel_lain_menjadi_hati_hati_varian_konflik(label):
    p = putus([art(label, 0.93), art("salah", 0.89)])
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_KONFLIK
    assert [k.label for k in p.cek_fakta] == [label, "salah"]  # urutan skor


@pytest.mark.parametrize("label", ["lainnya", "belum_terbukti"])
def test_label_lainnya_dan_belum_terbukti_tidak_dihitung_konflik(label):
    p = putus([art(label, 0.95), art("salah", 0.89)])
    assert p.tingkat is Tingkat.KUAT


def test_artikel_berlabel_lain_di_bawah_ambang_mirip_tidak_berpengaruh():
    p = putus([art("salah", 0.89), art("benar", 0.80)])
    assert p.tingkat is Tingkat.KUAT and [k.label for k in p.cek_fakta] == ["salah"]


# --- hati_hati ---


def test_salah_di_rentang_mirip_hati_hati_dengan_ciri_sedang():
    p = putus([art("salah", 0.86)])
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_MIRIP
    assert p.ciri_dibantah.keyakinan == "sedang"


def test_tepat_di_ambang_mirip_masuk():
    assert putus([art("penipuan", 0.85)]).varian == tingkat.VARIAN_MIRIP


def test_ciri_tanpa_kecocokan_hati_hati_tidak_pernah_kuat():
    p = putus([], CIRI)
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_CIRI_SAJA and p.ciri_dibantah is None


def test_ciri_dengan_artikel_di_bawah_ambang_tetap_ciri_saja_dan_artikel_tidak_tampil():
    p = putus([art("salah", 0.80)], CIRI)
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_CIRI_SAJA and p.cek_fakta == []


def test_satir_cocok_hati_hati_varian_satir_tanpa_ciri_pernah_dibantah():
    p = putus([art("satir", 0.90)])
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_SATIR and p.ciri_dibantah is None
    assert [k.label for k in p.cek_fakta] == ["satir"]


def test_satir_hanya_mirip_tidak_menaikkan_tingkat():
    p = putus([art("satir", 0.86)])
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN and p.varian == tingkat.VARIAN_RUJUKAN


def test_sakelar_satir_dimatikan():
    p = putus([art("satir", 0.90)], cfg=Pengaturan(satir_hati_hati=False))
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN


def test_satir_cocok_mengalahkan_salah_yang_hanya_mirip():
    p = putus([art("satir", 0.90), art("salah", 0.86)])
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_SATIR
    assert p.ciri_dibantah is not None and p.ciri_dibantah.keyakinan == "sedang"


# --- tidak_ditemukan ---


def test_tanpa_ciri_dan_tanpa_kecocokan_tidak_ditemukan():
    p = putus([])
    assert (p.tingkat, p.varian, p.ciri_dibantah, p.cek_fakta) == (Tingkat.TIDAK_DITEMUKAN, "", None, [])


@pytest.mark.parametrize("label", ["benar", "klarifikasi", "lainnya", "belum_terbukti"])
def test_label_non_salah_tidak_menaikkan_tingkat_tetapi_tetap_ditampilkan(label):
    p = putus([art(label, 0.95)])
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN and p.varian == tingkat.VARIAN_RUJUKAN
    assert p.ciri_dibantah is None and [k.label for k in p.cek_fakta] == [label]


def test_label_non_salah_dengan_ciri_menjadi_hati_hati_ciri_saja_dan_artikel_tampil():
    p = putus([art("benar", 0.95)], CIRI)
    assert p.tingkat is Tingkat.HATI_HATI and p.varian == tingkat.VARIAN_CIRI_SAJA
    assert [k.label for k in p.cek_fakta] == ["benar"]


def test_label_dibandingkan_tanpa_peduli_huruf_besar_dan_spasi():
    assert putus([art(" Salah ", 0.9)]).tingkat is Tingkat.KUAT


# --- artikel yang ditampilkan ---


def test_cek_fakta_dibatasi_dan_diurutkan_dari_skor_tertinggi():
    kandidat = [art("lainnya", 0.86 + i / 100, judul=f"J{i}") for i in range(5)]
    p = putus(kandidat, cfg=Pengaturan(cek_fakta_maks=3))
    assert len(p.cek_fakta) == 3
    assert [k.skor for k in p.cek_fakta] == sorted((k.skor for k in p.cek_fakta), reverse=True)


def test_artikel_penentu_tidak_terpotong_batas_tampilan():
    kandidat = [art("lainnya", 0.99, judul="a"), art("lainnya", 0.98, judul="b"), art("lainnya", 0.97, judul="c"),
                art("salah", 0.89)]
    p = putus(kandidat, cfg=Pengaturan(cek_fakta_maks=3))
    assert "salah" in [k.label for k in p.cek_fakta] and len(p.cek_fakta) == 3
    assert p.tingkat is Tingkat.KUAT  # 'lainnya' bukan konflik


def test_kandidat_tidak_berurutan_tetap_benar():
    p = putus([art("benar", 0.5), art("salah", 0.9), art("lainnya", 0.7)])
    assert p.tingkat is Tingkat.KUAT


def test_ambang_dari_konfigurasi_dipakai():
    cfg = Pengaturan(ambang_cocok=0.95, ambang_mirip=0.90)
    assert putus([art("salah", 0.93)], cfg=cfg).varian == tingkat.VARIAN_MIRIP
    assert putus([art("salah", 0.96)], cfg=cfg).tingkat is Tingkat.KUAT
    assert putus([art("salah", 0.89)], cfg=cfg).tingkat is Tingkat.TIDAK_DITEMUKAN


# ----- Sesi 5.5: ciri sedang tunggal tidak menaikkan tingkat -----


def _ciri(id_, keyakinan):
    from app.pipeline.tipe import CiriTerdeteksi

    return CiriTerdeteksi(id_, ["bukti sah ini"], keyakinan)


def test_satu_ciri_sedang_tunggal_tidak_ditemukan_dan_dibuang():
    c = _ciri("bahasa_provokatif", "sedang")
    p = tingkat.tentukan([c], [], "teks")
    assert p.tingkat is Tingkat.TIDAK_DITEMUKAN and p.ciri_dibuang == [c]


def test_satu_ciri_tinggi_atau_dua_ciri_sedang_hati_hati():
    tinggi = tingkat.tentukan([_ciri("desakan_waktu", "tinggi")], [], "teks")
    assert tinggi.tingkat is Tingkat.HATI_HATI and tinggi.varian == tingkat.VARIAN_CIRI_SAJA and tinggi.ciri_dibuang == []
    dua = tingkat.tentukan([_ciri("desakan_waktu", "sedang"), _ciri("bahasa_provokatif", "sedang")], [], "teks")
    assert dua.tingkat is Tingkat.HATI_HATI and dua.ciri_dibuang == []
