"""Pencarian cek fakta dengan indeks kecil buatan dan embedder palsu. Tidak memuat e5 asli dan tidak membaca
server/data_lokal."""

import importlib.util
import json
import logging
import re
from pathlib import Path

import numpy as np
import pytest

from app.konfigurasi import Pengaturan
from app.pipeline import cocok
from app.pipeline.cocok import Pencarian
from app.pipeline.tipe import Kandidat

pytestmark = pytest.mark.anyio
DIM = 64


@pytest.fixture
def anyio_backend():
    return "asyncio"


def bow(teks: str) -> np.ndarray:
    """Vektor kantong kata berhash, ternormalisasi L2: teks yang berbagi kata punya cosine tinggi."""
    v = np.zeros(DIM, dtype=np.float32)
    for kata in re.findall(r"[a-z0-9]+", teks.lower()):
        v[sum(ord(c) * (i + 1) for i, c in enumerate(kata)) % DIM] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


class EmbedderPalsu:
    def __init__(self):
        self.kueri: list[str] = []

    def encode_kueri(self, teks: list[str]):
        self.kueri += teks
        return np.stack([bow(t) for t in teks])


ARTIKEL = [
    {"id": "a1", "judul": "[SALAH] Air keran Jakarta mengandung zat berbahaya", "narasi": "Beredar pesan air keran Jakarta mengandung zat berbahaya penyebab penyakit.",
     "label": "salah", "sumber": "TurnBackHoax", "url": "https://turnbackhoax.id/articles/1-air-keran", "tanggal": "2025-11-04"},
    {"id": "a2", "judul": "[PENIPUAN] Hadiah undian bank pesan berantai", "narasi": "Pesan berisi hadiah undian dari bank meminta kode verifikasi.",
     "label": "penipuan", "sumber": "Komdigi", "url": "https://turnbackhoax.id/2019/05/01/hadiah-undian/", "tanggal": "2019-05-01",
     "url_format_lama": True},
    {"id": "a3", "judul": "[KLARIFIKASI] Jalan Merdeka ditutup untuk perbaikan", "narasi": "Dinas pekerjaan umum menutup Jalan Merdeka pada Oktober.",
     "label": "klarifikasi", "sumber": "Kominfo", "url": "https://example.test/3", "tanggal": ""},
    {"id": "a4", "judul": "Vaksin cacar air dan penyakit shingles", "narasi": "",
     "label": "lainnya", "sumber": "Media", "url": "https://example.test/4", "tanggal": "bukan-tanggal"},
]


def bangun_indeks(folder: Path, artikel=ARTIKEL, ukuran="base", varian="fp32", ubah_meta=None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "artikel.jsonl", "w", encoding="utf-8") as f:
        for a in artikel:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    vektor = np.stack([bow(cocok.teks_passage(a).removeprefix("passage: ")) for a in artikel])
    np.save(folder / f"vektor_{ukuran}_{varian}.npy", vektor)
    meta = {"jumlah": len(artikel), "dimensi": DIM, "ukuran": ukuran, "varian": varian, "maks_token": 256,
            "teks_sha1": cocok.sidik_teks(artikel)}
    meta.update(ubah_meta or {})
    (folder / f"vektor_{ukuran}_{varian}.json").write_text(json.dumps(meta), encoding="utf-8")


def pengaturan_uji(folder: Path, **ubah) -> Pengaturan:
    return Pengaturan(cek_fakta_folder=folder, model_folder=folder / "model", **ubah)


def pencarian_siap(tmp_path: Path, **ubah) -> tuple[Pencarian, EmbedderPalsu]:
    bangun_indeks(tmp_path)
    embedder = EmbedderPalsu()
    p = Pencarian(buat_embedder=lambda cfg, maks_token: embedder)
    p.muat(pengaturan_uji(tmp_path, **ubah))
    assert p.status == cocok.STATUS_SIAP, p.alasan
    return p, embedder


# --- pemuatan ---


def test_muat_indeks_kecil_siap(tmp_path):
    p, _ = pencarian_siap(tmp_path)
    assert p.jumlah == 4 and p.detik_muat >= 0
    assert p.ringkasan().startswith("siap, 4 artikel (e5-base fp32)")


def test_nonaktif_lewat_konfigurasi_tidak_memuat_apa_pun(tmp_path):
    p = Pencarian(buat_embedder=lambda *a: pytest.fail("embedder tidak boleh dibuat"))
    p.muat(pengaturan_uji(tmp_path, cek_fakta_aktif=False))
    assert p.status == cocok.STATUS_NONAKTIF and "CEKHOAKS_CEKFAKTA=mati" in p.ringkasan()
    assert p.cari("apa saja", 3) == []


def test_berkas_tidak_ada_pencarian_tidak_tersedia_dengan_pesan_jelas(tmp_path):
    p = Pencarian(buat_embedder=lambda *a: EmbedderPalsu())
    p.muat(pengaturan_uji(tmp_path / "tidak-ada"))
    assert p.status == cocok.STATUS_TIDAK_TERSEDIA
    assert "artikel.jsonl" in p.alasan and "TIDAK TERSEDIA" in p.ringkasan()
    assert p.cari("air keran", 3) == []


