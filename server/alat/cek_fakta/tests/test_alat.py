"""Uji fungsi murni alat cek fakta: tanpa jaringan dan tanpa model."""

import sys
from pathlib import Path

import json

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bangun  # noqa: E402
import kumpul_tbh  # noqa: E402
import skema  # noqa: E402


@pytest.mark.parametrize("asli,harapan", [
    ("SALAH", "salah"), ("FALSE", "salah"), ("HOAX/FITNAH", "salah"), ("DISINFORMASI+HASUT", "salah"),
    ("HOAX + HASUT", "salah"), ("PENIPUAN", "penipuan"), ("BELUM TERBUKTI", "belum_terbukti"), ("BENAR", "benar"),
    ("KLARIFIKASI", "klarifikasi"), ("CLARIFICATION", "klarifikasi"), ("BERITA", "bukan_cek_fakta"),
    ("BERITA, EDUKASI", "bukan_cek_fakta"), ("TOP 5", "bukan_cek_fakta"), ("CEK FAKTA", "bukan_cek_fakta"),
    ("PARODI", "satir"), ("SATIR", "satir"), ("SATIRE", "satir"), ("KOMEDI", "satir"), ("Parodi", "satir"),
    ("", "lainnya"), ("ISU", "lainnya"), ("FAKTA", "benar"), ("FRAMING", "lainnya"), ("CekFakta", "lainnya"),
])
def test_normalisasi_label(asli, harapan):
    assert skema.normalisasi_label(asli) == harapan


def test_label_dari_judul():
    assert skema.label_asli_dari_judul("[SALAH] Judul") == "SALAH"
    assert skema.label_asli_dari_judul("(ISU) : Judul") == "ISU"
    assert skema.label_asli_dari_judul("Judul biasa") == ""
    assert skema.judul_bersih("[SALAH] Judul biasa") == "Judul biasa"


def test_slug_sama_untuk_format_lama_dan_baru():
    lama = "https://turnbackhoax.id/2025/11/07/salah-luhut-ingatkan-prabowo/"
    baru = "https://turnbackhoax.id/articles/36100-salah-luhut-ingatkan-prabowo"
    assert skema.kunci_slug(lama) == skema.kunci_slug(baru) == "salah-luhut-ingatkan-prabowo"
    assert skema.url_format_lama(lama) and not skema.url_format_lama(baru)


def test_tanggal_iso():
    assert skema.tanggal_iso("Oktober 30, 2024") == "2024-10-30"
    assert skema.tanggal_iso("08/10/2026") == "2026-10-08"
    assert skema.tanggal_iso("2026-10-06 23:06:00") == "2026-10-06"
    assert skema.tanggal_iso("bukan tanggal") is None and skema.tanggal_iso(None) is None


def test_narasi_tbh_berbagai_penanda():
    a = "Faktanya salah.====[KATEGORI] Konten====[NARASI]: “Pesan berantai ini”====[PENJELASAN]Isi panjang"
    assert skema.narasi_dari_teks_tbh(a) == "Pesan berantai ini"
    b = "Faktanya.= = = = =KATEGORI: X= = = = =SUMBER: Y= = = = =NARASI:“Ini narasinya”= = = = =PENJELASAN:Isi"
    assert skema.narasi_dari_teks_tbh(b) == "Ini narasinya"
    assert skema.narasi_dari_teks_tbh("Tanpa penanda sama sekali") == ""
    assert skema.narasi_dari_teks_tbh("===NARASI : (narasi tidak ditampilkan)===PENJELASAN : x") == ""


def test_narasi_komdigi_dan_pemotongan():
    t = "Penjelasan : Beredar unggahan berisi klaim A. Faktanya, klaim itu tidak benar. Link Counter : https://x.id/a"
    assert skema.narasi_dari_komdigi(t) == "Beredar unggahan berisi klaim A."
    panjang = skema.rapikan("kata " * 400)
    assert len(panjang) <= skema.MAKS_NARASI + 1 and panjang.endswith("…")


def test_teks_passage():
    assert skema.teks_passage({"judul": "[SALAH] Air keran", "narasi": "klaim X"}) == "passage: Air keran. klaim X"
    assert skema.teks_passage({"judul": "[SALAH] Air keran", "narasi": ""}) == "passage: Air keran"


