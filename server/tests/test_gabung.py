import dataclasses

from app.konfigurasi import Pengaturan
from app.pipeline.ciri import gabung_ciri
from app.pipeline.tipe import CiriRegex, KandidatLLM

TEKS = (
    "VIRAL!! Air keran di Jakarta mengandung zat berbahaya.\n"
    "Sudah 12 orang dirawat! SEBARKAN ke keluarga   sebelum dihapus!!!\n"
    "Info dari grup sebelah, cek bit.ly/air-keran"
)


def regex(id_ciri, kekuatan, *bukti):
    return CiriRegex(id_ciri, kekuatan, list(bukti))


def llm(id_ciri, *kutipan):
    return KandidatLLM(id_ciri, list(kutipan))


def peta(hasil):
    return {c.id: c for c in hasil}


# ----- LLM gagal (None) -----

def test_llm_gagal_pola_kuat_tinggi_dan_pola_lemah_sedang():
    hasil = peta(gabung_ciri(
        [regex("ajakan_menyebarkan", "kuat", "SEBARKAN ke keluarga"), regex("sumber_tidak_jelas", "lemah", "Info dari grup")],
        None, TEKS,
    ))
    assert hasil["ajakan_menyebarkan"].keyakinan == "tinggi"
    assert hasil["sumber_tidak_jelas"].keyakinan == "sedang"
    assert hasil["ajakan_menyebarkan"].bukti == ["SEBARKAN ke keluarga"]


def test_llm_gagal_tanpa_regex_hasilnya_kosong():
    assert gabung_ciri([], None, TEKS) == []


# ----- LLM berhasil -----

def test_llm_dan_regex_sama_sama_menemukan_tinggi_walau_regex_lemah():
    hasil = peta(gabung_ciri([regex("sumber_tidak_jelas", "lemah", "Info dari grup sebelah")],
                             [llm("sumber_tidak_jelas", "info dari grup sebelah")], TEKS))
    assert hasil["sumber_tidak_jelas"].keyakinan == "tinggi"


def test_regex_kuat_tetap_tinggi_walau_llm_tidak_menandai():
    hasil = peta(gabung_ciri([regex("ajakan_menyebarkan", "kuat", "SEBARKAN ke keluarga")], [], TEKS))
    assert hasil["ajakan_menyebarkan"].keyakinan == "tinggi"


def test_hanya_llm_dengan_kutipan_terverifikasi_sedang():
    hasil = peta(gabung_ciri([], [llm("desakan_waktu", "keluarga sebelum dihapus")], TEKS))
    assert hasil["desakan_waktu"].keyakinan == "sedang"
    assert hasil["desakan_waktu"].bukti == ["keluarga sebelum dihapus"]


def test_regex_lemah_dibuang_kalau_llm_berhasil_tetapi_tidak_menandainya():
    assert gabung_ciri([regex("sumber_tidak_jelas", "lemah", "Info dari grup")], [], TEKS) == []
    # juga ketika LLM menandai ciri lain
    hasil = gabung_ciri([regex("sumber_tidak_jelas", "lemah", "Info dari grup")], [llm("desakan_waktu", "keluarga sebelum dihapus")], TEKS)
    assert [c.id for c in hasil] == ["desakan_waktu"]


# ----- verifikasi kutipan -----

def test_kutipan_tidak_ada_di_teks_dibuang_dan_ciri_dibuang_kalau_tidak_tersisa():
    hasil = gabung_ciri([], [llm("desakan_waktu", "segera sebelum terlambat"), llm("ajakan_menyebarkan", "")], TEKS)
    assert hasil == []


def test_hanya_kutipan_terverifikasi_yang_dipertahankan():
    hasil = peta(gabung_ciri([], [llm("desakan_waktu", "keluarga sebelum dihapus", "kalimat karangan model")], TEKS))
    assert hasil["desakan_waktu"].bukti == ["keluarga sebelum dihapus"]


def test_verifikasi_mengabaikan_huruf_besar_kecil_spasi_dan_pergantian_baris():
    hasil = peta(gabung_ciri([], [llm("ajakan_menyebarkan", "sebarkan   KE keluarga\nsebelum dihapus")], TEKS))
    # bukti diambil dari teks asli (huruf asli, spasi dirapikan), bukan dari ketikan model
    assert hasil["ajakan_menyebarkan"].bukti == ["SEBARKAN ke keluarga sebelum dihapus"]


