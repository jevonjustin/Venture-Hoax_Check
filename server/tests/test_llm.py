"""Klien LLM dengan transport palsu: urutan penyedia, coba ulang, batas waktu, galat, dan privasi log.
Tidak ada panggilan jaringan."""

import importlib.util
import json
import logging
import time
from pathlib import Path

import pytest

from app.konfigurasi import Pengaturan
from app.konfigurasi import VERSI_SERVER
from app.pipeline import llm
from app.pipeline.tipe import KandidatLLM

pytestmark = [pytest.mark.anyio, pytest.mark.llm_nyata]

KUNCI_GROQ = "gsk_RAHASIA_GROQ_123"
KUNCI_GEMINI = "AIza_RAHASIA_GEMINI_456"
TEKS = "Pesan berantai RAHASIA-ISI-TEKS: segera sebarkan ke semua keluarga sebelum dihapus"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def kunci_terisi(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KUNCI_GROQ)
    monkeypatch.setenv("GEMINI_API_KEY", KUNCI_GEMINI)


def balasan(klaim="Air keran berbahaya", ciri=None, status=200) -> tuple[int, str]:
    isi = json.dumps({"klaim_utama": klaim, "ciri": ciri if ciri is not None else []})
    return status, json.dumps({"choices": [{"message": {"content": isi}}]})


class TransportPalsu:
    """Antrean balasan per penyedia. Item: (status, isi), Exception (dilempar), atau callable(timeout)."""

    def __init__(self, groq=(), gemini=()):
        self.antrean = {"groq": list(groq), "gemini": list(gemini)}
        self.panggilan: list[tuple[str, dict, str, float]] = []

    def __call__(self, penyedia, badan, kunci, timeout):
        self.panggilan.append((penyedia.nama, badan, kunci, timeout))
        item = self.antrean[penyedia.nama].pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(timeout)
        return item

    def jumlah(self, nama: str) -> int:
        return sum(1 for p in self.panggilan if p[0] == nama)


CFG = Pengaturan(llm_timeout_groq=1.0, llm_timeout_gemini=1.0, llm_anggaran_total=3.0)


async def jalankan(transport, teks=TEKS, cfg=CFG):
    return await llm.analisis(teks, cfg, transport)


# --- urutan penyedia ---


async def test_groq_berhasil_gemini_tidak_dipanggil():
    t = TransportPalsu(groq=[balasan("Klaim satu", [{"id": "desakan_waktu", "kutipan": ["sebelum dihapus"]}])])
    h = await jalankan(t)
    assert h.penyedia == "groq" and h.klaim_utama == "Klaim satu" and h.percobaan == 1
    assert h.kandidat == [KandidatLLM("desakan_waktu", ["sebelum dihapus"])]
    assert t.jumlah("gemini") == 0


async def test_permintaan_memakai_model_kunci_dan_prompt_yang_benar():
    t = TransportPalsu(groq=[balasan()])
    await jalankan(t)
    nama, badan, kunci, _ = t.panggilan[0]
    assert kunci == KUNCI_GROQ and badan["model"] == "openai/gpt-oss-120b" and badan["temperature"] == 0
    assert badan["reasoning_effort"] == "low" and badan["response_format"]["type"] == "json_schema"
    sistem, pengguna = (m["content"] for m in badan["messages"])
    assert sistem == llm.prompt_sistem() and TEKS in pengguna


async def test_groq_gagal_pindah_ke_gemini_dengan_kunci_dan_model_gemini():
    t = TransportPalsu(groq=[(500, "galat")], gemini=[balasan("Klaim gemini")])
    h = await jalankan(t)
    assert h.penyedia == "gemini" and h.klaim_utama == "Klaim gemini"
    nama, badan, kunci, _ = t.panggilan[-1]
    assert nama == "gemini" and kunci == KUNCI_GEMINI and badan["model"] == "gemini-3.5-flash-lite"
    assert badan["reasoning_effort"] == "minimal"