HTML_ARTIKEL = """<main><article><div><h1>[PENIPUAN] Tautan Lowongan X</h1>
<p><a href="/articles?category=Politik">Politik</a> <time datetime="2026-09-22">22/09/2026</time></p></div>
<section><section><strong>Narasi</strong><div><p>Beredar unggahan <a href="#">[arsip]</a> dengan narasi:</p>
<blockquote><span>“Klaim <b>asli</b> di sini”</span></blockquote></div></section>
<section><strong>Penjelasan</strong><div><p>RAHASIA penjelasan panjang</p></div></section>
<section><strong>Hasil Periksa fakta</strong><div><p><strong>Salah</strong> Sumber: x</p></div></section></section></article></main>"""


def test_baca_artikel():
    d = kumpul_tbh.baca_artikel(HTML_ARTIKEL, "https://turnbackhoax.id/articles/123-penipuan-tautan-lowongan-x")
    assert d["judul"] == "[PENIPUAN] Tautan Lowongan X" and d["tanggal"] == "2026-09-22"
    assert d["label_asli"] == "PENIPUAN" and d["hasil_periksa"] == "Salah" and d["kategori"] == "Politik"
    assert d["id_situs"] == 123
    assert "Klaim asli di sini" in d["narasi"] and "RAHASIA" not in d["narasi"] and "arsip" not in d["narasi"]


def test_baca_daftar():
    html = ('<div class="news-card-h-alt"><a href="https://turnbackhoax.id/articles/5-salah-a"><img alt="[SALAH] A"></a>'
            '<a href="https://turnbackhoax.id/articles/5-salah-a">x</a><span class="t">08/10/2026</span></div>')
    assert kumpul_tbh.baca_daftar(html) == [
        {"url": "https://turnbackhoax.id/articles/5-salah-a", "tanggal": "2026-10-08", "judul": "[SALAH] A"}]


def _r(asal, judul, url, tanggal="2025-01-01", narasi="", **lain):
    return {"asal_data": asal, "judul": judul, "url": url, "tanggal": tanggal, "narasi": narasi, **lain}


def test_gabung_utamakan_situs_dan_isi_narasi():
    kaggle = _r("kaggle_aginanjar", "[SALAH] Klaim air keran berbahaya", "https://turnbackhoax.id/2025/01/01/salah-klaim-air-keran-berbahaya/", narasi="narasi kaggle")
    situs = _r("situs_turnbackhoax", "[SALAH] Klaim air keran berbahaya", "https://turnbackhoax.id/articles/9-salah-klaim-air-keran-berbahaya", id_situs=9)
    hasil, stat = bangun.gabung([kaggle, situs])
    assert len(hasil) == 1 and stat["duplikat_slug"] == 1
    a = hasil[0]
    assert a["asal_data"] == "situs_turnbackhoax" and a["id"] == "tbh-9" and a["narasi"] == "narasi kaggle"
    assert a["asal_lain"] == ["kaggle_aginanjar"] and not a["url_format_lama"]


def test_gabung_komdigi_dengan_link_counter_dan_judul():
    tbh = _r("kaggle_aginanjar", "[SALAH] Menkeu diganti Luhut", "https://turnbackhoax.id/2025/11/07/salah-menkeu-diganti-luhut/")
    kom = _r("kaggle_ireddragonicy", "[HOAKS] Menkeu diganti Luhut", "https://www.komdigi.go.id/berita/x",
             label_asli="HOAKS", ref_url=["https://turnbackhoax.id/2025/11/07/salah-menkeu-diganti-luhut/"])
    lain = _r("kaggle_ireddragonicy", "[HOAKS] Kasus beda total isinya", "https://www.komdigi.go.id/berita/y", label_asli="HOAKS")
    jauh = _r("kaggle_aginanjar", "[SALAH] Kasus beda total isinya", "https://turnbackhoax.id/2020/01/01/salah-kasus-lain/", tanggal="2020-01-01")
    hasil, stat = bangun.gabung([tbh, kom, lain, jauh])
    assert len(hasil) == 3 and stat["duplikat_ref_url"] == 1  # judul sama tetapi beda tahun: bukan duplikat


