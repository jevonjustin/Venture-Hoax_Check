"""Pengunduhan data pencarian dari dataset Hugging Face (Sesi 8.1). Semua pengunduh di sini tiruan: tanpa jaringan
dan tanpa huggingface_hub."""

import dataclasses
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import data_hf, konfigurasi, main
from app.konfigurasi import Pengaturan, muat
from app.pipeline import cocok

TOKEN_RAHASIA = "hf_tokenRahasiaUntukUji123"

BERKAS_HARAPAN = [
    "cek_fakta/artikel.jsonl",
    "cek_fakta/vektor_base_fp32.npy",
    "cek_fakta/vektor_base_fp32.json",
    "model/e5-base/model.onnx",
    "model/e5-base/tokenizer.json",
]


class PengunduhTiruan:
    """Meniru snapshot_download: menulis berkas yang diminta allow_patterns ke local_dir, atau melempar galat."""

    def __init__(self, galat: Exception | None = None, lewati: tuple[str, ...] = ()):
        self.galat = galat
        self.lewati = lewati
        self.panggilan: list[dict] = []

    def __call__(self, **kwargs):
        self.panggilan.append(kwargs)
        if self.galat:
            raise self.galat
        for pola in kwargs["allow_patterns"]:
            if pola in self.lewati:
                continue
            jalur = Path(kwargs["local_dir"]) / pola
            jalur.parent.mkdir(parents=True, exist_ok=True)
            jalur.write_bytes(b"isi")
        return kwargs["local_dir"]


def _cfg(tmp_path, **ubah) -> Pengaturan:
    return dataclasses.replace(Pengaturan(), hf_dataset="jevonjustin/veritas-data", hf_folder=tmp_path / "hf", **ubah)


def test_pengaturan_dari_lingkungan(tmp_path):
    bawaan = muat({})
    assert bawaan.hf_dataset is None
    assert bawaan.hf_folder == konfigurasi.DATA_LOKAL.parent / "data_hf"
    p = muat({"CEKHOAKS_HF_DATASET": " jevonjustin/veritas-data ", "CEKHOAKS_HF_FOLDER": str(tmp_path)})
    assert (p.hf_dataset, p.hf_folder) == ("jevonjustin/veritas-data", tmp_path)
    # Folder data lokal tidak berubah hanya karena variabel diisi: pengarahan terjadi setelah unduhan berhasil.
    assert p.cek_fakta_folder == bawaan.cek_fakta_folder and p.model_folder == bawaan.model_folder


def test_berkas_yang_diunduh_sama_dengan_yang_dibaca_pencarian():
    assert data_hf.pola_berkas(Pengaturan()) == BERKAS_HARAPAN
    assert cocok.berkas_dibaca(Pengaturan()) == {
        "cek_fakta": ["artikel.jsonl", "vektor_base_fp32.npy", "vektor_base_fp32.json"],
        "model": ["e5-base/model.onnx", "e5-base/tokenizer.json"],
    }


def test_variabel_kosong_tidak_mengunduh_dan_tidak_mengubah_folder():
    cfg = Pengaturan()
    unduh = PengunduhTiruan()
    assert data_hf.siapkan(cfg, {"HF_TOKEN": TOKEN_RAHASIA}, unduh) is None
    assert unduh.panggilan == []
    assert cfg.cek_fakta_folder == Pengaturan().cek_fakta_folder


def test_cek_fakta_dimatikan_tidak_mengunduh(tmp_path):
    cfg = _cfg(tmp_path, cek_fakta_aktif=False)
    unduh = PengunduhTiruan()
    assert data_hf.siapkan(cfg, {}, unduh) is None
    assert unduh.panggilan == []


def test_berhasil_mengarahkan_folder_dan_memakai_token(tmp_path):
    cfg = _cfg(tmp_path)
    unduh = PengunduhTiruan()
    hasil = data_hf.siapkan(cfg, {"HF_TOKEN": f" {TOKEN_RAHASIA} "}, unduh)
    assert hasil.berhasil
    (panggilan,) = unduh.panggilan
    assert panggilan == {
        "repo_id": "jevonjustin/veritas-data", "repo_type": "dataset", "local_dir": str(tmp_path / "hf"),
        "allow_patterns": BERKAS_HARAPAN, "token": TOKEN_RAHASIA,
    }
    assert cfg.cek_fakta_folder == tmp_path / "hf" / "cek_fakta"
    assert cfg.model_folder == tmp_path / "hf" / "model"
    assert (cfg.model_folder / "e5-base" / "model.onnx").is_file()


def test_galat_unduh_tidak_mencetak_token_dan_folder_tetap(tmp_path, caplog):
    cfg = _cfg(tmp_path)
    galat = RuntimeError(f"401 Client Error for url https://huggingface.co/x (Authorization: Bearer {TOKEN_RAHASIA})")
    unduh = PengunduhTiruan(galat=galat)
    with caplog.at_level(logging.INFO):
        hasil = data_hf.siapkan_atau_tandai(cfg, {"HF_TOKEN": TOKEN_RAHASIA}, unduh)
    assert not hasil.berhasil
    assert TOKEN_RAHASIA not in hasil.alasan and "RuntimeError" in hasil.alasan and "401" in hasil.alasan
    assert TOKEN_RAHASIA not in caplog.text
    assert "Data pencarian tidak disiapkan" in caplog.text and "jevonjustin/veritas-data" in caplog.text
    assert cfg.cek_fakta_folder == Pengaturan().cek_fakta_folder
    assert cocok.pencarian.status == cocok.STATUS_TIDAK_TERSEDIA
    assert cocok.pencarian.alasan == hasil.alasan