@pytest.mark.parametrize("galat", [
    (429, "rate limit"), (500, "x"), (503, "x"), (401, "salah kunci"), (400, "bad request"),
    llm.GagalJaringan(), (200, "bukan json"), (200, json.dumps({"choices": []})),
    (200, json.dumps({"choices": [{"message": {"content": "{rusak"}}]})),
    balasan(klaim=None) if False else (200, json.dumps({"choices": [{"message": {"content": json.dumps({"x": 1})}}]})),
])
async def test_setiap_jenis_kegagalan_groq_berakhir_di_gemini(galat):
    t = TransportPalsu(groq=[galat], gemini=[balasan("dari gemini")])
    h = await jalankan(t)
    assert h.penyedia == "gemini" and h.klaim_utama == "dari gemini"
    assert t.jumlah("groq") == 1


async def test_semua_gagal_menghasilkan_none_bukan_galat():
    t = TransportPalsu(groq=[llm.GagalJaringan()], gemini=[llm.GagalJaringan()])
    assert await jalankan(t) is None


async def test_galat_tak_terduga_di_transport_menghasilkan_none():
    t = TransportPalsu(groq=[RuntimeError("meledak")], gemini=[ValueError("meledak")])
    assert await jalankan(t) is None


async def test_json_validate_failed_dicoba_ulang_sekali_di_groq_yang_sama():
    t = TransportPalsu(groq=[(400, '{"error":{"code":"json_validate_failed"}}'), balasan("setelah ulang")])
    h = await jalankan(t)
    assert h.penyedia == "groq" and h.klaim_utama == "setelah ulang" and h.percobaan == 2
    assert t.jumlah("groq") == 2 and t.jumlah("gemini") == 0


async def test_json_validate_failed_dua_kali_pindah_ke_gemini():
    gagal = (400, '{"error":{"code":"json_validate_failed"}}')
    t = TransportPalsu(groq=[gagal, gagal], gemini=[balasan("gemini")])
    h = await jalankan(t)
    assert h.penyedia == "gemini" and t.jumlah("groq") == 2


async def test_400_lain_tidak_dicoba_ulang():
    t = TransportPalsu(groq=[(400, "parameter tidak didukung")], gemini=[balasan("gemini")])
    await jalankan(t)
    assert t.jumlah("groq") == 1


# --- kunci dan sakelar ---


