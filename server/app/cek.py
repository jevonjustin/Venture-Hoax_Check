"""Menguji pipeline dari terminal: python -m app.cek PATH_GAMBAR

Menjalankan pipeline yang sama dengan endpoint /analisis dan mencetak JSON dengan format respons
API (termasuk format galat seragam). Tanpa jeda buatan. Menghormati PAKSA_TINGKAT.
Gambar hanya dibaca dari disk, tidak ada yang ditulis.

Kode keluar: 0 sukses, 1 galat API, 2 berkas tidak bisa dibaca.
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

from .galat import DibatalkanKlien, GalatApi
from . import konfigurasi
from .pipeline import orkestrator
from .pipeline.tipe import Konteks


async def _tidak_putus() -> bool:
    return False


async def analisis_gambar(data: bytes, paksa: str | None) -> dict:
    """Mengembalikan dict sesuai format respons API, sukses maupun galat."""
    ctx = Konteks(id_permintaan=uuid.uuid4().hex, jeda_detik=(0.0, 0.0), klien_putus=_tidak_putus, paksa=paksa)
    try:
        return (await orkestrator.jalankan(data, ctx)).model_dump(mode="json")
    except GalatApi as e:
        return e.ke_respons().model_dump(mode="json")
    except DibatalkanKlien:  # tidak mungkin terjadi: klien_putus selalu False
        raise AssertionError("app.cek tidak punya klien yang bisa putus") from None


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # PowerShell 5.1 bawaannya bukan UTF-8
    if len(argv) != 1:
        print("Pemakaian: python -m app.cek PATH_GAMBAR", file=sys.stderr)
        return 2
    try:
        data = Path(argv[0]).read_bytes()
    except OSError as e:
        print(f"Berkas tidak bisa dibaca: {e}", file=sys.stderr)
        return 2
    if konfigurasi.kesalahan:
        print(f"Pengaturan tidak sah:\n  {konfigurasi.kesalahan}", file=sys.stderr)
        return 1

    hasil = asyncio.run(analisis_gambar(data, konfigurasi.pengaturan.paksa_tingkat))
    print(json.dumps(hasil, ensure_ascii=False, indent=2))
    return 1 if "galat" in hasil else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
