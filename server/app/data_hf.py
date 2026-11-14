"""Pengunduhan data pencarian dari dataset Hugging Face saat server menyala (Sesi 8.1, server di Spaces).

Hanya berjalan bila CEKHOAKS_HF_DATASET diisi. Isi dataset mengikuti susunan server/data_lokal:
`cek_fakta/...` dan `model/...`, dan yang diunduh hanya berkas yang dibaca pencarian (cocok.berkas_dibaca).
Setelah berhasil, cek_fakta_folder dan model_folder diarahkan ke folder unduhan sebelum pencarian dimuat.
Tanpa variabel itu perilaku lokal tidak berubah.

Token dibaca dari variabel lingkungan HF_TOKEN (Secret Space) dan tidak pernah dicetak, termasuk di pesan galat.
huggingface_hub diimpor di dalam fungsi: hanya jalur Spaces yang membutuhkannya (requirements-space.txt).
"""

import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .konfigurasi import Pengaturan
from .pipeline import cocok

log = logging.getLogger("uvicorn.error").getChild("cekhoaks")

# Pengganti snapshot_download untuk uji (tanpa jaringan). Argumen kata kunci sama dengan huggingface_hub.
Pengunduh = Callable[..., object]


@dataclass(frozen=True)
class HasilUnduh:
    berhasil: bool
    alasan: str = ""  # untuk banner dan status pencarian; tidak pernah memuat token
    detik: float = 0.0


def pola_berkas(cfg: Pengaturan) -> list[str]:
    """Jalur berkas di dataset (garis miring "/"), dipakai sebagai allow_patterns."""
    return [f"{folder}/{nama}" for folder, daftar in cocok.berkas_dibaca(cfg).items() for nama in daftar]


def _snapshot_download(**kwargs):
    from huggingface_hub import snapshot_download

    return snapshot_download(**kwargs)


def _tanpa_token(pesan: str, token: str) -> str:
    return pesan.replace(token, "***") if token else pesan


def siapkan(cfg: Pengaturan, env: Mapping[str, str] = os.environ, unduh: Pengunduh | None = None) -> HasilUnduh | None:
    """Mengunduh dataset bila cfg.hf_dataset diisi, lalu mengarahkan folder data di `cfg`.

    None bila tidak ada yang perlu dilakukan (variabel kosong atau cek fakta dimatikan). Tidak pernah melempar:
    kegagalan dikembalikan sebagai HasilUnduh(berhasil=False) dan folder data tidak diubah."""
    if not cfg.hf_dataset or not cfg.cek_fakta_aktif:
        return None
    token = env.get("HF_TOKEN", "").strip()
    pola = pola_berkas(cfg)
    mulai = time.perf_counter()
    try:
        (unduh or _snapshot_download)(
            repo_id=cfg.hf_dataset, repo_type="dataset", local_dir=str(cfg.hf_folder),
            allow_patterns=pola, token=token or None,
        )
    except ImportError:
        return HasilUnduh(False, "paket huggingface_hub belum terpasang (requirements-space.txt)")
    except Exception as e:
        pesan = _tanpa_token(str(e).strip().splitlines()[0] if str(e).strip() else "", token)
        petunjuk = "" if token else "; HF_TOKEN kosong (isi Secret HF_TOKEN di Settings Space)"
        return HasilUnduh(False, f"unduhan dataset {cfg.hf_dataset} gagal ({type(e).__name__}: {pesan[:200]}){petunjuk}")
    hilang = [p for p in pola if not (cfg.hf_folder / p).is_file()]
    if hilang:
        return HasilUnduh(False, f"dataset {cfg.hf_dataset} tidak memuat: {', '.join(hilang)}")
    cfg.cek_fakta_folder = cfg.hf_folder / "cek_fakta"
    cfg.model_folder = cfg.hf_folder / "model"
    return HasilUnduh(True, detik=time.perf_counter() - mulai)


def siapkan_atau_tandai(cfg: Pengaturan, env: Mapping[str, str] = os.environ, unduh: Pengunduh | None = None) -> HasilUnduh | None:
    """`siapkan`, lalu bila gagal: catat ke log dan tandai pencarian tidak tersedia (server tetap menyala)."""
    hasil = siapkan(cfg, env, unduh)
    if hasil is not None and not hasil.berhasil:
        log.error("Data pencarian tidak disiapkan: %s. Server jalan tanpa cek fakta.", hasil.alasan)
        cocok.pencarian.tandai_tidak_tersedia(hasil.alasan)
    return hasil
