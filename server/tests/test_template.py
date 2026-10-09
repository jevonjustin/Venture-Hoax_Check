"""Memindai semua template: id/label/tingkat harus punya template, dan teks tidak boleh memuat kata ganti
orang kedua, vonis, atau angka persen."""

import re

import pytest

from app.pipeline import template
from app.pipeline.tipe import CiriTerdeteksi
from app.skema import ID_CIRI_TERKUNCI, Tingkat

LABEL_DATABASE = ["salah", "penipuan", "klarifikasi", "benar", "lainnya", "belum_terbukti", "satir"]

KATA_GANTI_KEDUA = {"kamu", "anda", "engkau", "kalian", "dirimu"}
# Kata berakhiran "mu" yang bukan kata ganti.
PENGECUALIAN_MU = {"ilmu", "temu", "bertemu", "ketemu", "menemu", "jamu", "tamu", "bertamu"}
FRASA_VONIS = [
    "adalah fakta", "merupakan fakta", "terbukti benar", "benar adanya", "dijamin", "pasti benar", "pasti salah",
    "tanpa diragukan", "sudah pasti", "informasi ini benar", "informasi ini salah", "dipastikan hoaks",
]
PENGECUALIAN_KALIMAT = ("bukan jaminan", "tidak menjamin")  # kalimat penyangkal boleh memuat frasa vonis


def kalimat(teks: str) -> list[str]:
    return [k for k in re.split(r"(?<=[.!?;])\s+", teks) if k]


def cari_pelanggaran(teks: str) -> list[str]:
    """Daftar pelanggaran di sebuah teks template. Pengecualian vonis hanya berlaku di dalam kalimat yang sama."""
    pelanggaran = []
    token = re.findall(r"[a-z]+(?:-[a-z]+)*", teks.lower())
    for t in token:
        if t in KATA_GANTI_KEDUA:
            pelanggaran.append(f"kata ganti: {t}")
        elif t.endswith("mu") and len(t) >= 4 and t not in PENGECUALIAN_MU:
            pelanggaran.append(f"akhiran -mu: {t}")
    if re.search(r"\d+\s*(?:%|persen)|\bpersen\b", teks.lower()):
        pelanggaran.append("angka persen")
    for k in kalimat(teks):
        bawah = k.lower()
        if any(p in bawah for p in PENGECUALIAN_KALIMAT):
            continue
        for frasa in FRASA_VONIS:
            if re.search(rf"\b{re.escape(frasa)}\b", bawah):
                pelanggaran.append(f"vonis: {frasa}")
    return pelanggaran


# ----- pemeriksa kata terlarang itu sendiri -----

@pytest.mark.parametrize("teks", [
    "Kamu perlu memeriksa ini", "Silakan cek sendiri, Anda berhak", "Kalian harus hati-hati", "Jaga dirimu baik-baik",
    "Tolong bukumu dicek", "Kau ... engkau",
])
def test_pemeriksa_menangkap_kata_ganti_orang_kedua(teks):
    assert cari_pelanggaran(teks)


@pytest.mark.parametrize("teks", ["Ilmu pengetahuan", "Ada tamu dan jamu", "Bertemu di sini", "Ketemu lagi", "Temu wicara"])
def test_pemeriksa_tidak_salah_tangkap_kata_berakhiran_mu_yang_bukan_kata_ganti(teks):
    assert cari_pelanggaran(teks) == []


@pytest.mark.parametrize("teks", [
    "Isi ini adalah fakta", "Berita itu merupakan fakta.", "Ini terbukti benar", "Benar adanya", "Hasil dijamin aman",
    "Kemungkinan 80% salah", "Sekitar 80 persen", "Ini sudah pasti",
])
def test_pemeriksa_menangkap_vonis_dan_persen(teks):
    assert cari_pelanggaran(teks)


def test_jaminan_tidak_kena_karena_dicek_per_kata():
    assert cari_pelanggaran("Ini bukan jaminan dan tidak ada jaminan apa pun") == []
    assert cari_pelanggaran("Ada jaminan uang kembali") == []
    assert cari_pelanggaran("Produk dijamin asli") != []


def test_cek_fakta_sebagai_jenis_artikel_boleh():
    assert cari_pelanggaran("Artikel cek fakta dari sebuah media membahas klaim yang mirip.") == []


def test_pengecualian_bukan_jaminan_hanya_berlaku_di_kalimat_yang_sama():
    # kalimat penyangkal yang menyebut frasa vonis: boleh
    assert cari_pelanggaran("Ini bukan jaminan bahwa informasi ini benar.") == []
    assert cari_pelanggaran("Ini tidak menjamin bahwa isinya adalah fakta.") == []
    # vonis di kalimat lain tidak ikut lolos
    assert cari_pelanggaran("Ini bukan jaminan. Informasi ini benar.") != []
    assert cari_pelanggaran("Informasi ini benar. Ini bukan jaminan.") != []
    assert cari_pelanggaran("Ini bukan jaminan; isinya adalah fakta.") != []  # titik koma memisahkan kalimat
    assert cari_pelanggaran("Ini bukan jaminan!\nIsinya terbukti benar.") != []