def test_gabung_membuang_non_cek_fakta_dan_tanpa_url():
    hasil, stat = bangun.gabung([
        _r("kaggle_aginanjar", "[BERITA] Pengumuman", "https://turnbackhoax.id/2020/01/01/berita-pengumuman/"),
        _r("kaggle_aginanjar", "[SALAH] Tanpa alamat", ""),
        _r("kaggle_aginanjar", "[EDUKASI] Tips", "https://turnbackhoax.id/2020/01/02/edukasi-tips/"),
        _r("kaggle_aginanjar", "[SALAH] Ini masuk", "https://turnbackhoax.id/2020/01/03/salah-ini-masuk/", tanggal=None),
    ])
    assert [a["judul"] for a in hasil] == ["[SALAH] Ini masuk"] and hasil[0]["tanggal"] is None
    assert stat["dibuang_bukan_cek_fakta"] == 2 and stat["dibuang_tanpa_url"] == 1


def test_indeks_cari_vektor_urutan_dan_batas_k():
    from embed import Indeks

    ind = Indeks.__new__(Indeks)
    v = np.array([[1, 0], [0, 1], [0.6, 0.8]], dtype=np.float32)
    ind.vektor = v
    hasil = ind.cari_vektor(np.array([[0.6, 0.8]], dtype=np.float32), k=5)[0]
    assert [i for i, _ in hasil] == [2, 1, 0] and hasil[0][1] == pytest.approx(1.0)


@pytest.mark.parametrize("judul,label_asli,bersih", [
    ("HOAX: MyRoti Adalah Kloningnya Sari Roti", "HOAX", "MyRoti Adalah Kloningnya Sari Roti"),
    ("HASUT : Malaysia Ada, Mana Indonesia?", "HASUT", "Malaysia Ada, Mana Indonesia?"),
    ("[SALAH Anies Baswedan Diseret KPK", "SALAH", "Anies Baswedan Diseret KPK"),
    ("SALAH] Surat Penerimaan Pegawai BNN", "SALAH", "Surat Penerimaan Pegawai BNN"),
    ("(FAKTA) Kebakaran Hutan di Kalimantan Tengah", "FAKTA", "Kebakaran Hutan di Kalimantan Tengah"),
    ("(ISU) : STARBUCKS Mendukung", "ISU", "STARBUCKS Mendukung"),
    ("[CekFakta] “Luhut Diusir”", "CekFakta", "“Luhut Diusir”"),
    ("“Kementerian Bantah Arahkan Motor”", "", "“Kementerian Bantah Arahkan Motor”"),
    ("Berita: Sesuatu terjadi", "", "Berita: Sesuatu terjadi"),
])
def test_awalan_label_tanpa_kurung_dan_kurung_hilang(judul, label_asli, bersih):
    assert skema.label_asli_dari_judul(judul) == label_asli
    assert skema.judul_bersih(judul) == bersih


def test_pemetaan_label_judul_lengkap():
    peta = {"HOAX: A": "salah", "HASUT: A": "salah", "[SALAH A": "salah", "(FAKTA) A": "benar",
            "(ISU) A": "lainnya", "(FRAMING) A": "lainnya", "[CekFakta] A": "lainnya", "“A”": "lainnya"}
    for judul, harapan in peta.items():
        assert skema.normalisasi_label(skema.label_asli_dari_judul(judul)) == harapan, judul


def test_baca_jsonl_melewati_baris_terpotong(tmp_path):
    berkas = tmp_path / "x.jsonl"
    berkas.write_text('{"a": 1}\n{"a": 2}\n{"a": 3, "b": "terpot', encoding="utf-8")
    assert skema.baca_jsonl(berkas) == [{"a": 1}, {"a": 2}]


# ---------- pengaman pengumpul: berkas kunci dan penulisan tahan galat ----------

