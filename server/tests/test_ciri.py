import dataclasses

import pytest

from app.konfigurasi import Pengaturan
from app.pipeline import ciri
from app.skema import ID_CIRI_TERKUNCI


def hasil(teks: str, cfg=None) -> dict[str, ciri.CiriRegex]:
    return {c.id: c for c in ciri.deteksi_regex(teks, cfg)}


def kekuatan(teks: str, id_ciri: str):
    c = hasil(teks).get(id_ciri)
    return c.kekuatan if c else None


def test_id_yang_bisa_ditandai_adalah_tujuh_id_terkunci_tanpa_pernah_dibantah():
    assert ciri.ID_BISA_DITANDAI == tuple(i for i in ID_CIRI_TERKUNCI if i != "pernah_dibantah")
    assert len(ciri.ID_BISA_DITANDAI) == 7


def test_pernah_dibantah_tidak_pernah_muncul_dari_regex_dan_teks_kosong_tidak_menghasilkan_apa_pun():
    teks = "SEBARKAN ke semua grup sebelum dihapus!!! bit.ly/abc katanya heboh bantai kafir"
    assert "pernah_dibantah" not in hasil(teks)
    assert ciri.deteksi_regex("") == []


# ----- ajakan_menyebarkan -----

@pytest.mark.parametrize("teks", [
    "SEBARKAN ke keluarga", "tolong viralkan", "Teruskan ke grup keluarga", "bagikan ke semua teman",
    "sebarkan   ke    semua", "sebarkan\nke keluarga", "share sebanyak-banyaknya", "Bagikan pesan ini",
    "bantu share ya", "CUKUP VIRALKANINI DAN DIKOPI", "kirim pesan ini ke 10 grup", "CUKUP VIRALKAN INI",
])
def test_ajakan_kuat(teks):
    assert kekuatan(teks, "ajakan_menyebarkan") == "kuat"


@pytest.mark.parametrize("teks", ["Bagikan", "mau share?", "forward dulu"])
def test_ajakan_lemah(teks):
    assert kekuatan(teks, "ajakan_menyebarkan") == "lemah"


@pytest.mark.parametrize("teks", [
    "Bagikan ke Facebook", "Bagikan: Facebook Twitter WhatsApp", "Share ke WhatsApp", "Teruskan via Telegram",
    "Bagikan  ke  salin tautan", "bagikan ke X", "Share on Pinterest", "bagikan ke LINE",
])
def test_menu_berbagi_situs_bukan_ajakan_baik_kuat_maupun_lemah(teks):
    assert "ajakan_menyebarkan" not in hasil(teks)


def test_menu_berbagi_tidak_menutupi_ajakan_sungguhan_di_dekatnya():
    assert kekuatan("Bagikan ke Facebook. Tolong sebarkan ke semua teman", "ajakan_menyebarkan") == "kuat"


# ----- desakan_waktu -----

@pytest.mark.parametrize("teks", [
    "SEBARKAN sebelum dihapus!!!", "sebelum di blokir", "Hari ini terakhir", "kesempatan terakhir", "Akun Anda AKAN Segera Dinonaktifkan",
    "segera daftar sebelum kehabisan",
])
def test_desakan_kuat(teks):
    assert kekuatan(teks, "desakan_waktu") == "kuat"


@pytest.mark.parametrize("teks", ["Segera hubungi kami", "mulai besok berlaku", "kirim sekarang juga", "Dalam 24 jam"])
def test_desakan_lemah(teks):
    assert kekuatan(teks, "desakan_waktu") == "lemah"


def test_desakan_negatif():
    assert "desakan_waktu" not in hasil("Rapat dimulai pukul 10 di balai kota. Terima kasih.")


# ----- kapital_tanda_seru -----

def test_kapital_tanda_seru_kuat_dari_tiga_tanda_seru_beruntun():
    assert kekuatan("Awas!!!", "kapital_tanda_seru") == "kuat"
    assert kekuatan("Awas! ! !", "kapital_tanda_seru") == "kuat"