async def test_kunci_groq_kosong_dilewati_langsung_ke_gemini(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    t = TransportPalsu(gemini=[balasan("gemini")])
    h = await jalankan(t)
    assert h.penyedia == "gemini" and t.jumlah("groq") == 0


async def test_tanpa_kunci_sama_sekali_none_tanpa_panggilan(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    t = TransportPalsu()
    assert await jalankan(t) is None and t.panggilan == []


async def test_sakelar_mati_tidak_memanggil_apa_pun():
    t = TransportPalsu()
    assert await llm.analisis(TEKS, Pengaturan(llm_aktif=False), t) is None
    assert t.panggilan == []


def test_muat_kunci_dari_file_env_dan_prioritas_lingkungan(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# komentar\nGROQ_API_KEY="dari-file"\nGEMINI_API_KEY=gem-file\n', encoding="utf-8")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm.muat_kunci("GROQ_API_KEY", env) == "dari-file"
    assert llm.muat_kunci("GEMINI_API_KEY", env) == "gem-file"
    assert llm.muat_kunci("TIDAK_ADA", env) == ""
    monkeypatch.setenv("GROQ_API_KEY", "dari-env")
    assert llm.muat_kunci("GROQ_API_KEY", env) == "dari-env"
    assert llm.muat_kunci("GROQ_API_KEY", tmp_path / "tidak-ada") == "dari-env"


def test_ringkasan_status_tidak_memuat_kunci(monkeypatch):
    teks = llm.ringkasan_status(Pengaturan())
    assert KUNCI_GROQ not in teks and KUNCI_GEMINI not in teks and "groq" in teks and "gemini" in teks
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert "kunci cadangan belum diisi" in llm.ringkasan_status(Pengaturan())
    assert "dimatikan" in llm.ringkasan_status(Pengaturan(llm_aktif=False))


# --- batas waktu (B): wait_for di luar thread; thread yang tertinggal tidak menahan permintaan berikutnya ---


def lambat(detik: float):
    def _(timeout):
        time.sleep(detik)
        return balasan("terlambat")

    return _


async def test_transport_lambat_dipotong_batas_waktu_lalu_pindah_ke_gemini():
    t = TransportPalsu(groq=[lambat(2.0)], gemini=[balasan("gemini")])
    cfg = Pengaturan(llm_timeout_groq=0.4, llm_timeout_gemini=1.0, llm_anggaran_total=3.0)
    mulai = time.monotonic()
    h = await jalankan(t, cfg=cfg)
    lama = time.monotonic() - mulai
    assert h.penyedia == "gemini" and lama < 1.5  # tidak menunggu 2 detik


async def test_semua_penyedia_lambat_total_dibatasi_anggaran():
    t = TransportPalsu(groq=[lambat(3.0)], gemini=[lambat(3.0)])
    cfg = Pengaturan(llm_timeout_groq=0.5, llm_timeout_gemini=0.5, llm_anggaran_total=0.8)
    mulai = time.monotonic()
    assert await jalankan(t, cfg=cfg) is None
    assert time.monotonic() - mulai < 1.5


async def test_anggaran_total_membatasi_penyedia_kedua():
    t = TransportPalsu(groq=[lambat(3.0)], gemini=[balasan("gemini")])
    cfg = Pengaturan(llm_timeout_groq=0.6, llm_timeout_gemini=5.0, llm_anggaran_total=0.9)
    h = await jalankan(t, cfg=cfg)
    assert h is None  # sisa anggaran 0,3 detik < minimum; Gemini tidak dicoba
    assert t.jumlah("gemini") == 0


async def test_thread_tertinggal_tidak_menahan_permintaan_berikutnya():
    lambat_dulu = TransportPalsu(groq=[lambat(1.5)], gemini=[llm.GagalJaringan()])
    cfg = Pengaturan(llm_timeout_groq=0.3, llm_timeout_gemini=0.3, llm_anggaran_total=2.0)
    assert await jalankan(lambat_dulu, cfg=cfg) is None  # thread groq masih tidur ~1,2 detik lagi
    cepat = TransportPalsu(groq=[balasan("cepat")])
    mulai = time.monotonic()
    h = await jalankan(cepat, cfg=cfg)
    assert h.klaim_utama == "cepat" and time.monotonic() - mulai < 0.5


async def test_batas_soket_thread_sedikit_di_atas_batas_wait_for():
    t = TransportPalsu(groq=[balasan()])
    await jalankan(t, cfg=Pengaturan(llm_timeout_groq=2.0, llm_anggaran_total=9.0))
    assert 2.0 < t.panggilan[0][3] <= 3.5


# --- klaim kosong tidak dicoba ulang (Sesi 5.5: hemat kuota; orkestrator memakai klaim cadangan) ---


async def test_klaim_kosong_tidak_dicoba_ulang_dan_ciri_tetap_dipakai():
    t = TransportPalsu(groq=[balasan("", [{"id": "desakan_waktu", "kutipan": ["sebelum dihapus"]}])])
    h = await jalankan(t)
    assert h.penyedia == "groq" and h.klaim_utama == "" and len(h.kandidat) == 1
    assert t.jumlah("groq") == 1 and t.jumlah("gemini") == 0


# --- max_tokens dan finish_reason ---


def test_batas_token_keluaran_1000_dan_dipakai_di_badan_permintaan():
    assert Pengaturan().llm_maks_token == 1000
    assert llm._badan(llm.GROQ, "teks", Pengaturan())["max_tokens"] == 1000


def balasan_terpotong():
    isi = json.dumps({"klaim_utama": "Klaim yang terpot", "ciri": []})
    badan = {"choices": [{"message": {"content": isi}, "finish_reason": "length"}], "usage": {"prompt_tokens": 900, "completion_tokens": 1000}}
    return 200, json.dumps(badan)


async def test_finish_reason_length_gagal_di_jejak_lalu_pindah_penyedia():
    t = TransportPalsu(groq=[balasan_terpotong()], gemini=[balasan("Klaim utuh", [])])
    jejak: list = []
    h = await llm.analisis(TEKS, CFG, t, jejak=jejak)
    assert h.penyedia == "gemini" and h.klaim_utama == "Klaim utuh"
    assert jejak[0]["penyedia"] == "groq" and jejak[0]["status"] == "terpotong"
    assert jejak[0]["token"] == {"prompt": 900, "completion": 1000}
    assert t.jumlah("groq") == 1  # tidak diulang: hasilnya akan sama


async def test_finish_reason_length_dengan_cadangan_mati_hasilnya_none():
    t = TransportPalsu(groq=[balasan_terpotong()])
    cfg = Pengaturan(llm_timeout_groq=1.0, llm_anggaran_total=3.0, llm_cadangan_aktif=False)
    assert await llm.analisis(TEKS, cfg, t) is None


async def test_finish_reason_stop_diterima_normal():
    isi = json.dumps({"klaim_utama": "Klaim", "ciri": []})
    badan = {"choices": [{"message": {"content": isi}, "finish_reason": "stop"}]}
    t = TransportPalsu(groq=[(200, json.dumps(badan))])
    assert (await llm.analisis(TEKS, CFG, t)).klaim_utama == "Klaim"


# --- klaim dengan kata ganti kedua ditolak ---


def test_klaim_llm_dengan_kata_ganti_kedua_tidak_dapat_dipakai():
    teks = "Akun Facebook akan dinonaktifkan secara permanen kecuali melakukan verifikasi melalui tautan"
    assert llm.klaim_dapat_dipakai("Akun Facebook akan dinonaktifkan secara permanen kecuali verifikasi", teks)
    assert not llm.klaim_dapat_dipakai("Akun Facebook Anda akan dinonaktifkan secara permanen kecuali verifikasi", teks)
    assert not llm.klaim_dapat_dipakai("Akun Facebook kamu akan dinonaktifkan secara permanen", teks)


# --- pengurai balasan ---


def test_id_tidak_dikenal_pernah_dibantah_dan_duplikat_dibuang():
    konten = json.dumps({"klaim_utama": " k ", "ciri": [
        {"id": "ciri_ngawur", "kutipan": ["a"]},
        {"id": "pernah_dibantah", "kutipan": ["b"]},
        {"id": "desakan_waktu", "kutipan": ["c", " ", "d"]},
        {"id": "desakan_waktu", "kutipan": ["e"]},
        {"id": "ajakan_menyebarkan", "kutipan": ["1", "2", "3", "4", "5"]},
        {"id": "judul_clickbait", "kutipan": []},
        "bukan objek",
        {"id": 5, "kutipan": ["x"]},
    ]})
    klaim, kandidat = llm.urai_balasan(konten)
    assert klaim == "k"
    assert kandidat == [KandidatLLM("desakan_waktu", ["c", "d"]), KandidatLLM("ajakan_menyebarkan", ["1", "2", "3"])]


@pytest.mark.parametrize("konten", ["", "bukan json", "[]", '{"klaim_utama": 1, "ciri": []}', '{"klaim_utama": "x"}',
                                    '{"klaim_utama": "x", "ciri": "salah"}'])
def test_balasan_tidak_sah_ditolak(konten):
    assert llm.urai_balasan(konten) is None


def test_pagar_kode_json_dibuang():
    klaim, kandidat = llm.urai_balasan('```json\n{"klaim_utama": "ok", "ciri": []}\n```')
    assert klaim == "ok" and kandidat == []


# --- privasi log ---


async def test_log_hanya_memuat_penyedia_status_dan_durasi(caplog):
    caplog.set_level(logging.DEBUG)
    t = TransportPalsu(groq=[(500, "ISI-GALAT-RAHASIA")], gemini=[balasan("KLAIM-RAHASIA", [{"id": "desakan_waktu", "kutipan": ["sebelum dihapus"]}])])
    await jalankan(t)
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "groq" in log and "status=500" in log and "status=200" in log and "gemini" in log
    for rahasia in (KUNCI_GROQ, KUNCI_GEMINI, "RAHASIA-ISI-TEKS", "KLAIM-RAHASIA", "ISI-GALAT-RAHASIA", "sebelum dihapus",
                    "Kamu adalah pengekstrak", "klaim_utama"):
        assert rahasia not in log


async def test_log_galat_tak_terduga_hanya_jenisnya(caplog):
    caplog.set_level(logging.DEBUG)
    t = TransportPalsu(groq=[RuntimeError(f"kunci {KUNCI_GROQ} bocor")], gemini=[llm.GagalJaringan()])
    await jalankan(t)
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "RuntimeError" in log and KUNCI_GROQ not in log


def test_transport_urllib_tidak_membawa_pesan_asli_saat_gagal(monkeypatch):
    def meledak(*a, **k):
        raise OSError(f"koneksi ke host gagal dengan kunci {KUNCI_GROQ}")

    monkeypatch.setattr(llm.urllib.request, "urlopen", meledak)
    with pytest.raises(llm.GagalJaringan) as e:
        llm.transport_urllib(llm.GROQ, {}, KUNCI_GROQ, 1.0)
    assert KUNCI_GROQ not in str(e.value) and e.value.__cause__ is None


# --- paritas prompt dengan alat ukur ---


def test_prompt_sama_persis_dengan_alat_ukur_llm():
    jalur = Path(__file__).resolve().parents[1] / "alat" / "ukur_llm" / "prompt.py"
    spec = importlib.util.spec_from_file_location("prompt_alat_ukur_llm", jalur)
    alat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alat)
    assert llm.prompt_sistem() == alat.prompt_sistem()
    assert llm.pesan_pengguna("abc") == alat.pesan_pengguna("abc")
    assert llm.skema_json() == alat.skema_json()
    assert alat.id_untuk_llm() == tuple(llm.PENJELASAN_CIRI)


def test_prompt_menawarkan_delapan_id_tanpa_pernah_dibantah():
    sistem = llm.prompt_sistem()
    assert len(llm.PENJELASAN_CIRI) == 8 and "pernah_dibantah" not in sistem
    assert "permintaan_data_rahasia" in sistem


# --- pemeriksaan kutipan dan klaim ---

ASLI = "Hubungi +62 812-3456-7890 segera. Segera kirim kode OTP sebelum dihapus."


def test_petakan_kandidat_menolak_kutipan_palsu_dan_membuka_token_penyamaran():
    from app.pipeline.samarkan import samarkan

    samar = samarkan(ASLI)
    kandidat = [
        KandidatLLM("permintaan_data_rahasia", ["Segera kirim kode OTP", "minta transfer seratus juta"]),
        KandidatLLM("desakan_waktu", ["Hubungi [NOMOR] segera"]),
        KandidatLLM("judul_clickbait", ["tidak ada di teks"]),
    ]
    sah, ditolak = llm.petakan_kandidat(kandidat, samar, ASLI)
    assert ditolak == 2
    assert sah == [
        KandidatLLM("permintaan_data_rahasia", ["Segera kirim kode OTP"]),
        KandidatLLM("desakan_waktu", ["Hubungi +62 812-3456-7890 segera"]),
    ]


def test_kesetiaan_klaim_dihitung_dari_kata_isi_yang_ada_di_teks():
    teks = "PDIP USUL KE PEMERINTAH AGAR PESANTREN DI TUTUP SELURUH INDONESIA"
    assert llm.kesetiaan_klaim("PDIP mengusulkan pemerintah menutup pesantren", teks) >= 0.5
    assert llm.kesetiaan_klaim("Presiden mengumumkan kenaikan harga beras nasional", teks) == 0.0
    assert llm.kesetiaan_klaim("", teks) == 0.0
    assert llm.kesetiaan_klaim("pemerintahagar pesantren", "pemerintahagar pesantren ditutup") == 1.0  # kata menempel


def test_klaim_dengan_kata_penilaian_di_luar_teks_ditolak_walau_setia():
    teks = "Vaksin cacar air menyebabkan epidemi shingles yang lebih mematikan"
    cfg = Pengaturan()
    assert llm.klaim_dapat_dipakai("Vaksin cacar air menyebabkan epidemi shingles", teks, cfg) is True
    assert llm.klaim_dapat_dipakai("Ini fakta: vaksin cacar air menyebabkan epidemi shingles", teks, cfg) is False
    assert llm.klaim_dapat_dipakai("Terdapat modus penipuan: vaksin cacar air menyebabkan epidemi", teks, cfg) is False
    # kata penilaian yang memang ada di teks boleh dipakai
    assert llm.klaim_dapat_dipakai("Pesan menyebut penipuan lewat inbox", "Waspada penipuan lewat inbox", cfg) is True


def test_klaim_tidak_dipakai_bila_kosong_tidak_setia_atau_memuat_token_penyamaran():
    teks = "PDIP usul pemerintah tutup pesantren seluruh Indonesia"
    cfg = Pengaturan()
    assert llm.klaim_dapat_dipakai("", teks, cfg) is False
    assert llm.klaim_dapat_dipakai("Wakil Menteri Keuangan terlibat korupsi besar", teks, cfg) is False
    assert llm.klaim_dapat_dipakai("PDIP usul pemerintah tutup pesantren, hubungi [NOMOR]", teks + " [NOMOR]", cfg) is False


def test_ambang_kesetiaan_dari_konfigurasi():
    teks = "kata satu kata dua kata tiga empat"
    klaim = "kata satu muncul baru"
    assert llm.klaim_dapat_dipakai(klaim, teks, Pengaturan(klaim_kesetiaan_minimum=0.5)) is True
    assert llm.klaim_dapat_dipakai(klaim, teks, Pengaturan(klaim_kesetiaan_minimum=0.9)) is False


# --- diagnostik percobaan (Sesi 5.5) ---


def test_kode_galat_hanya_mengambil_kode_dan_tipe():
    body = json.dumps({"error": {"message": "teks rahasia pengguna", "type": "invalid_request_error", "code": "json_validate_failed"}})
    assert llm.kode_galat(body) == "json_validate_failed/invalid_request_error"
    assert llm.kode_galat("error code: 1010") == "cf_1010"
    assert llm.kode_galat("<html>bukan json</html>") is None
    assert llm.kode_galat(json.dumps({"error": {"code": "kalimat panjang dengan spasi"}})) is None
    assert llm.kode_galat("") is None


async def test_jejak_mencatat_tiap_percobaan_tanpa_isi():
    t = TransportPalsu(groq=[(403, "error code: 1010")], gemini=[balasan("Klaim", [])])
    jejak: list = []
    h = await llm.analisis(TEKS, CFG, t, jejak=jejak)
    assert h.penyedia == "gemini"
    assert [(j["penyedia"], j["status"], j["kode"]) for j in jejak] == [("groq", 403, "cf_1010"), ("gemini", 200, None)]
    assert all(set(j) == {"penyedia", "status", "ms", "kode", "token", "tunggu", "kuota"} for j in jejak)


# --- User-Agent eksplisit dan sakelar cadangan (Sesi 5.5) ---


@pytest.mark.parametrize("penyedia", [llm.GROQ, llm.GEMINI])
def test_setiap_permintaan_membawa_user_agent_cekhoaks(monkeypatch, penyedia):
    dilihat = {}

    class Balasan:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def tangkap(permintaan, timeout):
        dilihat["ua"] = permintaan.get_header("User-agent")
        return Balasan()

    monkeypatch.setattr(llm.urllib.request, "urlopen", tangkap)
    llm.transport_urllib(penyedia, {}, "kunci", 1.0)
    assert dilihat["ua"] == llm.USER_AGENT == f"CekHoaks/{VERSI_SERVER}"
    assert not dilihat["ua"].startswith("Python-urllib")


async def test_cf_1010_tercatat_di_jejak_lalu_pindah_ke_gemini():
    t = TransportPalsu(groq=[(403, "error code: 1010")], gemini=[balasan("Klaim", [])])
    jejak: list = []
    h = await llm.analisis(TEKS, CFG, t, jejak=jejak)
    assert h.penyedia == "gemini" and jejak[0]["kode"] == "cf_1010" and jejak[0]["status"] == 403


async def test_cadangan_dimatikan_groq_gagal_hasilnya_none_tanpa_memanggil_gemini():
    t = TransportPalsu(groq=[(500, "")])
    cfg = Pengaturan(llm_timeout_groq=1.0, llm_timeout_gemini=1.0, llm_anggaran_total=3.0, llm_cadangan_aktif=False)
    assert await llm.analisis(TEKS, cfg, t) is None
    assert t.jumlah("groq") == 1 and t.jumlah("gemini") == 0


async def test_cadangan_dimatikan_groq_berhasil_tetap_dipakai():
    t = TransportPalsu(groq=[balasan("Klaim", [])])
    cfg = Pengaturan(llm_timeout_groq=1.0, llm_anggaran_total=3.0, llm_cadangan_aktif=False)
    assert (await llm.analisis(TEKS, cfg, t)).penyedia == "groq"


def test_banner_cadangan_dimatikan():
    assert llm.ringkasan_status(Pengaturan(llm_cadangan_aktif=False)) == "groq saja (cadangan dimatikan)"


def test_sakelar_cadangan_dari_lingkungan():
    from app.konfigurasi import KonfigurasiTidakValid, muat

    assert muat({}).llm_cadangan_aktif is True
    assert muat({"CEKHOAKS_LLM_CADANGAN": "mati"}).llm_cadangan_aktif is False
    with pytest.raises(KonfigurasiTidakValid):
        muat({"CEKHOAKS_LLM_CADANGAN": "nonaktif"})


# --- token dan penanganan 429 (Sesi 5.5) ---


def balasan_token(klaim="Klaim", ciri=None, prompt=900, completion=200, penalaran=120):
    status, isi = balasan(klaim, ciri)
    badan = json.loads(isi)
    badan["usage"] = {
        "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion,
        "completion_tokens_details": {"reasoning_tokens": penalaran},
    }
    return status, json.dumps(badan)


def galat_429(tunggu="1", kuota=True):
    pesan = "Rate limit reached ... Limit 8000, Used 7200, Requested 1100. Please try again in 6.5s." if kuota else "x"
    isi = json.dumps({"error": {"message": pesan, "type": "tokens", "code": "rate_limit_exceeded"}})
    return 429, isi, {"retry-after": tunggu}


CFG_9 = Pengaturan(llm_timeout_groq=2.0, llm_timeout_gemini=2.0, llm_anggaran_total=9.0, llm_tunggu_429_maks=3.0)


async def test_token_dicatat_di_jejak_tanpa_isi():
    t = TransportPalsu(groq=[balasan_token()])
    jejak: list = []
    await llm.analisis(TEKS, CFG, t, jejak=jejak)
    assert jejak[0]["token"] == {"prompt": 900, "completion": 200, "penalaran": 120}


def test_penggunaan_token_dan_waktu_tunggu_dan_kuota():
    assert llm.penggunaan_token("bukan json") is None
    assert llm.penggunaan_token(json.dumps({"choices": []})) is None
    assert llm._durasi_detik("2m59.5s") == pytest.approx(179.5)
    assert llm._durasi_detik("50ms") == pytest.approx(0.05)
    assert llm._durasi_detik("kata") is None
    assert llm.waktu_tunggu({"retry-after": "7"}, "") == 7
    assert llm.waktu_tunggu({}, "... Please try again in 1m2.5s. ...") == pytest.approx(62.5)
    assert llm.waktu_tunggu({"x-ratelimit-reset-tokens": "3.2s"}, "") == pytest.approx(3.2)
    assert llm.waktu_tunggu({}, "tanpa petunjuk") is None
    assert llm.kuota_dari_galat("Limit 8000, Used 7200, Requested 1100") == {"batas": 8000, "terpakai": 7200, "diminta": 1100}


async def test_429_tunggu_pendek_menunggu_lalu_groq_dicoba_lagi(monkeypatch):
    tidur = []

    async def tidur_palsu(d):
        tidur.append(d)

    monkeypatch.setattr(llm.asyncio, "sleep", tidur_palsu)
    t = TransportPalsu(groq=[galat_429("1"), balasan("Klaim", [])])
    jejak: list = []
    h = await llm.analisis(TEKS, CFG_9, t, jejak=jejak)
    assert h.penyedia == "groq" and t.jumlah("groq") == 2 and t.jumlah("gemini") == 0
    assert tidur and 1.0 <= tidur[0] < 1.5
    assert jejak[0]["status"] == 429 and jejak[0]["kode"] == "rate_limit_exceeded/tokens" and jejak[0]["tunggu"] == 1
    assert jejak[0]["kuota"] == {"batas": 8000, "terpakai": 7200, "diminta": 1100}


async def test_429_tunggu_terlalu_lama_langsung_pindah_ke_gemini():
    t = TransportPalsu(groq=[galat_429("30")], gemini=[balasan("Klaim", [])])
    h = await llm.analisis(TEKS, CFG_9, t)
    assert h.penyedia == "gemini" and t.jumlah("groq") == 1


async def test_429_berulang_hanya_sekali_menunggu(monkeypatch):
    async def tidur_palsu(d):
        pass

    monkeypatch.setattr(llm.asyncio, "sleep", tidur_palsu)
    t = TransportPalsu(groq=[galat_429("1"), galat_429("1")], gemini=[balasan("Klaim", [])])
    h = await llm.analisis(TEKS, CFG_9, t)
    assert h.penyedia == "gemini" and t.jumlah("groq") == 2


async def test_429_tanpa_petunjuk_waktu_langsung_pindah():
    t = TransportPalsu(groq=[(429, "{}", {})], gemini=[balasan("Klaim", [])])
    h = await llm.analisis(TEKS, CFG_9, t)
    assert h.penyedia == "gemini" and t.jumlah("groq") == 1