def test_tulis_aman_mencoba_lagi_saat_permissionerror(tmp_path, monkeypatch):
    import os

    asli, hitung = os.replace, {"n": 0}

    def replace_sering_gagal(a, b):
        hitung["n"] += 1
        if hitung["n"] <= 2:
            raise PermissionError(5, "Access is denied")
        return asli(a, b)

    monkeypatch.setattr(kumpul_tbh.os, "replace", replace_sering_gagal)
    monkeypatch.setattr(kumpul_tbh.time, "sleep", lambda s: None)
    tujuan = tmp_path / "status.json"
    assert kumpul_tbh.tulis_aman(tujuan, "isi") is True
    assert tujuan.read_text(encoding="utf-8") == "isi" and hitung["n"] == 3
    assert not list(tmp_path.glob("*.tmp"))


def test_tulis_aman_tidak_melempar_kalau_tetap_gagal(tmp_path, monkeypatch, capsys):
    def selalu_gagal(a, b):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(kumpul_tbh.os, "replace", selalu_gagal)
    monkeypatch.setattr(kumpul_tbh.time, "sleep", lambda s: None)
    assert kumpul_tbh.tulis_aman(tmp_path / "status.json", "isi") is False
    assert "PERINGATAN" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.tmp"))


def test_penyimpan_status_gagal_tidak_menghentikan(tmp_path, monkeypatch):
    monkeypatch.setattr(kumpul_tbh.os, "replace", lambda a, b: (_ for _ in ()).throw(OSError("rusak")))
    monkeypatch.setattr(kumpul_tbh.time, "sleep", lambda s: None)
    simpan = kumpul_tbh.Penyimpan(tmp_path)
    simpan.tulis_status({"x": 1})
    simpan.simpan_ckpt({"halaman_berikut": 3})
    simpan.tutup()


def test_kunci_ditolak_kalau_ada_pengumpul_lain(tmp_path, monkeypatch):
    monkeypatch.setattr(kumpul_tbh, "proses_pengumpul_lain", lambda: [4242])
    with pytest.raises(kumpul_tbh.Ditolak, match="4242"):
        kumpul_tbh.Kunci(tmp_path).ambil()
    assert not (tmp_path / "tbh.lock").exists()


def test_kunci_kedua_ditolak_dan_dilepas_setelah_selesai(tmp_path, monkeypatch):
    import os

    monkeypatch.setattr(kumpul_tbh, "proses_pengumpul_lain", lambda: [])
    pertama = kumpul_tbh.Kunci(tmp_path)
    pertama.ambil()
    assert (tmp_path / "tbh.lock").read_text() == str(os.getpid())
    # kunci dipegang proses yang (menurut pemeriksaan) masih berjalan sebagai pengumpul
    monkeypatch.setattr(kumpul_tbh, "pengumpul_aktif", lambda pid: True)
    tulis_pid_lain = tmp_path / "tbh.lock"
    tulis_pid_lain.write_text("999999")
    with pytest.raises(kumpul_tbh.Ditolak, match="999999"):
        kumpul_tbh.Kunci(tmp_path).ambil()
    tulis_pid_lain.write_text(str(os.getpid()))
    pertama.lepas()
    assert not (tmp_path / "tbh.lock").exists()


def test_kunci_basi_diambil_alih(tmp_path, monkeypatch, capsys):
    import os

    monkeypatch.setattr(kumpul_tbh, "proses_pengumpul_lain", lambda: [])
    (tmp_path / "tbh.lock").write_text("2147483000")  # PID yang tidak ada
    kunci = kumpul_tbh.Kunci(tmp_path)
    kunci.ambil()
    assert "kunci basi" in capsys.readouterr().out
    assert (tmp_path / "tbh.lock").read_text() == str(os.getpid())
    kunci.lepas()
    assert not (tmp_path / "tbh.lock").exists()


def test_kunci_rusak_dianggap_basi(tmp_path, monkeypatch):
    monkeypatch.setattr(kumpul_tbh, "proses_pengumpul_lain", lambda: [])
    (tmp_path / "tbh.lock").write_text("bukan angka")
    kumpul_tbh.Kunci(tmp_path).ambil()