def test_kapital_tanda_seru_kuat_dari_dua_kalimat_kapital_bertanda_seru():
    assert kekuatan("AWAS PENIPUAN BESAR! HATI-HATI SEKARANG JUGA!", "kapital_tanda_seru") == "kuat"


@pytest.mark.parametrize("teks", [
    "Hebat!!",
    "BERITA TERBARU HARI INI TENTANG HARGA BERAS NAIK DI SELURUH PASAR",
    "AWAS PENIPUAN BESAR! hati-hati ya",
])
def test_kapital_tanda_seru_lemah(teks):
    assert kekuatan(teks, "kapital_tanda_seru") == "lemah"


@pytest.mark.parametrize("teks", ["Pemerintah mengumumkan perbaikan jalan.", "Halo! Apa kabar?", "PT ABC dan CV XYZ"])
def test_kapital_tanda_seru_negatif(teks):
    assert "kapital_tanda_seru" not in hasil(teks)


def test_ambang_kapital_mengikuti_konfigurasi():
    teks = "BERITA TERBARU HARI INI TENTANG HARGA BERAS NAIK DI SELURUH PASAR"
    assert kekuatan(teks, "kapital_tanda_seru") == "lemah"
    cfg = dataclasses.replace(Pengaturan(), ciri_kapital_rasio=1.0)
    assert "kapital_tanda_seru" not in hasil(teks, cfg)


# ----- link_mencurigakan -----

@pytest.mark.parametrize("teks", [
    "Cek di sini bit.ly/info-tilang-baru", "https://s.id/abc", "chat.whatsapp.com/XyZ123", "promo.xyz/klaim",
    "Tekan tautan: https://\nkonfirmasipenonaktifan2025.weeblysite.com/", "TINYURL.COM/abc",
])
def test_link_kuat(teks):
    assert kekuatan(teks, "link_mencurigakan") == "kuat"


def test_link_umum_yang_tidak_dikecualikan_hanya_lemah():
    assert kekuatan("Buka https://contoh-toko.com/promo", "link_mencurigakan") == "lemah"
    assert kekuatan("Hubungi wa.me/6281234", "link_mencurigakan") is None  # tanpa https:// atau www.


@pytest.mark.parametrize("teks", [
    "https://www.kompas.com/berita/1", "https://dinkes.go.id/info", "www.kampus.ac.id", "https://turnbackhoax.id/articles/1",
    "Surel ke admin@kantor.com saja", "tanggal 1.2.3 dan s.id tanpa garis miring",
])
def test_tautan_situs_dikecualikan_tidak_ditandai(teks):
    assert "link_mencurigakan" not in hasil(teks)


def test_bukti_tautan_memuat_tautannya_tanpa_spasi_sisipan():
    bukti = hasil("Tekan tautan: https://\nkonfirmasipenonaktifan2025.weeblysite.com/ lalu isi data")["link_mencurigakan"].bukti
    assert any("https://konfirmasipenonaktifan2025.weeblysite.com/" in b for b in bukti)


# ----- sumber_tidak_jelas, judul_clickbait, bahasa_provokatif -----

@pytest.mark.parametrize("teks", [
    "katanya sih begitu", "Konon sudah beredar", "Info dari grup sebelah", "dapet info dari teman", "copas dari grup",
    "Forwarded many times", "Diteruskan", "Sumber: grup WA",
])
def test_sumber_tidak_jelas_hanya_punya_pola_lemah(teks):
    assert kekuatan(teks, "sumber_tidak_jelas") == "lemah"


def test_viral_hanya_untuk_judul_clickbait_bukan_sumber_tidak_jelas():
    h = hasil("Video ini viral di mana-mana")
    assert "judul_clickbait" in h and "sumber_tidak_jelas" not in h


@pytest.mark.parametrize("teks", [
    "Ternyata ini penyebabnya", "WAJIB BACA sampai habis", "kamu tidak akan percaya", "bikin kaget semua orang", "Heboh!",
])
def test_clickbait_hanya_lemah(teks):
    assert kekuatan(teks, "judul_clickbait") == "lemah"


