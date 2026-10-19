"""Alat evaluasi data berlabel (alat/uji_analisis/evaluasi_berlabel.py) dan hook leave-one-out di Pencarian.cari.
Tanpa jaringan, tanpa e5 asli, tanpa membaca server/data_lokal."""

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path

import pytest
from PIL import Image
from test_cocok import pencarian_siap

from app import konfigurasi
from app.pipeline import cocok, llm, orkestrator
from app.pipeline.tipe import Kandidat, Konteks

jalur_alat = Path(__file__).resolve().parents[1] / "alat" / "uji_analisis" / "evaluasi_berlabel.py"
spec = importlib.util.spec_from_file_location("evaluasi_berlabel_alat", jalur_alat)
alat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alat)

pytestmark = pytest.mark.anyio

KOLOM = "id,berkas,set,label_harapan,label_boleh,kategori,sintetis,id_artikel_sumber,sumber,catatan"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def profil_alat(monkeypatch):
    """Alat menerapkan --profil (bawaan lama) ke Pengaturan global di main(); tes memanggil fungsinya langsung."""
    for k, v in konfigurasi.nilai_profil("lama").items():
        monkeypatch.setattr(konfigurasi.pengaturan, k, v)


def kand(skor=0.9, label="salah", judul="Judul artikel uji") -> Kandidat:
    return Kandidat(judul, "Sumber", "https://example.test/x", skor, label, None, False, "", 1.0)


def buat_gambar(folder: Path, nama: str, warna: int) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 300), (warna, 40, 40)).save(folder / nama, format="PNG")


@pytest.fixture
def evaluasi(tmp_path, monkeypatch, pencarian_palsu, pembaca_palsu):
    """Folder evaluasi sementara: dev d1 (positif_db), d2 (berita), uji u1, u2; versi database dibuat tetap."""
    akar = tmp_path / "evaluasi"
    monkeypatch.setattr(alat, "J", alat.jalur_dari(akar))
    monkeypatch.setattr(alat, "FOLDER_HASIL", tmp_path / "hasil")
    monkeypatch.setattr(alat.PencarianBerCache, "versi_db", lambda self: "db-uji")
    asli_cari = pencarian_palsu.cari
    monkeypatch.setattr(pencarian_palsu, "cari", lambda teks, k, kecualikan_id=None: asli_cari(teks, k))
    baris = [
        ("d1", "positif_db", "kuat", "", "tidak", "a1"),
        ("d2", "berita", "tidak_ditemukan", "", "ya", ""),
        ("u1", "penipuan", "kuat", "hati_hati", "tidak", ""),
        ("u2", "edukasi", "tidak_ditemukan", "", "tidak", ""),
    ]
    teks = [KOLOM]
    for i, (id_, kat, harapan, boleh, sint, sumber) in enumerate(baris):
        buat_gambar(akar / "gambar", f"{id_}.png", 20 * (i + 1))
        teks.append(f"{id_},{id_}.png,{'dev' if id_[0] == 'd' else 'uji'},{harapan},{boleh},{kat},{sint},{sumber},x,catatan")
    akar.mkdir(parents=True, exist_ok=True)
    (akar / "metadata.csv").write_text("\n".join(teks) + "\n", encoding="utf-8")
    return akar


def tulis_beku(akar: Path) -> None:
    baris = [
        f"{hashlib.sha256((akar / 'gambar' / f'{i}.png').read_bytes()).hexdigest()}  gambar/{i}.png" for i in ("u1", "u2")
    ]
    (akar / "uji_beku.sha256").write_text("\n".join(baris) + "\n", encoding="utf-8")


def argumen(*a):
    return alat.buat_parser().parse_args(["--log", ""] + list(a))


def png_uji() -> bytes:
    import io

    b = io.BytesIO()
    Image.new("RGB", (200, 300), (9, 9, 9)).save(b, format="PNG")
    return b.getvalue()


# --- hook leave-one-out ---


def test_hook_loo_bawaan_tidak_mengubah_pencarian(tmp_path):
    p, _ = pencarian_siap(tmp_path)
    q = "air keran Jakarta mengandung zat berbahaya"
    assert p.cari(q, 4) == p.cari(q, 4, None) == p.cari(q, 4, frozenset())
    assert p.cari(q, 4)[0].judul.startswith("[SALAH] Air keran")