def test_deteksi_proses_pengumpul_lain_pakai_nama_skrip():
    import subprocess

    # proses tiruan yang baris perintahnya memuat kumpul_tbh.py, seperti pengumpul sungguhan
    anak = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "kumpul_tbh.py"])
    try:
        import time as waktu

        waktu.sleep(0.5)
        assert anak.pid in kumpul_tbh.proses_pengumpul_lain()
        assert kumpul_tbh.pengumpul_aktif(anak.pid)
    finally:
        anak.kill()
        anak.wait()
    assert not kumpul_tbh.pengumpul_aktif(anak.pid)
    import os
    assert os.getpid() not in kumpul_tbh.proses_pengumpul_lain()


def test_jalankan_menolak_saat_pengumpul_lain_berjalan(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kumpul_tbh, "proses_pengumpul_lain", lambda: [111, 222])
    kode = kumpul_tbh.jalankan("lengkap", "2024-11-01", tmp_path, 1, None)
    assert kode == kumpul_tbh.KODE_KELUAR_DITOLAK
    assert "DITOLAK" in capsys.readouterr().err
    assert not (tmp_path / "tbh_artikel.jsonl").exists()  # tidak menyentuh data sama sekali


def test_bersihkan_pilih_salinan_terbaik_dan_buang_rusak():
    import bersihkan

    def b(**k):
        d = {"url": "u", "judul": "j", "tanggal": "2025-01-01", "narasi": "", "label_asli": "", "diambil": "t1"} | k
        return json.dumps(d).encode()

    baris = [b(url="a", galat="tak_terbaca"), b(url="b", narasi="pendek"), b(url="a", narasi="utuh", label_asli="SALAH"),
             b'-10-08T20:12:53"}', b(url="b", narasi="lebih panjang dari yang pertama"), b"", b'{"url": "c"}']
    terpilih, stat = bersihkan.bersihkan_baris(baris)
    assert [d["url"] for d in terpilih] == ["a", "b"]  # urutan kemunculan pertama
    assert terpilih[0]["narasi"] == "utuh" and "galat" not in terpilih[0]
    assert terpilih[1]["narasi"] == "lebih panjang dari yang pertama"
    assert stat["rusak"] == 1 and stat["judul_hilang"] == 1 and stat["duplikat_dibuang"] == 2 and stat["unik"] == 2 and stat["galat_tersisa"] == 0


def test_penyimpan_galat_dicoba_lagi(tmp_path):
    (tmp_path / "tbh_artikel.jsonl").write_text(
        '{"url": "u1", "tanggal": "2025-01-01"}\n{"url": "u2", "tanggal": "2025-01-02", "galat": "tak_terbaca"}\n',
        encoding="utf-8")
    simpan = kumpul_tbh.Penyimpan(tmp_path)
    simpan.tutup()
    assert simpan.sudah == {"u1"}


def test_label_satir_dari_judul_dan_tidak_menaikkan_tingkat():
    for judul in ("[PARODI] Prabowo : Wanita Hamil Wajib Bayar Pajak", "[SATIRE] Judul", "[KOMEDI] Judul"):
        assert skema.normalisasi_label(skema.label_asli_dari_judul(judul)) == "satir"
    assert "satir" in skema.LABEL


def test_tanggal_tidak_sah_menjadi_none():
    assert skema.tanggal_iso("0000-00-00") is None
    assert skema.tanggal_iso("2025-02-30") is None
    assert skema.tanggal_iso("2025-07-17") == "2025-07-17"
    assert skema.tanggal_iso("Februari 30, 2025") is None


def test_bersihkan_hanya_buang_tanpa_url_judul_duplikat_rusak():
    import bersihkan

    def b(**k):
        d = {"url": "u", "judul": "j", "tanggal": "2025-01-01", "narasi": "n", "diambil": "t"} | k
        return json.dumps(d).encode()

    tanpa_narasi_tanggal = json.dumps({"url": "d", "judul": "j"}).encode()  # kunci narasi dan tanggal tidak ada
    baris = [b(url="a", narasi=""), b(url="b", tanggal="0000-00-00"), b(url="c", tanggal=None), tanpa_narasi_tanggal,
             b(url=""), b(judul=" "), b(url="a"), b"{rusak"]
    terpilih, stat = bersihkan.bersihkan_baris(baris)
    assert [d["url"] for d in terpilih] == ["a", "b", "c", "d"]
    assert {d["url"]: d["tanggal"] for d in terpilih} == {"a": "2025-01-01", "b": None, "c": None, "d": None}
    assert stat["url_hilang"] == 1 and stat["judul_hilang"] == 1 and stat["rusak"] == 1 and stat["duplikat_dibuang"] == 1
    assert stat["tanggal_diperbaiki_ke_null"] == 1 and stat["tanggal_kosong"] == 3