@pytest.mark.parametrize("teks", ["bantai semua kafir", "Ganyang antek asing", "habisi kaum komunis", "basmi etnis tertentu"])
def test_provokatif_kuat_hanya_untuk_ajakan_kekerasan_ke_kelompok(teks):
    assert kekuatan(teks, "bahasa_provokatif") == "kuat"


@pytest.mark.parametrize("teks", ["dasar kafir", "antek", "pengkhianat bangsa", "hancurkan", "bantai", "mengerikan sekali", "Warga panik"])
def test_provokatif_kata_tunggal_hanya_lemah(teks):
    assert kekuatan(teks, "bahasa_provokatif") == "lemah"


def test_provokatif_negatif_dan_kata_kerja_kekerasan_tanpa_kelompok_tidak_kuat():
    assert "bahasa_provokatif" not in hasil("Pemerintah menyiapkan bantuan untuk korban banjir.")
    assert kekuatan("Polisi habisi sisa barang bukti di gudang", "bahasa_provokatif") is None
    assert kekuatan("kebakaran bakar rumah penduduk", "bahasa_provokatif") is None


# ----- bukti -----

def test_bukti_maksimal_tiga_dan_tidak_tumpang_tindih():
    teks = " ".join(f"Kalimat {i} sebarkan ke semua teman sekarang. " + "isi biasa " * 12 for i in range(6))
    c = hasil(teks)["ajakan_menyebarkan"]
    assert len(c.bukti) == 3 and len(set(c.bukti)) == 3


def test_bukti_pola_kuat_didahulukan_dari_lemah():
    teks = "Bagikan dulu. " + "isi biasa " * 20 + "Tolong sebarkan ke keluarga."
    assert "sebarkan" in hasil(teks)["ajakan_menyebarkan"].bukti[0]


def test_panjang_bukti_dibatasi_dan_dipotong_di_batas_kata():
    teks = "Mohon segera " + "kata " * 5 + "sebarkan ke semua teman sekarang juga " + "kata " * 40
    cfg = dataclasses.replace(Pengaturan(), ciri_bukti_maks_karakter=50)
    for b in hasil(teks, cfg)["ajakan_menyebarkan"].bukti:
        isi = b.rstrip("…")
        assert len(isi) <= 50
        assert isi in teks.replace("  ", " ")
        assert not isi.startswith(" ") and not isi.endswith(" ")
    # tidak memotong di tengah kata: setiap kata dalam bukti utuh
    kata_teks = set(teks.split())
    assert all(k in kata_teks for k in hasil(teks, cfg)["ajakan_menyebarkan"].bukti[0].rstrip("…").split())


def test_bukti_adalah_potongan_teks_asli_dengan_spasi_dirapikan():
    teks = "Halo semua,   TOLONG   sebarkan\nke    keluarga   ya"
    bukti = hasil(teks)["ajakan_menyebarkan"].bukti[0]
    assert "  " not in bukti and "\n" not in bukti
    assert "sebarkan ke keluarga" in bukti


def test_jumlah_bukti_mengikuti_konfigurasi():
    teks = ". ".join("sebarkan ke semua teman " + "isi biasa " * 12 for _ in range(5))
    cfg = dataclasses.replace(Pengaturan(), ciri_bukti_maks=1)
    assert len(hasil(teks, cfg)["ajakan_menyebarkan"].bukti) == 1


def test_urutan_hasil_mengikuti_id_terkunci():
    teks = "bit.ly/abc sebarkan ke semua katanya heboh sebelum dihapus!!!"
    urutan = [c.id for c in ciri.deteksi_regex(teks)]
    assert urutan == sorted(urutan, key=ID_CIRI_TERKUNCI.index)


def test_deteksi_ciri_dummy_masih_ada_untuk_analisis():
    assert callable(ciri.deteksi_ciri)