def test_vektor_tidak_cocok_dengan_artikel_ditolak(tmp_path):
    bangun_indeks(tmp_path, ubah_meta={"teks_sha1": "0000000000000000"})
    p = Pencarian(buat_embedder=lambda *a: EmbedderPalsu())
    p.muat(pengaturan_uji(tmp_path))
    assert p.status == cocok.STATUS_TIDAK_TERSEDIA and "tidak cocok" in p.alasan


def test_jumlah_vektor_beda_dari_jumlah_artikel_ditolak(tmp_path):
    bangun_indeks(tmp_path)
    np.save(tmp_path / "vektor_base_fp32.npy", np.zeros((3, DIM), dtype=np.float32))
    p = Pencarian(buat_embedder=lambda *a: EmbedderPalsu())
    p.muat(pengaturan_uji(tmp_path))
    assert p.status == cocok.STATUS_TIDAK_TERSEDIA


def test_model_tidak_ada_atau_paket_hilang_tidak_menjatuhkan_server(tmp_path):
    bangun_indeks(tmp_path)

    def buat(cfg, maks_token):
        raise cocok.PencarianTidakTersedia("paket tokenizers belum terpasang")

    p = Pencarian(buat_embedder=buat)
    p.muat(pengaturan_uji(tmp_path))
    assert p.status == cocok.STATUS_TIDAK_TERSEDIA and "tokenizers" in p.alasan


def test_galat_tak_terduga_saat_memuat_hanya_dicatat_jenisnya(tmp_path):
    bangun_indeks(tmp_path)

    def buat(cfg, maks_token):
        raise RuntimeError("rahasia")

    p = Pencarian(buat_embedder=buat)
    p.muat(pengaturan_uji(tmp_path))
    assert p.status == cocok.STATUS_TIDAK_TERSEDIA and p.alasan == "gagal memuat (RuntimeError)"


def test_model_asli_tidak_ditemukan_memberi_pesan_berkas(tmp_path):
    bangun_indeks(tmp_path)
    p = Pencarian()  # embedder asli, tetapi folder model tidak ada: gagal sebelum paket apa pun diimpor
    p.muat(pengaturan_uji(tmp_path))
    assert p.status == cocok.STATUS_TIDAK_TERSEDIA and "model" in p.alasan


# --- pencarian ---


def test_pencarian_mengurutkan_dan_membatasi_jumlah(tmp_path):
    p, embedder = pencarian_siap(tmp_path)
    hasil = p.cari("air keran Jakarta mengandung zat berbahaya", 2)
    assert len(hasil) == 2
    assert hasil[0].judul.startswith("[SALAH] Air keran")
    assert hasil[0].skor >= hasil[1].skor and 0.0 <= hasil[0].skor <= 1.0
    assert embedder.kueri == ["air keran Jakarta mengandung zat berbahaya"]  # spasi dirapikan


def test_kandidat_membawa_label_sumber_url_tanggal_dan_penanda_format_lama(tmp_path):
    p, _ = pencarian_siap(tmp_path)
    a1, a2 = (p.cari(t, 1)[0] for t in ("air keran Jakarta zat berbahaya", "hadiah undian bank kode verifikasi"))
    assert (a1.label, a1.sumber, a1.url) == ("salah", "TurnBackHoax", "https://turnbackhoax.id/articles/1-air-keran")
    assert str(a1.tanggal) == "2025-11-04" and a1.url_format_lama is False
    assert a2.label == "penipuan" and a2.url_format_lama is True and a2.narasi.startswith("Pesan berisi")


def test_tanggal_kosong_atau_rusak_menjadi_none(tmp_path):
    p, _ = pencarian_siap(tmp_path)
    semua = {k.judul[:5]: k for k in p.cari("Jalan Merdeka vaksin cacar air shingles", 4)}
    assert all(k.tanggal is None for k in semua.values() if k.label in ("klarifikasi", "lainnya"))


def test_kueri_kosong_tidak_memanggil_embedder(tmp_path):
    p, embedder = pencarian_siap(tmp_path)
    assert p.cari("   \n ", 3) == [] and embedder.kueri == []


async def test_cari_kecocokan_memakai_top_k_konfigurasi(tmp_path, monkeypatch):
    p, _ = pencarian_siap(tmp_path)
    monkeypatch.setattr(cocok, "pencarian", p)
    hasil = await cocok.cari_kecocokan("air keran Jakarta", Pengaturan(cocok_top_k=3))
    assert hasil.lengkap is True
    assert len(hasil.kandidat) == 3 and all(isinstance(k, Kandidat) for k in hasil.kandidat)


