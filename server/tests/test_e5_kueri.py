"""Panjang token kueri e5 terpisah dari passage, kunci cache evaluasi memuat varian, dan alat ukur. Tanpa jaringan,
tanpa model asli, tanpa membaca server/data_lokal."""

import importlib.util
from pathlib import Path

from test_cocok import EmbedderPalsu, bangun_indeks, pengaturan_uji

from app.konfigurasi import Pengaturan
from app.pipeline import cocok
from app.pipeline.cocok import Pencarian

ALAT = Path(__file__).resolve().parents[1] / "alat" / "uji_analisis"


def muat_alat(nama: str):
    spec = importlib.util.spec_from_file_location(f"{nama}_alat_e5", ALAT / f"{nama}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def muat_dengan_pencatat(tmp_path, ubah_meta=None, **ubah) -> list[int]:
    bangun_indeks(tmp_path, ubah_meta=ubah_meta)
    diterima: list[int] = []

    def buat(cfg, maks_token):
        diterima.append(maks_token)
        return EmbedderPalsu()

    p = Pencarian(buat_embedder=buat)
    p.muat(pengaturan_uji(tmp_path, **ubah))
    assert p.status == cocok.STATUS_SIAP, p.alasan
    return diterima


def test_bawaan_kueri_tetap_256():
    assert Pengaturan().e5_maks_token_kueri == 256
    assert Pengaturan().e5_model_berkas is None and Pengaturan().e5_vektor_berkas is None


def test_bawaan_meneruskan_256_ke_embedder(tmp_path):
    assert muat_dengan_pencatat(tmp_path) == [256]


def test_nilai_512_diteruskan_tanpa_memengaruhi_pemuatan_vektor(tmp_path):
    # meta passage tetap 256; teks_sha1 tetap diperiksa terhadap artikel
    assert muat_dengan_pencatat(tmp_path, e5_maks_token_kueri=512) == [512]


def test_meta_maks_token_tidak_menimpa_nilai_kueri(tmp_path):
    assert muat_dengan_pencatat(tmp_path, ubah_meta={"maks_token": 128}, e5_maks_token_kueri=512) == [512]


def test_sidik_teks_tetap_diperiksa_dengan_kueri_512(tmp_path):
    bangun_indeks(tmp_path, ubah_meta={"teks_sha1": "salah"})
    p = Pencarian(buat_embedder=lambda *a: EmbedderPalsu())
    p.muat(pengaturan_uji(tmp_path, e5_maks_token_kueri=512))
    assert p.status == cocok.STATUS_TIDAK_TERSEDIA and "tidak cocok" in p.alasan


def test_embedder_asli_memotong_kueri_sesuai_nilai(monkeypatch, tmp_path):
    """EmbedderE5 meneruskan maks_token ke truncation tokenizer (tiruan tokenizers dan onnxruntime)."""
    import sys
    import types

    catatan = {}

    class TokPalsu:
        @staticmethod
        def from_file(_):
            return TokPalsu()

        def enable_truncation(self, max_length):
            catatan["maks"] = max_length

        def enable_padding(self, **_):
            pass

        def token_to_id(self, _):
            return 1

    class SesiPalsu:
        def __init__(self, *a, **k):
            pass

        def get_inputs(self):
            return []

    ort = types.SimpleNamespace(
        SessionOptions=lambda: types.SimpleNamespace(log_severity_level=0), InferenceSession=SesiPalsu
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "tokenizers", types.SimpleNamespace(Tokenizer=TokPalsu))
    cocok.EmbedderE5(tmp_path / "m.onnx", tmp_path / "t.json", 512)
    assert catatan["maks"] == 512


def test_berkas_model_dan_vektor_khusus_dipakai(tmp_path):
    folder = tmp_path / "db"
    bangun_indeks(folder)
    int8 = tmp_path / "model_int8"
    int8.mkdir()
    for ekstensi in (".npy", ".json"):
        (int8 / f"vek{ekstensi}").write_bytes((folder / f"vektor_base_fp32{ekstensi}").read_bytes())
    diterima = []
    p = Pencarian(buat_embedder=lambda cfg, mt: diterima.append(cfg.e5_model_berkas) or EmbedderPalsu())
    p.muat(pengaturan_uji(folder, e5_vektor_berkas=int8 / "vek.npy", e5_model_berkas=int8 / "m.onnx"))
    assert p.status == cocok.STATUS_SIAP, p.alasan
    assert diterima == [int8 / "m.onnx"]


def test_kunci_cache_pencarian_berbeda_menurut_kueri_dan_varian(tmp_path, monkeypatch):
    alat = muat_alat("evaluasi_berlabel")
    folder = tmp_path / "db"
    bangun_indeks(folder)
    bangun_indeks(folder, varian="int8")
    cfg = pengaturan_uji(folder)
    monkeypatch.setattr(alat.konfigurasi, "pengaturan", cfg)
    cari = alat.PencarianBerCache(None, False)

    dasar = (cari.versi_db(), cari.sufiks_varian())
    assert dasar[1] == ""  # bawaan: nama berkas cache lama tidak berubah
    cfg.e5_maks_token_kueri = 512
    k512 = (cari.versi_db(), cari.sufiks_varian())
    cfg.cek_fakta_varian = "int8"
    int8_512 = (cari.versi_db(), cari.sufiks_varian())
    cfg.e5_maks_token_kueri = 256
    int8_256 = (cari.versi_db(), cari.sufiks_varian())
    semua = {dasar, k512, int8_512, int8_256}
    assert len(semua) == 4
    assert len({s[1] for s in semua}) == 4  # nama berkas juga beda, jadi tidak saling menimpa
    cfg.cek_fakta_varian = "fp32"
    cfg.e5_model_berkas = tmp_path / "model_int8.onnx"
    assert (cari.versi_db(), cari.sufiks_varian()) not in semua


def test_opsi_cli_e5_menimpa_pengaturan(monkeypatch):
    alat = muat_alat("evaluasi_berlabel")
    cfg = Pengaturan()
    a = alat.buat_parser().parse_args(
        ["--maks-token-kueri", "512", "--varian-e5", "int8", "--model-e5", "m.onnx", "--vektor-e5", "v.npy",
         "nilai", "--set", "dev"]
    )
    alat.terapkan_opsi_e5(a, cfg)
    assert (cfg.e5_maks_token_kueri, cfg.cek_fakta_varian) == (512, "int8")
    assert cfg.e5_model_berkas == Path("m.onnx") and cfg.e5_vektor_berkas == Path("v.npy")
    a = alat.buat_parser().parse_args(["--maks-token-kueri", "513", "nilai", "--set", "dev"])
    import pytest

    with pytest.raises(alat.GalatAlat):
        alat.terapkan_opsi_e5(a, Pengaturan())


def test_ukur_e5_membaca_kueri_dari_cache_ocr_dan_menolak_int8_tanpa_model(tmp_path, capsys):
    ukur = muat_alat("ukur_e5")
    ocr = tmp_path / "ocr"
    ocr.mkdir()
    (ocr / "a.json").write_text('{"teks": "mentah", "teks_bersih": "  teks   bersih "}', encoding="utf-8")
    (ocr / "b.json").write_text('{"teks": "hanya mentah"}', encoding="utf-8")
    (ocr / "c.json").write_text("rusak", encoding="utf-8")
    assert ukur.baca_kueri(ocr, None, None) == ["teks bersih", "hanya mentah"]
    assert ukur.baca_kueri(ocr, None, 1) == ["teks bersih"]
    assert ukur.main(["--cache-ocr", str(ocr), "--keluaran", str(tmp_path / "x.md")]) == 2
    assert "--model-int8" in capsys.readouterr().err
    assert ukur.main(["--cache-ocr", str(ocr), "--keluaran", str(tmp_path / "x.md"), "--varian", "fp32", "--token", "600"]) == 2


def test_ukur_e5_laporan_tanpa_isi_kueri(tmp_path):
    ukur = muat_alat("ukur_e5")
    hasil = {"detik_model": 1.5, "detik_vektor": 0.2, "n": 3, "median_ms": 40.0, "p90_ms": 60.0, "maks_ms": 70.0,
             "terpotong": 1, "median_token": 120, "ram_mb": 900.0}
    jalur = tmp_path / "h" / "ukur.md"
    ukur.tulis_laporan(jalur, [("fp32", 256, hasil), ("int8", 512, hasil)], ["- Model int8: m.onnx (lokal)."])
    isi = jalur.read_text(encoding="utf-8")
    assert "| fp32 | 256 |" in isi and "| int8 | 512 |" in isi and "1/3" in isi


def test_kuantisasi_menolak_tanpa_paket_atau_timpa(tmp_path, capsys):
    kuant = muat_alat("kuantisasi_e5")
    assert kuant.main(["--masukan", str(tmp_path / "tidak_ada.onnx"), "--keluaran", str(tmp_path / "k.onnx")]) == 2
    masukan, keluaran = tmp_path / "m.onnx", tmp_path / "k.onnx"
    masukan.write_bytes(b"x")
    keluaran.write_bytes(b"y")
    assert kuant.main(["--masukan", str(masukan), "--keluaran", str(keluaran)]) == 2
    assert keluaran.read_bytes() == b"y"