def test_hook_loo_tidak_terhubung_ke_server():
    # cari_kecocokan (jalur server) tidak punya parameter itu, dan modul tidak membaca lingkungan untuknya.
    assert "kecualikan_id" not in inspect.signature(cocok.cari_kecocokan).parameters
    assert "environ" not in inspect.getsource(cocok.Pencarian.cari)


def test_hook_loo_mengeluarkan_artikel_yang_diminta(tmp_path):
    p, _ = pencarian_siap(tmp_path)
    q = "air keran Jakarta mengandung zat berbahaya"
    biasa = p.cari(q, 4)
    tanpa = p.cari(q, 4, kecualikan_id=frozenset({"a1"}))
    assert len(biasa) == 4 and len(tanpa) == 3  # artikel dikeluarkan, bukan diganti
    assert all(not k.judul.startswith("[SALAH] Air keran") for k in tanpa)
    assert [k.judul for k in tanpa] == [k.judul for k in biasa if not k.judul.startswith("[SALAH] Air keran")]


# --- ambang ---


def test_urai_ambang_alias_dan_penolakan():
    assert alat.urai_ambang("skor_kuat=0.9,relevansi=0.5,satir=mati") == {
        "ambang_cocok": 0.9, "relevansi_minimum": 0.5, "satir_hati_hati": False,
    }
    assert alat.urai_ambang(None) == {}
    for buruk in ("tidak_ada=1", "skor_kuat", "skor_kuat=abc", "top_k=50", "llm_aktif=0"):
        with pytest.raises(alat.GalatAlat):
            alat.urai_ambang(buruk)


def test_urai_sapu_grid():
    grid = alat.urai_sapu("skor_kuat=0.86:0.90:0.02,relevansi=0.3/0.4")
    assert grid == {"ambang_cocok": [0.86, 0.88, 0.9], "relevansi_minimum": [0.3, 0.4]}
    assert len(alat.kombinasi(grid)) == 6
    with pytest.raises(alat.GalatAlat):
        alat.urai_sapu("skor_kuat=0.1:0.9:0.001")


async def test_ambang_bawaan_sama_dengan_hasil_lama_dan_penimpaan_berlaku(evaluasi, pencarian_palsu):
    pencarian_palsu.kandidat = [kand(0.90)]
    dasar = alat.baca_metadata()[0]
    ctx = Konteks("x", (0.0, 0.0), alat.tidak_putus, diagnostik={})
    langsung = await orkestrator.jalankan(png_uji(), ctx)
    # gambar dev d1 berbeda isinya, tetapi pembaca dan pencarian palsu membuat hasilnya sama dengan langsung
    komp = alat.buat_komponen(ocr=True, cari=True)
    hasil = await alat.nilai_baris(komp, [dasar], {}, "biasa")
    assert hasil["biasa"]["d1"]["hasil"] == langsung.tingkat.value == "kuat"
    eksplisit = {"ambang_cocok": 0.88, "ambang_mirip": 0.85, "relevansi_minimum": 0.40, "selisih_konflik": 0.02}
    assert (await alat.nilai_baris(komp, [dasar], eksplisit, "biasa"))["biasa"]["d1"]["hasil"] == "kuat"
    ketat = await alat.nilai_baris(komp, [dasar], {"ambang_cocok": 0.95}, "biasa")
    assert ketat["biasa"]["d1"]["hasil"] == "hati_hati"
    # setelah blok, pengaturan global kembali
    assert alat.konfigurasi.pengaturan.ambang_cocok == 0.88


# --- cache ---


async def test_cache_ocr_dan_pencarian_tidak_diulang(evaluasi, pencarian_palsu, pembaca_palsu):
    pencarian_palsu.kandidat = [kand(0.9)]
    b = alat.baca_metadata()[0]
    komp = alat.buat_komponen(ocr=True, cari=True)
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, b, "biasa")
        await alat.jalankan_gambar(komp, b, "biasa")
    assert pembaca_palsu.dipanggil == 1 and len(pencarian_palsu.kueri) == 1
    assert komp.pembaca.baru == 1 and komp.pencarian.baru == 1
    # proses baru yang hanya boleh membaca cache tetap berhasil dan tidak memanggil OCR atau pencarian
    baca_saja = alat.buat_komponen()
    hasil = await alat.nilai_baris(baca_saja, [b], {}, "biasa")
    assert hasil["biasa"]["d1"]["hasil"] == "kuat"
    assert pembaca_palsu.dipanggil == 1 and len(pencarian_palsu.kueri) == 1
    teks_bersih = json.loads(next((evaluasi / "cache" / "ocr").glob("*.json")).read_text(encoding="utf-8"))
    assert "teks_bersih" in teks_bersih