# ----- cakupan -----

def test_setiap_id_ciri_punya_nama_dan_penjelasan():
    assert set(template.NAMA) == set(ID_CIRI_TERKUNCI)
    assert set(template.PENJELASAN) == set(ID_CIRI_TERKUNCI)


def test_setiap_label_database_punya_template_sendiri_dan_label_tak_dikenal_memakai_cadangan():
    assert set(template.LABEL) == set(LABEL_DATABASE)
    cadangan = template.penjelasan_label("label-ngawur", "Sumber X", "Judul Y")
    assert cadangan == template.penjelasan_label(None, "Sumber X", "Judul Y")
    for label in LABEL_DATABASE:
        assert template.penjelasan_label(label, "Sumber X", "Judul Y") != cadangan


def test_setiap_tingkat_punya_judul_dan_keterangan():
    assert set(template.TINGKAT) == set(Tingkat)
    assert template.judul_tingkat(Tingkat.KUAT) == "Indikasi Kuat Hoaks"
    assert template.judul_tingkat(Tingkat.HATI_HATI) == "Perlu Hati-hati"
    assert template.judul_tingkat(Tingkat.TIDAK_DITEMUKAN) == "Tidak Ditemukan Indikasi Hoaks"


def test_tingkat_tidak_ditemukan_menyebut_bukan_jaminan():
    assert "bukan jaminan" in template.keterangan_tingkat(Tingkat.TIDAK_DITEMUKAN).lower()


# ----- kata terlarang pada semua template -----

@pytest.mark.parametrize("teks", template.semua_teks())
def test_semua_template_bebas_kata_terlarang(teks):
    assert cari_pelanggaran(teks) == [], teks


def test_template_label_terisi_juga_bebas_kata_terlarang():
    for label in LABEL_DATABASE + ["ngawur", None, ""]:
        for sumber, judul in [("Turnbackhoax", "[SALAH] Judul Artikel"), (None, None), ("", " ")]:
            teks = template.penjelasan_label(label, sumber, judul)
            assert cari_pelanggaran(teks) == [], teks


def test_label_benar_dan_klarifikasi_diatribusikan_ke_artikel_dan_tidak_menyiratkan_isi_layar_benar():
    for label in ("benar", "klarifikasi"):
        teks = template.LABEL[label]
        assert "{sumber}" in teks and "artikel" in teks.lower()
        assert "isi layar" in teks.lower() and "tetap" in teks.lower()  # mengajak memeriksa


def test_label_satir_menjelaskan_satir_atau_parodi_dan_berbeda_dari_salah():
    teks = template.penjelasan_label("satir", "Sumber X", "Judul Y").lower()
    assert "satir" in teks and "parodi" in teks
    assert template.LABEL["satir"] != template.LABEL["salah"]


def test_placeholder_kosong_ditangani_aman():
    teks = template.penjelasan_label("salah", None, None)
    assert "{" not in teks and "}" not in teks and "berjudul" not in teks
    assert template.SUMBER_CADANGAN in teks
    terisi = template.penjelasan_label("salah", "Turnbackhoax", "Air keran")
    assert "Turnbackhoax" in terisi and "berjudul \"Air keran\"" in terisi
    assert "{" not in template.penjelasan_label("benar", "  ", "")


def test_template_tautan_tidak_menyatakan_tautan_berbahaya_dan_tidak_menjamin_domain_resmi():
    teks = template.PENJELASAN["link_mencurigakan"].lower()
    assert "tujuan" in teks and "tidak terlihat" in teks
    assert "bukan tanda bahaya" in teks
    for terlarang in ("berbahaya", "penipuan", "go.id", "ac.id", "resmi pasti", "aman"):
        assert terlarang not in teks


def test_susun_penjelasan_mempertahankan_urutan_dan_bukti():
    ciri = [CiriTerdeteksi("desakan_waktu", ["sebelum dihapus"], "tinggi"), CiriTerdeteksi("judul_clickbait", ["viral"], "sedang")]
    hasil = template.susun_penjelasan(ciri)
    assert [c.id for c in hasil] == ["desakan_waktu", "judul_clickbait"]
    assert hasil[1].nama == template.NAMA["judul_clickbait"] and hasil[0].bukti == ["sebelum dihapus"]
    assert hasil[0].penjelasan == template.PENJELASAN["desakan_waktu"]