def test_kutipan_yang_menyambung_baris_dengan_teks_dummy_diverifikasi():
    teks = "Tekan tautan:\nhttps://abc.example.com/x"
    hasil = peta(gabung_ciri([], [llm("link_mencurigakan", "Tekan tautan: https://abc.example.com/x")], teks))
    assert hasil["link_mencurigakan"].bukti == ["Tekan tautan: https://abc.example.com/x"]


def test_kutipan_bukan_string_diabaikan_tanpa_galat():
    assert gabung_ciri([], [llm("desakan_waktu", None, 5, "keluarga sebelum dihapus")], TEKS)[0].bukti == ["keluarga sebelum dihapus"]  # type: ignore[list-item]


def test_id_tidak_dikenal_dibuang_termasuk_pernah_dibantah():
    hasil = gabung_ciri([], [llm("ciri_karangan", "sebelum dihapus"), llm("pernah_dibantah", "Air keran di Jakarta")], TEKS)
    assert hasil == []


def test_id_llm_yang_sama_dua_kali_digabung():
    hasil = gabung_ciri([], [llm("desakan_waktu", "keluarga sebelum dihapus"), llm("desakan_waktu", "keluarga sebelum dihapus", "Sudah 12 orang dirawat")], TEKS)
    assert len(hasil) == 1 and hasil[0].bukti == ["keluarga sebelum dihapus", "Sudah 12 orang dirawat"]


# ----- bukti gabungan -----

def test_bukti_yang_sama_dari_kedua_sumber_didahulukan_dan_duplikat_dibuang():
    regex_ajakan = regex("ajakan_menyebarkan", "kuat", "Kalimat lain yang hanya ditemukan regex", "SEBARKAN ke keluarga sebelum dihapus!!!")
    teks = "Kalimat lain yang hanya ditemukan regex. " + TEKS
    hasil = peta(gabung_ciri([regex_ajakan], [llm("ajakan_menyebarkan", "viral!! air keran", "sebarkan ke keluarga")], teks))
    bukti = hasil["ajakan_menyebarkan"].bukti
    assert bukti[0] == "SEBARKAN ke keluarga"  # yang sama dari dua sumber, versi lebih ringkas
    assert len(bukti) == len(set(bukti)) <= 3
    assert not any("sebarkan ke keluarga sebelum dihapus" in b.lower() for b in bukti[1:])  # duplikat tidak diulang


def test_bukti_maksimal_tiga_dan_mengikuti_konfigurasi():
    teks = "satu dua tiga empat lima enam tujuh delapan"
    kutipan = ["satu dua tiga", "dua tiga empat", "tiga empat lima", "empat lima enam", "lima enam tujuh"]
    hasil = gabung_ciri([], [llm("desakan_waktu", *kutipan)], teks)
    assert len(hasil[0].bukti) == 3
    cfg = dataclasses.replace(Pengaturan(), ciri_bukti_maks=2)
    assert len(gabung_ciri([], [llm("desakan_waktu", *kutipan)], teks, cfg)[0].bukti) == 2


def test_bukti_panjang_dipotong_di_batas_kata():
    teks = "kata " * 80
    hasil = gabung_ciri([], [llm("desakan_waktu", teks.strip())], teks)
    bukti = hasil[0].bukti[0]
    assert "…" not in bukti and len(bukti) <= Pengaturan().ciri_bukti_maks_karakter
    assert all(k == "kata" for k in bukti.split())


def test_urutan_keyakinan_tinggi_dulu_lalu_urutan_id():
    hasil = gabung_ciri(
        [regex("link_mencurigakan", "kuat", "bit.ly/air-keran")],
        [llm("desakan_waktu", "keluarga sebelum dihapus"), llm("ajakan_menyebarkan", "SEBARKAN ke keluarga sebelum")],
        TEKS,
    )
    from app.pipeline.ciri import ID_BISA_DITANDAI

    assert [(c.id, c.keyakinan) for c in hasil] == [("link_mencurigakan", "tinggi")] + [
        (i, "sedang") for i in ID_BISA_DITANDAI if i in ("ajakan_menyebarkan", "desakan_waktu")
    ]


def test_hasil_tidak_mengubah_masukan():
    r = [regex("ajakan_menyebarkan", "kuat", "SEBARKAN ke keluarga")]
    k = [llm("desakan_waktu", "keluarga sebelum dihapus")]
    gabung_ciri(r, k, TEKS)
    assert r[0].bukti == ["SEBARKAN ke keluarga"] and k[0].kutipan == ["keluarga sebelum dihapus"]


# ----- pengaman struktural dan sumber_tidak_jelas (Sesi 5.5) -----

