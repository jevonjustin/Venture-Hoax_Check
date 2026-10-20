"""Tahap B ujung ke ujung (LLM, pencarian, dan pembaca palsu): klaim, kutipan, privasi, pemeriksaan_terbatas,
tautan terpecah, dan perbaikan klaim heuristik."""

import dataclasses
import io
import logging

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.konfigurasi import Pengaturan, pengaturan
from app.pipeline import baca, klaim, llm
from app.pipeline.tipe import CiriTerdeteksi, KandidatLLM
from conftest import PembacaPalsu

KLAIM_ASLI = "Air keran di Jakarta mengandung zat berbahaya penyebab penyakit misterius."
TEKS_HOAKS = f"{KLAIM_ASLI}\nSEBARKAN ke semua keluarga sebelum dihapus!!!"


@pytest.fixture(autouse=True)
def tanpa_paksa(monkeypatch):
    monkeypatch.setattr(pengaturan, "paksa_tingkat", None)
    monkeypatch.setattr(pengaturan, "llm_aktif", True)
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


def hasil_llm(klaim_utama="", *kandidat: KandidatLLM, penyedia="groq"):
    return llm.HasilLLM(klaim_utama, list(kandidat), penyedia, 800)


# --- klaim utama ---


def test_klaim_llm_yang_setia_dipakai(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = hasil_llm("Air keran di Jakarta mengandung zat berbahaya")
    isi = kirim(klien).json()
    assert isi["klaim_utama"] == "Air keran di Jakarta mengandung zat berbahaya"
    assert isi["pemeriksaan_terbatas"] == []


def test_klaim_llm_yang_mengarang_diganti_klaim_heuristik(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = hasil_llm("Presiden mengumumkan kenaikan harga beras nasional bulan depan")
    isi = kirim(klien).json()
    assert "Presiden" not in (isi["klaim_utama"] or "")
    assert isi["klaim_utama"] and "Air keran" in isi["klaim_utama"]


def test_klaim_llm_dengan_kata_penilaian_di_luar_teks_diganti(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = hasil_llm("Ini hoaks: air keran di Jakarta mengandung zat berbahaya")
    assert "hoaks" not in kirim(klien).json()["klaim_utama"].lower()


def test_klaim_llm_kosong_memakai_heuristik(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = hasil_llm("")
    assert "Air keran" in kirim(klien).json()["klaim_utama"]


# --- ciri dari LLM dan verifikasi kutipan ---


def test_kandidat_llm_hanya_diterima_bila_kutipan_ada_di_teks(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, "Warga resah karena kabar air keran tercemar zat berbahaya di seluruh kota Jakarta")
    llm_palsu.hasil = hasil_llm(
        "", KandidatLLM("bahasa_provokatif", ["Warga resah karena kabar air keran tercemar"]),
        KandidatLLM("desakan_waktu", ["kabar air keran tercemar zat berbahaya"]),
        KandidatLLM("judul_clickbait", ["kalimat ini sama sekali tidak ada di layar"]),
    )
    isi = kirim(klien).json()
    ciri = {c["id"]: c for c in isi["ciri"]}
    assert set(ciri) == {"bahasa_provokatif", "desakan_waktu"}
    assert ciri["bahasa_provokatif"]["keyakinan"] == "sedang"  # hanya LLM, tanpa regex
    assert ciri["bahasa_provokatif"]["bukti"] == ["Warga resah karena kabar air keran tercemar"]


def test_ciri_regex_pola_lemah_dibuang_bila_llm_berhasil_tetapi_tidak_menandai(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, "Segera cek tagihan listrik bulan ini di aplikasi resmi PLN Mobile ya")
    llm_palsu.hasil = hasil_llm("")
    assert kirim(klien).json()["ciri"] == []


def test_ciri_regex_pola_lemah_dipakai_sedang_bila_llm_gagal(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, "Segera cek tagihan listrik bulan ini di aplikasi resmi PLN Mobile ya")
    llm_palsu.hasil = None
    isi = kirim(klien).json()
    # satu ciri sedang saja tidak menaikkan tingkat dan tidak ditampilkan (Sesi 5.5)
    assert isi["ciri"] == [] and isi["tingkat"] == "tidak_ditemukan"
    assert isi["pemeriksaan_terbatas"] == ["ai"]


def test_dua_ciri_regex_lemah_sedang_bila_llm_gagal_menaikkan_ke_hati_hati(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, "Segera cek kabar viral tentang tagihan listrik bulan ini di aplikasi resmi PLN Mobile ya")
    llm_palsu.hasil = None
    isi = kirim(klien).json()
    assert sorted((c["id"], c["keyakinan"]) for c in isi["ciri"]) == [("desakan_waktu", "sedang"), ("judul_clickbait", "sedang")]
    assert isi["tingkat"] == "hati_hati"


def test_ciri_llm_dan_regex_sama_keyakinan_tinggi_dengan_bukti_regex_kuat_dulu(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, "Segera klik tautan ini. Lakukan sebelum dinonaktifkan oleh pihak bank. Segera ya.")
    llm_palsu.hasil = hasil_llm("", KandidatLLM("desakan_waktu", ["Segera ya"]))
    c = {x["id"]: x for x in kirim(klien).json()["ciri"]}["desakan_waktu"]
    assert c["keyakinan"] == "tinggi"
    assert "sebelum dinonaktifkan" in c["bukti"][0].lower()  # pola kuat regex mendahului kutipan LLM dan pola lemah


# --- pemeriksaan_terbatas ---


def test_llm_gagal_ditandai_ai_tanpa_nama_penyedia(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = None
    isi = kirim(klien).json()
    assert isi["pemeriksaan_terbatas"] == ["ai"] and "groq" not in str(isi).lower()


def test_llm_dimatikan_lewat_konfigurasi_ditandai_ai(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    monkeypatch.setattr(pengaturan, "llm_aktif", False)
    isi = kirim(klien).json()
    assert isi["pemeriksaan_terbatas"] == ["ai"] and llm_palsu.teks_dikirim == []


def test_cek_fakta_dan_ai_keduanya_terbatas_urutan_tetap(monkeypatch, klien, llm_palsu, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = None
    pencarian_palsu.status = "nonaktif"
    assert kirim(klien).json()["pemeriksaan_terbatas"] == ["cek_fakta", "ai"]


def test_llm_melempar_galat_tidak_menggagalkan_analisis(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = RuntimeError("RAHASIA")
    r = kirim(klien)
    assert r.status_code == 200 and r.json()["pemeriksaan_terbatas"] == ["ai"]


def test_mode_paksa_tidak_memanggil_llm_dan_terbatas_kosong(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_HOAKS)
    llm_palsu.hasil = None
    isi = kirim(klien, params={"paksa": "kuat"}).json()
    assert isi["pemeriksaan_terbatas"] == [] and llm_palsu.teks_dikirim == []


# --- privasi ---

TEKS_DATA_PRIBADI = (
    "Hubungi Bu Rina di 0812-3456-7890 atau rina.sari@mail.co.id, akun @rina_sari. "
    "Transfer biaya admin Rp 250.000 pada 12 Oktober 2026 pukul 08.30 untuk 700 korban."
)


def test_llm_menerima_teks_tersamar_sedangkan_pencarian_dan_respons_memakai_teks_asli(
    monkeypatch, klien, llm_palsu, pencarian_palsu
):
    teks_layar(monkeypatch, TEKS_DATA_PRIBADI)
    isi = kirim(klien).json()
    terkirim = llm_palsu.teks_dikirim[0]
    for rahasia in ("0812-3456-7890", "rina.sari@mail.co.id", "@rina_sari"):
        assert rahasia not in terkirim
    assert "[NOMOR]" in terkirim and "[EMAIL]" in terkirim and "[AKUN]" in terkirim
    for biasa in ("Bu Rina", "Rp 250.000", "12 Oktober 2026", "08.30", "700 korban"):
        assert biasa in terkirim  # nama orang dan angka biasa tidak disamarkan
    assert pencarian_palsu.kueri == [TEKS_DATA_PRIBADI] and isi["teks_terbaca"] == TEKS_DATA_PRIBADI


def test_bukti_dari_kutipan_llm_bertoken_dikembalikan_sebagai_potongan_teks_asli(monkeypatch, klien, llm_palsu):
    teks_layar(monkeypatch, TEKS_DATA_PRIBADI)
    llm_palsu.hasil = hasil_llm("", KandidatLLM("bahasa_provokatif", ["Hubungi Bu Rina di [NOMOR] atau [EMAIL]"]))
    c = {x["id"]: x for x in kirim(klien).json()["ciri"]}["bahasa_provokatif"]
    assert c["bukti"] == ["Hubungi Bu Rina di 0812-3456-7890 atau rina.sari@mail.co.id"]
    assert "[" not in c["bukti"][0]


def test_log_tidak_memuat_teks_klaim_atau_data_pribadi(monkeypatch, klien, llm_palsu, caplog):
    caplog.set_level(logging.DEBUG)
    teks_layar(monkeypatch, TEKS_DATA_PRIBADI)
    llm_palsu.hasil = hasil_llm("Hubungi Bu Rina untuk transfer biaya admin")
    kirim(klien)
    log = "\n".join(r.getMessage() for r in caplog.records)
    for rahasia in ("0812-3456-7890", "rina.sari", "@rina_sari", "Bu Rina", "biaya admin", "Hubungi"):
        assert rahasia not in log
    assert "penyedia=groq" in log


# --- tautan terpecah ---


def test_tautan_terpecah_digabung_di_teks_terbaca_dan_bukti_tetap_potongan_teks(monkeypatch, klien):
    teks = "Peringatan akun Anda akan diblokir.\nTekan tautan: https://\nkonfirmasipenonaktifan2025.weeblysite.com/\nUntuk verifikasi."
    teks_layar(monkeypatch, teks)
    isi = kirim(klien).json()
    assert "https://konfirmasipenonaktifan2025.weeblysite.com/" in isi["teks_terbaca"]
    tautan = {c["id"]: c for c in isi["ciri"]}["link_mencurigakan"]
    assert any("https://konfirmasipenonaktifan2025.weeblysite.com/" in b for b in tautan["bukti"])
    for bukti in tautan["bukti"]:
        assert bukti in " ".join(isi["teks_terbaca"].split())
    assert "pembuat situs gratis" in tautan["penjelasan"]  # varian penjelasan situs gratis


def test_https_diikuti_kalimat_biasa_tidak_digabung(monkeypatch, klien):
    teks_layar(monkeypatch, "Silakan buka tautan berikut: https://\nSilakan klik tombol di bawah ini untuk melanjutkan")
    assert "https://\nSilakan" in kirim(klien).json()["teks_terbaca"]


# --- klaim heuristik yang diperbaiki ---

GAMBAR_12 = "kebakaran hutan kalimantan\nmulai masuk negara brunei\ndan bakar rumah penduduk\nJabatan Bomba dan Penyelamat\nKementerian Hal Ehwal Dalam Negeri"
GAMBAR_14 = "MenKeu Fiktlwam Terlibat\nKorupsi 500 Triliun\nSenin, 14 Sep 2026 21:00 WIB\nBlm bekerja sdh terungkap\njg ke publik Hancurrr"
GAMBAR_16 = (
    "CUKUP VIRALKAN INI DAN DIKOPI KASIKAN KE\nRAKYAT PLOSOK PLOSOK DESA INSYA ALLAH\nPASTI TUMBANG DAN PASTI DIBENCI SAMA\n"
    "RAKYAT TERUTAMA RAKYAT KAUM PEDESAAN\nPERDALAMAN\nPDIP USUL KE PEMERINTAH AGAR\nPESANTREN DI TUTUP SELURUH INDONESIA\nAndebaNews"
)
GAMBAR_07 = (
    "Waspada Akun Facebook\nDiretas, Modus Pinjam\nUang Via Inbox\nLangkah yang harus dilakukan\njika akun diretas\n"
    "Aktifkan autentikasi\ndua faktor (2FA)\nhumaspolresmerangin\nfpolresmerangin\npolresmerangin6\nhumaspolresmerangin"
)


def test_gambar_12_judul_huruf_kecil_mengalahkan_daftar_nama_lembaga():
    assert klaim.klaim_heuristik(GAMBAR_12) == "kebakaran hutan kalimantan mulai masuk negara brunei dan bakar rumah penduduk"


def test_gambar_14_judul_terpecah_dua_baris_digabung_dan_mengalahkan_komentar():
    assert klaim.klaim_heuristik(GAMBAR_14) == "MenKeu Fiktlwam Terlibat Korupsi 500 Triliun"


def test_gambar_16_kalimat_ajakan_tidak_mendapat_bonus_dan_klaim_yang_diviralkan_menang():
    ajakan = CiriTerdeteksi("ajakan_menyebarkan", ["CUKUP VIRALKAN INI DAN DIKOPI KASIKAN KE RAKYAT"], "tinggi")
    assert klaim.bukti_untuk_klaim([ajakan]) == []
    hasil = klaim.klaim_heuristik(GAMBAR_16, klaim.bukti_untuk_klaim([ajakan]))
    assert "PDIP USUL KE PEMERINTAH AGAR PESANTREN DI TUTUP SELURUH INDONESIA" in hasil
    assert "VIRALKAN" not in hasil and "AndebaNews" not in hasil


def test_bonus_klaim_hanya_dari_ciri_yang_lolos_dan_ber_id_tertentu():
    ciri = [
        CiriTerdeteksi("desakan_waktu", ["sebelum dihapus"], "tinggi"),
        CiriTerdeteksi("judul_clickbait", ["terungkap"], "sedang"),
        CiriTerdeteksi("kapital_tanda_seru", ["HEBOH!!!"], "sedang"),
        CiriTerdeteksi("permintaan_data_rahasia", ["kirim kode OTP"], "tinggi"),
    ]
    assert klaim.bukti_untuk_klaim(ciri) == ["sebelum dihapus", "kirim kode OTP"]


def test_gambar_07_baris_akun_tidak_menjadi_klaim_dan_infografis_tanpa_pernyataan_kosong():
    assert klaim.klaim_heuristik(GAMBAR_07) == ""
    assert "humaspolresmerangin" not in " ".join(klaim.pisah_kalimat(GAMBAR_07))


def test_baris_akun_menjadi_pemisah_bukan_sambungan_kalimat():
    teks = "Kementerian Perhubungan resmi menaikkan tarif tol mulai 1 Januari 2027\nhumaspolresmerangin\nfpolresmerangin\npolresmerangin6"
    assert klaim.pisah_kalimat(teks) == ["Kementerian Perhubungan resmi menaikkan tarif tol mulai 1 Januari 2027"]


def test_obrolan_pendek_tanpa_pernyataan_tidak_menjadi_klaim():
    assert klaim.klaim_heuristik("oke siap kak\nnanti saya kabari ya\nterima kasih banyak") == ""


def test_satu_kata_sendiri_bukan_potongan_judul():
    teks = "PERDALAMAN\nPDIP USUL KE PEMERINTAH AGAR PESANTREN DI TUTUP SELURUH INDONESIA\nAndebaNews"
    assert klaim.pisah_kalimat(teks)[0].startswith("PERDALAMAN")  # tidak menyambung ke bawah
    assert not klaim.pisah_kalimat(teks)[1].endswith("AndebaNews")


def test_teks_tanpa_pernyataan_menghasilkan_string_kosong_dengan_ambang_baru():
    assert Pengaturan().klaim_skor_minimum == 3.0
    assert klaim.klaim_heuristik("Langkah yang harus dilakukan jika akun diretas") == ""


def test_ambang_klaim_dari_konfigurasi():
    teks = "Pemerintah kota mengumumkan perbaikan Jalan Merdeka pada 12 Oktober 2026."
    assert klaim.klaim_heuristik(teks)
    ketat = dataclasses.replace(Pengaturan(), klaim_skor_minimum=99)
    assert klaim.klaim_heuristik(teks, cfg=ketat) == ""


# --- Sesi 5.5: rantai klaim (LLM -> bukti pernah_dibantah -> heuristik -> kosong) dan diagnostik ---

import asyncio  # noqa: E402
import io as _io  # noqa: E402
import uuid  # noqa: E402
from datetime import date  # noqa: E402

from app.pipeline import orkestrator  # noqa: E402
from app.pipeline.tipe import Kandidat, Konteks  # noqa: E402

TEKS_KLAIM = (
    "Air keran di Jakarta mengandung zat berbahaya penyebab penyakit misterius.\n"
    "Pemerintah belum memberi keterangan resmi mengenai kabar tersebut hari ini."
)


def artikel(skor=0.91):
    return Kandidat(
        judul="[SALAH] Air keran Jakarta mengandung zat berbahaya", sumber="TurnBackHoax",
        url="https://turnbackhoax.id/articles/1-air-keran", skor=skor, label="salah", tanggal=date(2025, 11, 4),
        url_format_lama=False, narasi="Beredar pesan air keran Jakarta mengandung zat berbahaya.",
    )


def analisis_dengan_diagnostik(monkeypatch):
    gambar = _io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 10)).save(gambar, format="JPEG")

    async def tidak_putus():
        return False

    diag: dict = {}
    ctx = Konteks(id_permintaan=uuid.uuid4().hex, jeda_detik=(0.0, 0.0), klien_putus=tidak_putus, diagnostik=diag)
    hasil = asyncio.run(orkestrator.jalankan(gambar.getvalue(), ctx))
    return hasil, diag


def test_klaim_kosong_dari_llm_diisi_bukti_pernah_dibantah(monkeypatch, klien, llm_palsu, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_KLAIM)
    llm_palsu.hasil = hasil_llm("")
    pencarian_palsu.kandidat = [artikel()]
    isi = kirim(klien).json()
    assert isi["klaim_utama"] == "Air keran di Jakarta mengandung zat berbahaya"
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    assert diag["klaim_sumber"] == "bukti"


def test_klaim_llm_yang_sah_didahulukan_atas_bukti(monkeypatch, klien, llm_palsu, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_KLAIM)
    llm_palsu.hasil = hasil_llm("Air keran di Jakarta mengandung zat berbahaya")
    pencarian_palsu.kandidat = [artikel()]
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    assert hasil.klaim_utama == "Air keran di Jakarta mengandung zat berbahaya" and diag["klaim_sumber"] == "llm"


def test_klaim_llm_dengan_anda_ditolak_lalu_bukti_atau_heuristik(monkeypatch, klien, llm_palsu, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_KLAIM)
    llm_palsu.hasil = hasil_llm("Air keran Anda di Jakarta mengandung zat berbahaya")
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    assert "anda" not in (hasil.klaim_utama or "").lower() and diag["klaim_sumber"] == "heuristik"


def test_klaim_kosong_bila_tak_ada_sumber_klaim_yang_layak(monkeypatch, klien, llm_palsu, pencarian_palsu):
    teks_layar(monkeypatch, "OK saya tunggu, sudah lebih dari 2 menit ya kak sampai selesai prosesnya")
    llm_palsu.hasil = hasil_llm("")
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    assert hasil.klaim_utama is None and diag["klaim_sumber"] == "kosong"
    assert diag["klaim_gugur_percakapan"] == 1


def test_klaim_llm_ditolak_membuat_ambang_heuristik_lebih_tinggi(monkeypatch, klien, llm_palsu, pencarian_palsu):
    teks_layar(monkeypatch, TEKS_KLAIM)
    llm_palsu.hasil = hasil_llm("Pemerintah menutup seluruh sekolah di Jakarta")  # tidak setia pada teks
    monkeypatch.setattr(pengaturan, "klaim_skor_setelah_tolak", 99.0)
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    assert hasil.klaim_utama is None and diag["klaim_sumber"] == "kosong"
    monkeypatch.setattr(pengaturan, "klaim_skor_setelah_tolak", 4.0)
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    assert diag["klaim_sumber"] == "heuristik"


def test_diagnostik_mencatat_bukti_dan_ciri_yang_dibuang(monkeypatch, klien, llm_palsu, pencarian_palsu):
    teks_layar(monkeypatch, "Segera verifikasi Formulir Pemulihan akun. Peringatan! Kabar dari orang dalam, cek sekarang")
    llm_palsu.hasil = hasil_llm(
        "", KandidatLLM("kapital_tanda_seru", ["Segera verifikasi Formulir Pemulihan"]),
        KandidatLLM("sumber_tidak_jelas", ["Kabar dari orang dalam"]),
        KandidatLLM("bahasa_provokatif", ["verifikasi Formulir Pemulihan akun"]),
    )
    hasil, diag = analisis_dengan_diagnostik(monkeypatch)
    alasan = {(d["id"], d["alasan"]) for d in diag["ciri_dibuang"]}
    assert ("kapital_tanda_seru", "bukan_kapital_atau_seru") in alasan
    assert ("sumber_tidak_jelas", "hanya_dari_llm") in alasan
    assert ("desakan_waktu", "regex_lemah_tanpa_llm") in alasan
    # satu ciri sedang tunggal (bahasa_provokatif) tidak ditampilkan dan tercatat sebagai dibuang
    assert hasil.tingkat.value == "tidak_ditemukan" and hasil.ciri == []
    assert ("bahasa_provokatif", "sedang_tunggal_tanpa_indikasi") in alasan