def test_tanpa_token_diberi_petunjuk(tmp_path):
    hasil = data_hf.siapkan(_cfg(tmp_path), {}, PengunduhTiruan(galat=RuntimeError("401 Unauthorized")))
    assert not hasil.berhasil and "HF_TOKEN kosong" in hasil.alasan


def test_paket_belum_terpasang(tmp_path):
    hasil = data_hf.siapkan(_cfg(tmp_path), {}, PengunduhTiruan(galat=ImportError("huggingface_hub")))
    assert not hasil.berhasil and "huggingface_hub" in hasil.alasan


def test_berkas_hilang_di_dataset_dianggap_gagal(tmp_path):
    cfg = _cfg(tmp_path)
    hasil = data_hf.siapkan(cfg, {}, PengunduhTiruan(lewati=("model/e5-base/model.onnx",)))
    assert not hasil.berhasil and "model/e5-base/model.onnx" in hasil.alasan
    assert cfg.model_folder == Pengaturan().model_folder


# --- Lifespan: server tetap menyala, pencarian dimuat dari folder unduhan atau ditandai tidak tersedia ---


class PencarianCatat:
    status = cocok.STATUS_BELUM
    alasan = ""

    def __init__(self):
        self.dimuat_dari = None

    async def siapkan(self):
        self.dimuat_dari = (konfigurasi.pengaturan.cek_fakta_folder, konfigurasi.pengaturan.model_folder)
        self.status = cocok.STATUS_SIAP
        return 0.0

    def tandai_tidak_tersedia(self, alasan):
        self.status, self.alasan = cocok.STATUS_TIDAK_TERSEDIA, alasan

    def ringkasan(self):
        return self.status if self.status == cocok.STATUS_SIAP else f"TIDAK TERSEDIA: {self.alasan}"

    def cari(self, teks, k):
        return []


@pytest.fixture
def server_hf(monkeypatch, tmp_path):
    p = konfigurasi.pengaturan
    monkeypatch.setattr(p, "hf_dataset", "jevonjustin/veritas-data")
    monkeypatch.setattr(p, "hf_folder", tmp_path / "hf")
    monkeypatch.setattr(p, "cek_fakta_folder", p.cek_fakta_folder)
    monkeypatch.setattr(p, "model_folder", p.model_folder)
    monkeypatch.setenv("HF_TOKEN", TOKEN_RAHASIA)
    pencarian = PencarianCatat()
    monkeypatch.setattr(cocok, "pencarian", pencarian)
    return pencarian, tmp_path / "hf"


def _pasang_pengunduh(monkeypatch, unduh):
    monkeypatch.setattr(data_hf, "_snapshot_download", unduh)


def test_lifespan_mengunduh_lalu_memuat_dari_folder_unduhan(monkeypatch, server_hf, capsys):
    pencarian, folder = server_hf
    unduh = PengunduhTiruan()
    _pasang_pengunduh(monkeypatch, unduh)
    with TestClient(main.app) as klien:
        assert klien.get("/health").status_code == 200
    assert len(unduh.panggilan) == 1 and unduh.panggilan[0]["token"] == TOKEN_RAHASIA
    assert pencarian.dimuat_dari == (folder / "cek_fakta", folder / "model")
    keluar = capsys.readouterr().out
    assert "Mengunduh data pencarian dari dataset jevonjustin/veritas-data" in keluar
    assert TOKEN_RAHASIA not in keluar


def test_lifespan_unduhan_gagal_server_tetap_menyala_tanpa_cek_fakta(monkeypatch, server_hf, capsys, caplog):
    pencarian, _ = server_hf
    _pasang_pengunduh(monkeypatch, PengunduhTiruan(galat=ConnectionError(f"gagal {TOKEN_RAHASIA}")))
    with caplog.at_level(logging.INFO), TestClient(main.app) as klien:
        assert klien.get("/health").json()["status"] == "ok"
        r = klien.post("/analisis", files={"gambar": ("p.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200
    assert "cek_fakta" in r.json()["pemeriksaan_terbatas"]
    assert pencarian.dimuat_dari is None  # tidak dimuat dari folder yang tidak lengkap
    assert pencarian.status == cocok.STATUS_TIDAK_TERSEDIA
    keluar = capsys.readouterr()
    assert TOKEN_RAHASIA not in keluar.out + keluar.err + caplog.text
    assert "TIDAK TERSEDIA: unduhan dataset jevonjustin/veritas-data gagal (ConnectionError" in keluar.out


def _jpeg() -> bytes:
    import io

    from PIL import Image

    keluaran = io.BytesIO()
    Image.new("RGB", (120, 80), (200, 30, 30)).save(keluaran, format="JPEG")
    return keluaran.getvalue()
