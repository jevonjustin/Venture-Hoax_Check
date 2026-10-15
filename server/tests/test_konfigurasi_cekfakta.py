import pytest

from app.konfigurasi import KonfigurasiTidakValid, muat


def test_nilai_bawaan_pencarian_cek_fakta():
    p = muat({})
    assert p.cek_fakta_aktif is True
    assert (p.cocok_top_k, p.cek_fakta_maks) == (5, 3)
    assert (p.ambang_cocok, p.ambang_mirip, p.selisih_konflik) == (0.88, 0.85, 0.02)
    assert p.satir_hati_hati is True
    assert p.cek_fakta_folder.name == "cek_fakta" and p.model_folder.name == "model"
    assert p.cek_fakta_folder.parent.name == "data_lokal"


def test_sakelar_cek_fakta_mati_dan_folder_bisa_ditimpa(tmp_path):
    p = muat({
        "CEKHOAKS_CEKFAKTA": " MATI ", "CEKHOAKS_CEKFAKTA_FOLDER": str(tmp_path),
        "CEKHOAKS_MODEL_FOLDER": str(tmp_path / "m"),
    })
    assert p.cek_fakta_aktif is False
    assert p.cek_fakta_folder == tmp_path and p.model_folder == tmp_path / "m"
    assert muat({"CEKHOAKS_CEKFAKTA": "aktif"}).cek_fakta_aktif is True


def test_sakelar_cek_fakta_tidak_dikenal_ditolak():
    with pytest.raises(KonfigurasiTidakValid) as e:
        muat({"CEKHOAKS_CEKFAKTA": "mungkin"})
    assert "'mungkin'" in str(e.value)