def catat(regex_, kandidat, teks=TEKS):
    catatan: list = []
    return gabung_ciri(regex_, kandidat, teks, catatan=catatan), catatan


def test_bukti_tautan_tunggal_dari_llm_diterima_walau_satu_kata():
    hasil, catatan = catat([], [llm("link_mencurigakan", "bit.ly/air-keran")])
    assert [(c.id, c.keyakinan, c.bukti) for c in hasil] == [("link_mencurigakan", "sedang", ["bit.ly/air-keran"])]
    assert catatan == []


def test_bukti_link_yang_bukan_tautan_dibuang_dengan_catatan():
    teks = "Lihat vocazine. di sini untuk info lengkap tentang hal itu"
    hasil, catatan = catat([], [llm("link_mencurigakan", "vocazine.")], teks)
    assert hasil == [] and catatan == [{"id": "link_mencurigakan", "bukti": "vocazine.", "alasan": "bukan_bentuk_tautan"}]


def test_domain_dengan_tld_dan_url_berskema_diterima():
    teks = "Buka https://konfirmasi.weeblysite.com/ atau situs promo-gratis.xyz sekarang"
    hasil, _ = catat([], [llm("link_mencurigakan", "https://konfirmasi.weeblysite.com/", "promo-gratis.xyz")], teks)
    assert hasil[0].bukti == ["https://konfirmasi.weeblysite.com/", "promo-gratis.xyz"]


def test_bukti_kapital_harus_didominasi_kapital_atau_tanda_seru():
    teks = "AKAN Segera Dinonaktifkan SECARA PERMANEN. Segera verifikasi Formulir Pemulihan. Cek sekarang juga!!"
    hasil, catatan = catat([], [llm(
        "kapital_tanda_seru", "AKAN Segera Dinonaktifkan SECARA PERMANEN", "Segera verifikasi Formulir Pemulihan",
        "Cek sekarang juga!!",
    )], teks)
    assert hasil[0].bukti == ["AKAN Segera Dinonaktifkan SECARA PERMANEN", "Cek sekarang juga!!"]
    assert catatan == [{"id": "kapital_tanda_seru", "bukti": "Segera verifikasi Formulir Pemulihan", "alasan": "bukan_kapital_atau_seru"}]


def test_ciri_kapital_hilang_bila_semua_buktinya_ditolak():
    teks = "Segera verifikasi Formulir Pemulihan akun anda hari ini"
    hasil, catatan = catat([], [llm("kapital_tanda_seru", "Segera verifikasi Formulir Pemulihan")], teks)
    assert hasil == [] and len(catatan) == 1


def test_bukti_llm_saja_minimal_tiga_kata_tetapi_tidak_bila_regex_juga_menemukan():
    teks = "Peringatan! Segera hubungi kami sekarang juga. OKNUM POLISI? Bukan"
    hasil, catatan = catat([], [llm("desakan_waktu", "Peringatan!"), llm("bahasa_provokatif", "OKNUM POLISI?")], teks)
    assert hasil == [] and {c["alasan"] for c in catatan} == {"terlalu_pendek"}
    hasil2, _ = catat([regex("desakan_waktu", "lemah", "Segera hubungi")], [llm("desakan_waktu", "Segera hubungi")], teks)
    assert hasil2[0].keyakinan == "tinggi"  # LLM dan regex sama-sama menemukan


def test_sumber_tidak_jelas_hanya_dari_llm_dibuang():
    hasil, catatan = catat([], [llm("sumber_tidak_jelas", "Info dari grup sebelah")])
    assert hasil == []
    assert catatan == [{"id": "sumber_tidak_jelas", "bukti": "Info dari grup sebelah", "alasan": "hanya_dari_llm"}]


def test_sumber_tidak_jelas_regex_lemah_ditandai_llm_tinggi_dengan_bukti_regex_saja():
    r = [regex("sumber_tidak_jelas", "lemah", "Info dari grup sebelah")]
    hasil, catatan = catat(r, [llm("sumber_tidak_jelas", "Info dari grup sebelah", "Sudah 12 orang dirawat")])
    assert [(c.keyakinan, c.bukti) for c in hasil] == [("tinggi", ["Info dari grup sebelah"])]
    assert [c["alasan"] for c in catatan] == ["hanya_dari_llm", "hanya_dari_llm"]


def test_regex_lemah_tanpa_persetujuan_llm_dicatat_sebagai_dibuang():
    hasil, catatan = catat([regex("sumber_tidak_jelas", "lemah", "Info dari grup sebelah")], [])
    assert hasil == [] and catatan[0]["alasan"] == "regex_lemah_tanpa_llm"
