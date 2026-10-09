import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metrik import kata_penilaian_tambahan, kutipan_jujur, persentil, urai_json, validasi  # noqa: E402
from prompt import id_terkunci, id_untuk_llm  # noqa: E402
from samarkan import samarkan  # noqa: E402

IDS = id_untuk_llm()


def test_samarkan_pribadi_tetapi_tautan_utuh():
    t = "Hubungi 0812-3456-7890 atau +62 812 3456 7890, email a.b@mail.com, akun @budi_99. Klik bit.ly/abc123 dan https://x.id/p?u=1"
    s = samarkan(t)
    assert "0812" not in s and "[NOMOR]" in s and "[EMAIL]" in s and "[AKUN]" in s
    assert "bit.ly/abc123" in s and "https://x.id/p?u=1" in s


def test_samarkan_tidak_merusak_angka_biasa():
    t = "Transfer Rp 1.500.000 pada 17 Agustus 2026 pukul 10.30"
    assert samarkan(t) == t


def test_id_pernah_dibantah_tidak_ditawarkan_ke_llm():
    assert "pernah_dibantah" in id_terkunci() and "pernah_dibantah" not in IDS


def test_validasi():
    ok = '{"klaim_utama":"x","ciri":[{"id":"desakan_waktu","kutipan":["segera"]}]}'
    assert validasi(ok, IDS)[0] is not None
    assert validasi('```json\n' + ok + '\n```', IDS)[0] is not None
    luar = '{"klaim_utama":"x","ciri":[{"id":"mengarang","kutipan":[]}]}'
    d, id_luar, m = validasi(luar, IDS)
    assert d is None and id_luar == ["mengarang"]
    assert validasi('{"klaim_utama":"x"}', IDS)[0] is None
    assert validasi("bukan json", IDS)[0] is None
    assert urai_json("") is None


def test_kutipan_jujur_normalisasi():
    d = {"ciri": [{"id": "desakan_waktu", "kutipan": ["SEGERA   sebarkan", "karangan"]}]}
    assert kutipan_jujur(d, "ayo segera\nsebarkan pesan ini") == (1, 2)


def test_kata_penilaian_hanya_yang_ditambahkan_model():
    assert kata_penilaian_tambahan("Pesan ini hoaks", "ada pesan") == ["hoaks"]
    assert kata_penilaian_tambahan("Korban salah transfer", "salah transfer ke rekening") == []
    assert kata_penilaian_tambahan("Sebenarnya begitu", "x") == []
    # OCR menempelkan kata: tetap berasal dari teks asli
    assert kata_penilaian_tambahan("Akun terdeteksi palsu", "AKUN ANDA TERDETEKSIPALSU DAN") == []


def test_persentil():
    assert persentil([1, 2, 3, 4, 100], 95) == 100 and persentil([], 50) is None