async def test_cari_kecocokan_kosong_bila_pencarian_tidak_siap(monkeypatch):
    monkeypatch.setattr(cocok, "pencarian", Pencarian())
    hasil = await cocok.cari_kecocokan("teks apa saja")
    assert hasil.kandidat == [] and hasil.lengkap is False


async def test_pencarian_gagal_tidak_menggagalkan_dan_tidak_membocorkan_teks(tmp_path, monkeypatch, caplog):
    p, _ = pencarian_siap(tmp_path)

    def rusak(teks, k):
        raise ValueError("RAHASIA-ISI-TEKS")

    monkeypatch.setattr(p, "cari", rusak)
    monkeypatch.setattr(cocok, "pencarian", p)
    caplog.set_level(logging.INFO)
    hasil = await cocok.cari_kecocokan("RAHASIA-ISI-TEKS")
    assert hasil.kandidat == [] and hasil.lengkap is False
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "ValueError" in log and "RAHASIA" not in log


# --- paritas dengan alat/cek_fakta ---


def _muat_skema_alat():
    jalur = Path(__file__).resolve().parents[1] / "alat" / "cek_fakta" / "skema.py"
    spec = importlib.util.spec_from_file_location("skema_alat_cek_fakta", jalur)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


JUDUL_UJI = [
    "[SALAH] Video \"Bunker-Bunker di Israel Mulai Terendam Banjir\"", "(ISU) : Pesan berantai", "HOAX: Hadiah mobil",
    "[SALAH Anies tidak pernah", "BENAR] Dana desa", "Judul tanpa awalan", "[Hoaks] [Satir] ganda", "  ", "",
]


def test_judul_bersih_dan_passage_sama_dengan_alat():
    alat = _muat_skema_alat()
    for judul in JUDUL_UJI:
        assert cocok.judul_bersih(judul) == alat.judul_bersih(judul), judul
        artikel = {"judul": judul, "narasi": "narasi uji"}
        assert cocok.teks_passage(artikel) == alat.teks_passage(artikel)
        assert cocok.teks_passage({"judul": judul}) == alat.teks_passage({"judul": judul})


def test_sidik_teks_sama_dengan_alat_embed():
    """embed.py alat tidak diimpor (butuh onnxruntime di venv lain); rumusnya dibandingkan lewat skema alat."""
    import hashlib

    alat = _muat_skema_alat()
    h = hashlib.sha1()
    for a in ARTIKEL:
        h.update(f"{a['id']}\n{alat.teks_passage(a)}\n".encode("utf-8"))
    assert cocok.sidik_teks(ARTIKEL) == h.hexdigest()[:16]


# --- kalimat bukti ---

ARTIKEL_AIR = Kandidat(
    judul="[SALAH] Air keran Jakarta mengandung zat berbahaya", sumber="TBH", url="u", skor=0.9, label="salah",
    tanggal=None, url_format_lama=False, narasi="Beredar pesan air keran Jakarta mengandung zat berbahaya penyebab penyakit.",
)


def test_kalimat_serupa_memilih_kalimat_dengan_kata_isi_yang_sama():
    teks = "Halo semua.\nAir keran di Jakarta mengandung zat berbahaya penyebab penyakit.\nSampai jumpa besok."
    # Tepi dipangkas ke bagian yang sama dengan judul artikel.
    assert cocok.kalimat_serupa(teks, ARTIKEL_AIR) == "Air keran di Jakarta mengandung zat berbahaya"


def test_kalimat_serupa_menyambung_baris_yang_terbelah_dan_hasilnya_potongan_teks():
    teks = "Air keran di Jakarta\nmengandung zat berbahaya penyebab penyakit.\nTerima kasih"
    bukti = cocok.kalimat_serupa(teks, ARTIKEL_AIR)
    assert bukti in re.sub(r"\s+", " ", teks)


def test_kalimat_serupa_tanpa_irisan_memakai_klaim_heuristik():
    teks = "Pemerintah kota mengumumkan perbaikan jalan di Jalan Merdeka pada 12-14 Oktober.\nSelesai."
    bukti = cocok.kalimat_serupa(teks, ARTIKEL_AIR)
    assert bukti.startswith("Pemerintah kota mengumumkan perbaikan jalan")


def test_kalimat_serupa_dipotong_di_batas_kata_tanpa_elipsis():
    panjang = "air keran Jakarta mengandung zat berbahaya penyebab penyakit " * 6
    bukti = cocok.kalimat_serupa(panjang.strip() + ".", ARTIKEL_AIR, Pengaturan(ciri_bukti_maks_karakter=50))
    assert len(bukti) <= 50 and "…" not in bukti
    assert bukti == bukti.strip() and bukti in panjang
    assert bukti.startswith("keran") and bukti.endswith("berbahaya")


def test_potong_di_batas_kata():
    assert cocok.potong_di_batas_kata("satu dua tiga empat", 12) == "satu dua"
    assert cocok.potong_di_batas_kata("satu dua", 8) == "satu dua"
    assert cocok.potong_di_batas_kata("satu dua tiga", 8) == "satu dua"