def test_sidik_teks_mengabaikan_label_tapi_peka_pada_teks_dan_urutan():
    import embed

    a = [{"id": "1", "judul": "[SALAH] Air keras", "narasi": "isi satu", "label": "lainnya", "url": "u1"},
         {"id": "2", "judul": "Judul dua", "narasi": "", "label": "salah", "url": "u2"}]
    dasar = embed.sidik_teks(a)
    b = [dict(x, label="salah", url="lain", sumber="X", asal_lain=["y"]) for x in a]
    assert embed.sidik_teks(b) == dasar
    assert embed.sidik_teks(a[::-1]) != dasar
    assert embed.sidik_teks([dict(a[0], narasi="isi lain"), a[1]]) != dasar
    assert embed.sidik_teks([dict(a[0], id="9"), a[1]]) != dasar
    assert embed.sidik_teks([a[0]]) != dasar


def test_periksa_cocok_menerima_label_berubah_dan_menolak_teks_berubah():
    import embed

    a = [{"id": "1", "judul": "Judul", "narasi": "isi", "label": "lainnya"}]
    meta = {"jumlah": 1, "teks_sha1": embed.sidik_teks(a)}
    embed.periksa_cocok(meta, [dict(a[0], label="salah")], "base", "fp32")  # tidak melempar
    with pytest.raises(SystemExit):
        embed.periksa_cocok(meta, [dict(a[0], narasi="berubah")], "base", "fp32")
    with pytest.raises(SystemExit):
        embed.periksa_cocok({"jumlah": 1, "artikel_sha1": "lama"}, a, "base", "fp32")  # metadata lama tanpa teks_sha1


@pytest.mark.parametrize("asli,harapan", [
    ("DISINFOMASI", "salah"), ("DISINFORMAS", "salah"), ("DISINFORMATION", "salah"), ("SCAM", "penipuan"),
    ("Konten yang dimanipulasi", "salah"), ("INFORMASI", "lainnya"), ("BERITA", "bukan_cek_fakta"),
])
def test_ejaan_miring(asli, harapan):
    assert skema.normalisasi_label(asli) == harapan


@pytest.mark.parametrize("asli,hasil,harapan", [
    ("", "Salah", "salah"), ("", "False", "salah"), ("ISU", "Salah", "salah"), ("isu", "salah", "salah"),
    ("", "Klarifikasi", "klarifikasi"), ("", "Clarification", "klarifikasi"), ("", "Benar", "klarifikasi"),
    ("", "True", "klarifikasi"), ("", "Berita", "lainnya"), ("", "Edukasi", "lainnya"), ("", "Dalam Proses", "lainnya"),
    ("", "", "lainnya"), ("INFORMASI", "Salah", "lainnya"), ("FRAMING", "Salah", "lainnya"),
    ("BENAR", "Salah", "benar"), ("SALAH", "Benar", "salah"), ("BERITA", "Salah", "bukan_cek_fakta"),
])
def test_label_dengan_hasil_periksa(asli, hasil, harapan):
    assert skema.label_dengan_hasil_periksa(asli, hasil) == harapan


def test_gabung_memakai_hasil_periksa_situs_dan_tidak_mengubah_teks_embed():
    r = {"judul": "Kabar tanpa label", "url": "https://turnbackhoax.id/articles/1-kabar", "tanggal": "2020-01-01",
         "narasi": "isi", "asal_data": "situs_turnbackhoax", "hasil_periksa": "Salah", "label_asli": ""}
    artikel, _ = bangun.gabung([r])
    assert artikel[0]["label"] == "salah" and artikel[0]["label_asli"] == ""
    sebelum = skema.teks_passage(r)
    assert skema.teks_passage(artikel[0]) == sebelum
