"""Alat unggah Hugging Face (alat/hf, Sesi 8.1): hanya pemilihan berkas yang diuji, tanpa jaringan dan token."""

import sys
from pathlib import Path

import pytest

FOLDER_ALAT = Path(__file__).resolve().parents[1] / "alat" / "hf"
sys.path.insert(0, str(FOLDER_ALAT))

import unggah_data  # noqa: E402
import unggah_space  # noqa: E402
import umum  # noqa: E402

from app import data_hf  # noqa: E402
from app.konfigurasi import Pengaturan  # noqa: E402


def test_data_yang_diunggah_sama_dengan_yang_diunduh_server(tmp_path):
    sumber = {"cek_fakta": tmp_path / "ck", "model": tmp_path / "md"}
    berkas = unggah_data.daftar_berkas(sumber=sumber)
    assert [t for t, _ in berkas] == data_hf.pola_berkas(Pengaturan())
    assert berkas[0][1] == tmp_path / "ck" / "artikel.jsonl"
    assert berkas[3][1] == tmp_path / "md" / "e5-base" / "model.onnx"


def test_data_tidak_memuat_folder_lain_di_data_lokal():
    for tujuan, sumber in unggah_data.daftar_berkas():
        assert tujuan.split("/")[0] in ("cek_fakta", "model")
        assert not ({"dataset_mentah", "evaluasi", "uji_hp", "demo", "uji"} & set(Path(tujuan).parts))
        assert sumber.parent.parent.name in ("data_lokal", "model")


def test_space_hanya_berkas_server_yang_dibutuhkan():
    berkas = unggah_space.daftar_berkas()
    tujuan = [t for t, _ in berkas]
    assert tujuan[:5] == ["Dockerfile", ".dockerignore", "README.md", "requirements.txt", "requirements-space.txt"]
    assert all(t.startswith("app/") and t.endswith(".py") for t in tujuan[5:])
    assert "app/main.py" in tujuan and "app/pipeline/cocok.py" in tujuan and "app/data_hf.py" in tujuan
    assert dict(berkas)["README.md"].parent.name == "space"
    for t in tujuan:
        assert not (set(Path(t).parts) & umum.BAGIAN_TERLARANG), t
        assert ".env" not in t


def test_space_menolak_berkas_terlarang(tmp_path):
    for jalur in ("data_lokal/cek_fakta/artikel.jsonl", ".env", "tests/test_api.py", ".venv/x.py", "app/.env.lokal"):
        with pytest.raises(unggah_space.BerkasTerlarang):
            unggah_space.periksa_aman(jalur)
    unggah_space.periksa_aman("app/pipeline/cocok.py")
    # Folder app yang memuat berkas terlarang (misalnya __pycache__) dilewati, bukan diunggah.
    (tmp_path / "app" / "__pycache__").mkdir(parents=True)
    (tmp_path / "app" / "__pycache__" / "x.py").write_text("")
    (tmp_path / "app" / "a.py").write_text("")
    assert [t for t, _ in unggah_space.daftar_berkas(tmp_path)][5:] == ["app/a.py"]


def test_space_menghapus_sisa_versi_lama_kecuali_gitattributes():
    di_space = {".gitattributes", "README.md", "app/main.py", "app/lama.py"}
    assert unggah_space.operasi_hapus(di_space, {"README.md", "app/main.py"}) == ["app/lama.py"]


def test_variabel_space_bukan_rahasia():
    assert unggah_space.VARIABEL == {
        "CEKHOAKS_HF_DATASET": "jevonjustin/veritas-data", "CEKHOAKS_HOST": "0.0.0.0", "CEKHOAKS_PORT": "7860",
    }
    assert not any("TOKEN" in k or "KEY" in k for k in unggah_space.VARIABEL)


def test_dockerignore_hanya_mengizinkan_app_dan_requirements():
    isi = (Path(unggah_space.SERVER) / ".dockerignore").read_text(encoding="utf-8").split()
    izin = [b for b in isi if b.startswith("!")]
    assert "*" in isi and izin == ["!app/", "!requirements.txt", "!requirements-space.txt"]


def test_token_kosong_menolak_jalan(monkeypatch, capsys):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit) as keluar:
        umum.ambil_token()
    assert keluar.value.code == 2
    assert "HF_TOKEN" in capsys.readouterr().err


class ApiTiruan:
    def __init__(self, privat):
        self.privat = privat
        self.dibuat = []

    def create_repo(self, repo_id, **kw):
        self.dibuat.append((repo_id, kw))

    def repo_info(self, repo_id, **kw):
        return type("Info", (), {"private": self.privat})()


def test_dataset_tidak_privat_ditolak(capsys):
    api = ApiTiruan(privat=False)
    with pytest.raises(SystemExit) as keluar:
        unggah_data.pastikan_privat(api, buat=True)
    assert keluar.value.code == 4
    assert api.dibuat == [("jevonjustin/veritas-data", {"repo_type": "dataset", "private": True, "exist_ok": True})]
    assert "TIDAK privat" in capsys.readouterr().err
    unggah_data.pastikan_privat(ApiTiruan(privat=True), buat=False)