async def test_cache_kosong_dilaporkan_bukan_dikarang(evaluasi):
    hasil = await alat.nilai_baris(alat.buat_komponen(), alat.baca_metadata()[:1], {}, "biasa")
    assert hasil["biasa"]["d1"]["hasil"] == "cache_kosong"


def fabrik_llm(monkeypatch, panggilan: list, status=200, header=None):
    """llm.analisis palsu yang melewati TransportGroq seperti klien asli (satu percobaan HTTP per panggilan)."""

    async def analisis(teks_samar, cfg=None, transport=None, jejak=None):
        panggilan.append(teks_samar)
        s, _, _ = transport(llm.GROQ, {}, "kunci", 1.0)
        if s != 200:
            if jejak is not None:
                jejak.append({"penyedia": "groq", "status": s, "ms": 1, "kode": None, "token": None, "tunggu": 1.0, "kuota": None})
            return None
        return llm.HasilLLM("klaim uji", [llm.KandidatLLM("ajakan_menyebarkan", ["sebarkan"])], "groq", 5)

    monkeypatch.setattr(llm, "analisis", analisis)

    def kirim(penyedia, badan, kunci, timeout):
        return status, '{"choices": []}', header or {"x-ratelimit-remaining-requests": "1000"}

    return kirim


async def test_panggilan_llm_tidak_diulang_bila_input_sama_dan_dipakai_bersama_mode(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    kirim = fabrik_llm(monkeypatch, panggilan)
    pencarian_palsu.kandidat = [kand(0.9)]
    pembaca_palsu.teks = "Hubungi 081234567890 segera sebarkan pesan ini ke semua grup keluarga"
    d1, d2 = alat.baca_metadata()[:2]
    komp = alat.buat_komponen(ocr=True, cari=True, nyata_llm=True, maks_panggilan=10, kirim=kirim, tidur=lambda s: None)
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
        await alat.jalankan_gambar(komp, d1, "loo")  # LLM tidak menerima hasil pencarian: cache dipakai bersama
        await alat.jalankan_gambar(komp, d1, "biasa")
    assert len(panggilan) == 1 and komp.llm.transport.sesi == 1 and alat.jumlah_panggilan_total() == 1
    assert "081234567890" not in panggilan[0] and "[NOMOR]" in panggilan[0]  # penyamaran orkestrator
    with alat.terpasang(komp):  # gambar lain, teks lain: panggilan baru
        pembaca_palsu.teks = "Info penting dari grup, segera teruskan kepada semua teman dan saudara"
        await alat.jalankan_gambar(komp, d2, "biasa")
    assert len(panggilan) == 2 and alat.jumlah_panggilan_total() == 2
    # prompt berubah: kunci cache berubah, panggilan ulang
    monkeypatch.setitem(llm.PENJELASAN_CIRI, "ajakan_menyebarkan", "definisi baru")
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
    assert len(panggilan) == 3
    # mode baca-saja memakai hasil LLM dari cache tanpa transport
    baca_saja = alat.buat_komponen(jalan=1)
    pembaca_palsu.teks = "Hubungi 081234567890 segera sebarkan pesan ini ke semua grup keluarga"
    hasil = await alat.nilai_baris(baca_saja, [d1], {}, "biasa")
    assert hasil["biasa"]["d1"]["llm_ada"] is True  # cache d1 ditulis ulang dengan kunci (prompt) yang baru


async def test_hasil_llm_dari_cache_dipakai_nilai(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    kirim = fabrik_llm(monkeypatch, panggilan)
    pencarian_palsu.kandidat = []
    pembaca_palsu.teks = "Sebarkan pesan ini ke semua grup keluarga kalian sekarang juga ya teman"
    d1 = alat.baca_metadata()[0]
    komp = alat.buat_komponen(ocr=True, cari=True, nyata_llm=True, maks_panggilan=5, kirim=kirim, tidur=lambda s: None)
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
    hasil = await alat.nilai_baris(alat.buat_komponen(), [d1], {}, "biasa")
    assert hasil["biasa"]["d1"]["llm_ada"] is True and len(panggilan) == 1
    tanpa = await alat.nilai_baris(alat.buat_komponen(tanpa_llm=True), [d1], {}, "biasa")
    assert tanpa["biasa"]["d1"]["llm_ada"] is False


# --- penghitung dan batas LLM ---


def test_penghitung_menghitung_setiap_percobaan_dan_batas_keras(evaluasi):
    tidur: list = []
    t = alat.TransportGroq(8.0, 3, tidur=tidur.append, jam=lambda: 100.0, kirim=lambda *a: (200, "{}", {}))
    for _ in range(3):
        t(llm.GROQ, {}, "k", 1.0)
    assert alat.jumlah_panggilan_total() == 3 and t.sesi == 3
    assert tidur == [8.0, 8.0]  # jeda minimal antar percobaan (waktu dibekukan: selalu 8 detik penuh)
    with pytest.raises(alat.BatasPanggilan):
        t(llm.GROQ, {}, "k", 1.0)
    assert alat.jumlah_panggilan_total() == 3
    with pytest.raises(alat.TransportDitolak):  # Gemini tidak pernah dipakai
        alat.TransportGroq(8.0, None, kirim=lambda *a: (200, "{}", {}))(llm.GEMINI, {}, "k", 1.0)
    assert alat.jumlah_panggilan_total() == 3


def test_penghitung_kumulatif_antar_sesi_dan_berkas_rusak_tidak_ditimpa(evaluasi):
    alat.tambah_penghitung()
    alat.tambah_penghitung(2)
    assert alat.jumlah_panggilan_total() == 3
    alat.J.penghitung.write_text("{rusak", encoding="utf-8")
    with pytest.raises(alat.GalatAlat):
        alat.tambah_penghitung()
    assert alat.J.penghitung.read_text(encoding="utf-8") == "{rusak"


async def test_berhenti_setelah_tiga_429_beruntun(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    kirim = fabrik_llm(monkeypatch, panggilan, status=429, header={"retry-after": "1"})
    d1 = alat.baca_metadata()[0]
    tidur: list = []
    komp = alat.buat_komponen(ocr=True, cari=True, nyata_llm=True, maks_panggilan=50, kirim=kirim, tidur=tidur.append)
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
    assert komp.llm.berhenti == "429_beruntun" and alat.jumlah_panggilan_total() == 3
    assert not list((evaluasi / "cache").glob("llm/*.json"))  # kegagalan tidak disimpan sebagai hasil


async def test_berhenti_bila_kuota_harian_rendah_dan_bila_batas_panggilan(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    kirim = fabrik_llm(monkeypatch, panggilan, header={"x-ratelimit-remaining-requests": "5"})
    d1, d2 = alat.baca_metadata()[:2]
    komp = alat.buat_komponen(ocr=True, cari=True, nyata_llm=True, maks_panggilan=50, kirim=kirim, tidur=lambda s: None)
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
        pembaca_palsu.teks = "Teks lain yang cukup panjang untuk lolos ambang karakter bermakna ya"
        await alat.jalankan_gambar(komp, d2, "biasa")
    assert komp.llm.berhenti == "kuota_harian_rendah" and len(panggilan) == 1

    panggilan.clear()
    kirim2 = fabrik_llm(monkeypatch, panggilan)
    komp2 = alat.buat_komponen(ocr=True, cari=True, nyata_llm=True, maks_panggilan=0, kirim=kirim2, tidur=lambda s: None)
    with alat.terpasang(komp2):
        await alat.jalankan_gambar(komp2, d2, "biasa")
    assert komp2.llm.berhenti == "batas_panggilan" and panggilan == []


async def test_ulang_llm_menyimpan_jalan_terpisah(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    kirim = fabrik_llm(monkeypatch, panggilan)
    d1 = alat.baca_metadata()[0]
    komp = alat.buat_komponen(ocr=True, cari=True, nyata_llm=True, maks_panggilan=10, kirim=kirim, tidur=lambda s: None)
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
        await komp.llm.lengkapi_jalan(3)
        await komp.llm.lengkapi_jalan(3)  # sudah ada: tanpa panggilan baru
    assert len(panggilan) == 3
    e = json.loads(next((evaluasi / "cache" / "llm").glob("*.json")).read_text(encoding="utf-8"))
    assert sorted(e["jalan"]) == ["1", "2", "3"]


# --- mode loo dengan pencarian sungguhan (indeks kecil) ---


async def test_cache_pencarian_loo_terpisah_dan_peringkat_sumber(evaluasi, pembaca_palsu, monkeypatch, tmp_path):
    p, _ = pencarian_siap(tmp_path / "idx")
    monkeypatch.setattr(cocok, "pencarian", p)
    pembaca_palsu.teks = "Beredar pesan air keran Jakarta mengandung zat berbahaya penyebab penyakit"
    d1 = alat.baca_metadata()[0]
    assert d1.id_artikel_sumber == "a1"
    komp = alat.buat_komponen(ocr=True, cari=True)
    with alat.terpasang(komp):
        biasa = await alat.jalankan_gambar(komp, d1, "biasa")
        loo = await alat.jalankan_gambar(komp, d1, "loo")
    assert biasa["rank_sumber"] == 1 and biasa["id_top1"] == "a1"
    assert loo["id_top1"] != "a1" and loo["rank_sumber"] is None
    berkas = sorted(x.name for x in (evaluasi / "cache" / "cari").glob("*.json"))
    assert len(berkas) == 2 and any(n.endswith("__loo.json") for n in berkas)
    c = json.loads(next((evaluasi / "cache" / "cari").glob("*__loo.json")).read_text(encoding="utf-8"))
    assert c["kecualikan"] == ["a1"] and all(h["id"] != "a1" for h in c["hasil"])


# --- segel set uji ---


async def isi_cache(evaluasi, pencarian_palsu, pembaca_palsu):
    pencarian_palsu.kandidat = [kand(0.9)]
    a = argumen("kumpul", "--tanpa-llm")
    assert await alat.perintah_kumpul(a, alat.Pencatat(None, gema=False)) == 0


async def test_nilai_uji_hanya_sekali_dengan_final(evaluasi, pencarian_palsu, pembaca_palsu):
    await isi_cache(evaluasi, pencarian_palsu, pembaca_palsu)
    tulis_beku(evaluasi)
    pencatat = alat.Pencatat(None, gema=False)
    with pytest.raises(alat.GalatAlat, match="--final"):
        await alat.perintah_nilai(argumen("nilai", "--set", "uji"), pencatat)
    assert not alat.J.penanda_uji.exists()
    a = argumen("nilai", "--set", "uji", "--final", "--nama", "uji_final", "--ambang", "skor_kuat=0.89")
    assert await alat.perintah_nilai(a, pencatat) == 0
    penanda = json.loads(alat.J.penanda_uji.read_text(encoding="utf-8"))
    assert penanda["profil"] == {"ambang_cocok": 0.89} and "waktu" in penanda
    laporan = (alat.FOLDER_HASIL / "uji_final.md").read_text(encoding="utf-8")
    assert "Matriks tingkat" in laporan and "u2" in laporan and "catatan" not in laporan
    with pytest.raises(alat.GalatAlat, match="sudah dinilai"):
        await alat.perintah_nilai(a, pencatat)
    with pytest.raises(alat.GalatAlat):
        await alat.perintah_nilai(argumen("nilai", "--set", "uji", "--final", "--sapu", "skor_kuat=0.8/0.9", "--paksa"), pencatat)
    assert await alat.perintah_nilai(argumen("nilai", "--set", "uji", "--final", "--paksa", "--nama", "ulang"), pencatat) == 0


async def test_nilai_uji_ditolak_bila_set_uji_berubah(evaluasi, pencarian_palsu, pembaca_palsu):
    await isi_cache(evaluasi, pencarian_palsu, pembaca_palsu)
    tulis_beku(evaluasi)
    buat_gambar(evaluasi / "gambar", "u1.png", 250)  # gambar uji diganti setelah dibekukan
    with pytest.raises(alat.GalatAlat, match="berubah"):
        await alat.perintah_nilai(argumen("nilai", "--set", "uji", "--final"), alat.Pencatat(None, gema=False))
    assert not alat.J.penanda_uji.exists()
    with pytest.raises(alat.GalatAlat, match="berubah"):
        await alat.perintah_segel_awal(argumen("segel-awal"), alat.Pencatat(None, gema=False))


async def test_segel_awal_tanpa_ringkasan_dan_tidak_menimpa(evaluasi, pencarian_palsu, pembaca_palsu, capsys):
    await isi_cache(evaluasi, pencarian_palsu, pembaca_palsu)
    tulis_beku(evaluasi)
    pencatat = alat.Pencatat(None)
    assert await alat.perintah_segel_awal(argumen("segel-awal"), pencatat) == 0
    keluar = capsys.readouterr().out
    assert "kuat" not in keluar and "hati_hati" not in keluar
    isi = json.loads(alat.J.hasil_awal.read_text(encoding="utf-8"))
    assert set(isi["hasil"]["biasa"]) == {"u1", "u2"} and isi["hasil"]["biasa"]["u1"]["hasil"] == "kuat"
    with pytest.raises(alat.GalatAlat):
        await alat.perintah_segel_awal(argumen("segel-awal"), pencatat)
    assert await alat.perintah_segel_awal(argumen("segel-awal", "--paksa"), pencatat) == 0
    # penilaian uji final memuat perbedaan terhadap kode awal
    await alat.perintah_nilai(argumen("nilai", "--set", "uji", "--final", "--nama", "u", "--ambang", "skor_kuat=0.95"), pencatat)
    assert "Perbedaan terhadap tingkat kode awal" in (alat.FOLDER_HASIL / "u.md").read_text(encoding="utf-8")


async def test_nilai_dev_boleh_berulang_dan_tidak_menyentuh_uji(evaluasi, pencarian_palsu, pembaca_palsu):
    await isi_cache(evaluasi, pencarian_palsu, pembaca_palsu)
    pencatat = alat.Pencatat(None, gema=False)
    for nama in ("a", "b"):
        assert await alat.perintah_nilai(argumen("nilai", "--set", "dev", "--nama", nama, "--sapu", "skor_kuat=0.86/0.95"), pencatat) == 0
    laporan = (alat.FOLDER_HASIL / "a.md").read_text(encoding="utf-8")
    assert "Sapuan ambang" in laporan and "d1" in laporan and "u1" not in laporan
    assert not alat.J.penanda_uji.exists()


def test_beku_tidak_ada_atau_format_hash_tunggal(evaluasi):
    uji = [b for b in alat.baca_metadata() if b.set == "uji"]
    with pytest.raises(alat.GalatAlat, match="belum dibekukan"):
        alat.verifikasi_beku(uji)
    sha = sorted(hashlib.sha256((evaluasi / "gambar" / f"{i}.png").read_bytes()).hexdigest() for i in ("u1", "u2"))
    (evaluasi / "uji_beku.sha256").write_text(hashlib.sha256(("\n".join(sha) + "\n").encode()).hexdigest() + "\n", encoding="utf-8")
    alat.verifikasi_beku(uji)


def test_laporan_tanpa_teks_ocr_dan_nama(evaluasi):
    baris = alat.baca_metadata()[:2]
    hasil = {"biasa": {b.id: {"id": b.id, "hasil": "kuat", "varian": "", "ciri": [], "skor_top1": 0.9, "id_top1": "a1",
                              "rank_sumber": 1, "skor_sumber": 0.9, "llm_ada": True, "ms": 1} for b in baris}}
    teks = alat.laporan("x", "dev", {}, baris, hasil).read_text(encoding="utf-8")
    assert "d2" in teks and "kuat" in teks and "catatan" not in teks


# --- filter id, token, batas token harian, 429 harian (T4b) ---


def kirim_usage(total=1000, status=200, isi=None):
    def kirim(penyedia, badan, kunci, timeout):
        if isi is not None:
            return status, isi, {"x-ratelimit-remaining-requests": "1000"}
        body = json.dumps({"choices": [], "usage": {"prompt_tokens": total - 100, "completion_tokens": 100, "total_tokens": total}})
        return status, body, {"x-ratelimit-remaining-requests": "1000"}

    return kirim


def test_filter_id_dari_opsi_dan_berkas(evaluasi, tmp_path):
    berkas = tmp_path / "id.txt"
    berkas.write_text("# komentar\nd2\n\n d1 \n", encoding="utf-8")
    a = argumen("kumpul", "--id", "d1,u1", "--id-berkas", str(berkas))
    assert alat.kumpulkan_id(a) == ["d1", "u1", "d2"]
    semua = alat.baca_metadata()
    terpilih = alat.batasi_id(semua, alat.pilih_set(semua, "semua"), ["d2", "u1"], "semua")
    assert [b.id for b in terpilih] == ["d2", "u1"]  # urutan metadata
    with pytest.raises(alat.GalatAlat):
        alat.batasi_id(semua, alat.pilih_set(semua, "semua"), ["d1", "zzz"], "semua")
    with pytest.raises(alat.GalatAlat):  # id dev, tetapi --set uji
        alat.batasi_id(semua, alat.pilih_set(semua, "uji"), ["d1"], "uji")


def test_id_uji_ditolak_pada_set_dev(evaluasi):
    semua = alat.baca_metadata()
    with pytest.raises(alat.GalatAlat, match="uji"):
        alat.batasi_id(semua, alat.pilih_set(semua, "dev"), ["d1", "u1"], "dev")


async def test_kumpul_dengan_id_hanya_mengisi_gambar_itu(evaluasi, pencarian_palsu, pembaca_palsu):
    pencarian_palsu.kandidat = [kand(0.9)]
    pembaca_palsu.teks = "Beredar pesan berantai yang cukup panjang untuk dibaca oleh pembaca palsu"
    a = argumen("kumpul", "--tanpa-llm", "--set", "dev", "--id", "d2")
    assert await alat.perintah_kumpul(a, alat.Pencatat(None, gema=False)) == 0
    assert len(list((evaluasi / "cache" / "ocr").glob("*.json"))) == 1
    a = argumen("kumpul", "--tanpa-llm", "--set", "dev", "--id", "u1")
    with pytest.raises(alat.GalatAlat):
        await alat.perintah_kumpul(a, alat.Pencatat(None, gema=False))


async def test_token_diakumulasi_per_jalan_dan_per_hari(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    fabrik_llm(monkeypatch, panggilan)
    monkeypatch.setattr(alat, "hari_ini", lambda: "2026-10-17")
    pembaca_palsu.teks = "Sebarkan pesan ini ke semua grup keluarga kalian sekarang juga ya teman"
    d1 = alat.baca_metadata()[0]
    komp = alat.buat_komponen(ocr=True, cari=True, nyata_llm=True, maks_panggilan=10, kirim=kirim_usage(1000), tidur=lambda s: None)
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
        await komp.llm.lengkapi_jalan(2)
    e = json.loads(next((evaluasi / "cache" / "llm").glob("*.json")).read_text(encoding="utf-8"))
    assert e["jalan"]["1"]["usage"] == {"prompt": 900, "completion": 100, "total": 1000}
    assert e["jalan"]["2"]["usage"]["total"] == 1000
    hari = json.loads(alat.J.penghitung.read_text(encoding="utf-8"))["per_hari"]["2026-10-17"]
    assert hari["panggilan"] == 2 and hari["token"] == 2000 and hari["prompt"] == 1800 and hari["completion"] == 200
    assert komp.llm.transport.token_sesi == 2000 and alat.token_hari_ini() == 2000 and alat.rata_token_panggilan() == 1000
    monkeypatch.setattr(alat, "hari_ini", lambda: "2026-10-18")  # hari baru mulai dari nol
    assert alat.token_hari_ini() == 0


async def test_berhenti_oleh_maks_token_hari(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    fabrik_llm(monkeypatch, panggilan)
    d1, d2 = alat.baca_metadata()[:2]
    komp = alat.buat_komponen(
        ocr=True, cari=True, nyata_llm=True, maks_panggilan=10, kirim=kirim_usage(1000), tidur=lambda s: None,
        maks_token_hari=1500,
    )
    with alat.terpasang(komp):
        pembaca_palsu.teks = "Sebarkan pesan ini ke semua grup keluarga kalian sekarang juga ya teman"
        await alat.jalankan_gambar(komp, d1, "biasa")  # 0 + 1200 (perkiraan bawaan) <= 1500: jalan
        assert komp.llm.berhenti == ""
        pembaca_palsu.teks = "Teks lain yang cukup panjang untuk lolos ambang karakter bermakna ya"
        await alat.jalankan_gambar(komp, d2, "biasa")  # 1000 + rata-rata 1000 > 1500: berhenti
    assert komp.llm.berhenti == "maks_token_hari" and len(panggilan) == 1 and alat.jumlah_panggilan_total() == 1


async def test_429_harian_langsung_berhenti_tanpa_menunggu(evaluasi, pencarian_palsu, pembaca_palsu, monkeypatch):
    panggilan: list = []
    fabrik_llm(monkeypatch, panggilan)
    isi = '{"error": {"message": "Rate limit reached ... on tokens per day (TPD): Limit 100000, Used 99900"}}'
    tidur: list = []
    komp = alat.buat_komponen(
        ocr=True, cari=True, nyata_llm=True, maks_panggilan=50, kirim=kirim_usage(status=429, isi=isi), tidur=tidur.append,
    )
    d1 = alat.baca_metadata()[0]
    with alat.terpasang(komp):
        await alat.jalankan_gambar(komp, d1, "biasa")
    assert komp.llm.berhenti == "429_harian" and alat.jumlah_panggilan_total() == 1
    assert tidur == []  # tidak ada tunggu ulang
    assert not list((evaluasi / "cache").glob("llm/*.json"))


def test_ringkas_token_mencetak_tanpa_memanggil(evaluasi, monkeypatch, capsys):
    monkeypatch.setattr(alat, "hari_ini", lambda: "2026-10-17")
    alat.tambah_penghitung(2)
    alat.catat_token(900, 100, 1000)
    a = argumen("ringkas-token")
    import asyncio

    assert asyncio.run(alat.perintah_ringkas_token(a, alat.Pencatat(None, gema=False))) == 0
    keluar = capsys.readouterr().out
    assert "panggilan total (semua hari): 2" in keluar and "2026-10-17: panggilan 2, token 1000" in keluar


# --- T7: Pengaturan baru Sesi 5.6, relevansi dihitung ulang dari cache, gambar tanpa cache LLM ---


def test_urai_ambang_pengaturan_baru_sesi56():
    assert alat.urai_ambang(
        "toleransi_ocr=ya,kombinasi=ya,kombinasi_skor=0.855,kombinasi_relevansi=0.7,kombinasi_kata=4,lolos=0.90,"
        "kesetiaan_ketat=ya,teks=25"
    ) == {
        "relevansi_toleransi_ocr": True, "kuat_kombinasi_aktif": True, "kuat_kombinasi_skor": 0.855,
        "kuat_kombinasi_relevansi": 0.7, "kuat_kombinasi_min_kata": 4, "relevansi_lolos_skor": 0.9,
        "periksa_kesetiaan_klaim": True, "ambang_teks_karakter": 25,
    }


def test_relevansi_cache_selalu_dihitung_ulang_dengan_pengaturan_sekarang(monkeypatch):
    # Cache bisa dikumpulkan dengan profil lain, jadi nilai relevansi di cache tidak pernah dipakai apa adanya.
    p = alat.PencarianBerCache(object(), boleh=False)
    hasil = [{"judul": "[SALAH] Menkeu Suahasil korupsi", "relevansi": 0.123}]
    monkeypatch.setattr(p, "idf", lambda: ({"menkeu": 3.0, "suahasil": 5.0, "korupsi": 1.0}, 10))
    lama = p.hitung_ulang_relevansi("Menkeu Suhasasil korupsi", hasil)
    assert lama[0]["relevansi"] == pytest.approx(4.0 / 9.0)  # tanpa toleransi: "Suahasil" tidak ada
    with alat.terapkan_profil({"relevansi_toleransi_ocr": True}):
        baru = p.hitung_ulang_relevansi("Menkeu Suhasasil korupsi", hasil)
    assert baru[0]["relevansi"] == pytest.approx(1.0) and hasil[0]["relevansi"] == 0.123


async def test_gambar_tanpa_cache_llm_dilaporkan_terpisah_dari_galat(evaluasi, pencarian_palsu, pembaca_palsu):
    pencarian_palsu.kandidat = [kand(0.9)]
    b = alat.baca_metadata()[0]
    with alat.terpasang(alat.buat_komponen(ocr=True, cari=True, tanpa_llm=True)) as komp:
        await alat.jalankan_gambar(komp, b, "biasa")
    hasil = await alat.nilai_baris(alat.buat_komponen(), [b], {}, "biasa")  # cache LLM tidak ada
    r = hasil["biasa"]["d1"]
    assert r["hasil"] == "kuat" and r["llm_kosong"] is True and r["llm_ada"] is False
    m = alat.metrik([(b, r)])
    assert m["belum"] == 0 and m["llm_kosong"] == 1
    teks = alat.laporan("x", "dev", {}, [b], hasil).read_text(encoding="utf-8")
    assert "Tanpa cache LLM (dinilai seperti LLM gagal, tidak termasuk galat): 1 (d1)" in teks
