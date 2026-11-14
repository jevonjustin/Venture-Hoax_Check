"""Bagian bersama alat unggah Hugging Face (Sesi 8.1). Dijalankan developer dari .venv server.

Token dibaca dari variabel lingkungan HF_TOKEN di jendela developer dan tidak pernah dicetak.
"""

import os
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

AKUN = "jevonjustin"
DATASET = f"{AKUN}/veritas-data"
SPACE = f"{AKUN}/veritas"

# Bagian jalur yang tidak boleh pernah ikut terunggah ke Space (pengaman tambahan selain daftar berkas eksplisit).
BAGIAN_TERLARANG = {".env", "data_lokal", "data_hf", "tests", ".venv", "alat", "__pycache__", ".pytest_cache"}


def ukuran(byte: int) -> str:
    for satuan, besar in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if byte >= besar:
            return f"{byte / besar:,.1f} {satuan}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{byte} B"


def cetak_daftar(berkas: list[tuple[str, Path]]) -> int:
    total = 0
    lebar = max(len(tujuan) for tujuan, _ in berkas)
    for tujuan, sumber in berkas:
        besar = sumber.stat().st_size
        total += besar
        print(f"  {tujuan:<{lebar}}  {ukuran(besar):>10}")
    print(f"  {'Total':<{lebar}}  {ukuran(total):>10}  ({len(berkas)} berkas)")
    return total


def ambil_token() -> str:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        print(
            "HF_TOKEN belum diisi di jendela ini. Isi dulu, lalu jalankan lagi:\n"
            '  $env:HF_TOKEN = Read-Host "Token HF"',
            file=sys.stderr,
        )
        sys.exit(2)
    return token


def konfirmasi(pertanyaan: str, ya: bool) -> None:
    if ya:
        return
    jawab = input(f"{pertanyaan} Ketik y untuk lanjut: ").strip().lower()
    if jawab not in ("y", "ya"):
        print("Dibatalkan, tidak ada yang diunggah.")
        sys.exit(1)


def masuk(api) -> str:
    """Nama akun pemilik token; menolak jalan bila bukan akun tujuan."""
    nama = api.whoami()["name"]
    print(f"Masuk sebagai: {nama}")
    if nama != AKUN:
        print(f"Token ini milik {nama}, bukan {AKUN}. Dibatalkan.", file=sys.stderr)
        sys.exit(3)
    return nama
