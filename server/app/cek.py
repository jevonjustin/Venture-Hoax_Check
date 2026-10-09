"""Menguji pipeline dari terminal: python -m app.cek PATH_GAMBAR

Menjalankan pipeline yang sama dengan endpoint /analisis dan mencetak JSON dengan format respons
API (termasuk format galat seragam). Membaca teks sungguhan (RapidOCR) dan membersihkannya; tahap lain masih dummy. Teks mentah, teks bersih, dan baris yang dibuang dicetak ke stderr. Tanpa jeda buatan. Menghormati PAKSA_TINGKAT.
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
from .pipeline import ciri, klaim, orkestrator, template
from .pipeline.tipe import Konteks


async def _tidak_putus() -> bool:
    return False


def cetak_diagnostik(diagnostik: dict) -> None:
    """Hasil antara untuk developer, ke stderr supaya stdout tetap JSON murni.

    Ciri regex, klaim heuristik, dan penjelasan template dihitung di sini dari teks bersih; /analisis belum
    memakainya (dipasang di Sesi 5.5)."""
    if "mentah" not in diagnostik:
        return
    keluar = sys.stderr
    print("=== Teks mentah ===", file=keluar)
    print(diagnostik["mentah"], file=keluar)
    bersih = diagnostik.get("bersih")
    if bersih is None:
        print("\n(pembersihan gagal; teks mentah dipakai)", file=keluar)
        teks_bersih = diagnostik["mentah"]
    else:
        teks_bersih = bersih.teks
        print("\n=== Teks bersih ===", file=keluar)
        print(bersih.teks, file=keluar)
        print(f"\n=== Baris dibuang ({len(bersih.dibuang)}) ===", file=keluar)
        for b in bersih.dibuang:
            print(f"[{b.alasan}] {b.teks}", file=keluar)

    hasil_regex = ciri.deteksi_regex(teks_bersih)
    print(f"\n=== Ciri regex ({len(hasil_regex)}) ===", file=keluar)
    for c in hasil_regex:
        print(f"{c.id} [pola {c.kekuatan}]", file=keluar)
        for b in c.bukti:
            print(f"    bukti: {b}", file=keluar)
    final = ciri.gabung_ciri(hasil_regex, None, teks_bersih)
    print(f"\n=== Ciri dan penjelasan template, LLM tidak dipakai ({len(final)}) ===", file=keluar)
    for c in template.susun_penjelasan(final):
        print(f"{c.nama} (keyakinan {c.keyakinan}): {c.penjelasan}", file=keluar)
    klaim_utama = klaim.klaim_heuristik(teks_bersih, [b for c in hasil_regex for b in c.bukti])
    print("\n=== Klaim utama (heuristik) ===", file=keluar)
    print(klaim_utama or "(tidak ada pernyataan yang layak)", file=keluar)
    print(file=keluar)


async def analisis_gambar(data: bytes, paksa: str | None, diagnostik: dict | None = None) -> dict:
    """Mengembalikan dict sesuai format respons API, sukses maupun galat."""
    ctx = Konteks(
        id_permintaan=uuid.uuid4().hex, jeda_detik=(0.0, 0.0), klien_putus=_tidak_putus, paksa=paksa,
        diagnostik=diagnostik,
    )
    try:
        return (await orkestrator.jalankan(data, ctx)).model_dump(mode="json")
    except GalatApi as e:
        return e.ke_respons().model_dump(mode="json")
    except DibatalkanKlien:  # tidak mungkin terjadi: klien_putus selalu False
        raise AssertionError("app.cek tidak punya klien yang bisa putus") from None


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # PowerShell 5.1 bawaannya bukan UTF-8
    sys.stderr.reconfigure(encoding="utf-8")
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

    if konfigurasi.pengaturan.paksa_tingkat != konfigurasi.PAKSA_TEKS_TIDAK_TERBACA:
        print("Memuat pembaca teks dan membaca gambar ...", file=sys.stderr, flush=True)
    diagnostik: dict = {}
    hasil = asyncio.run(analisis_gambar(data, konfigurasi.pengaturan.paksa_tingkat, diagnostik))
    cetak_diagnostik(diagnostik)
    print(json.dumps(hasil, ensure_ascii=False, indent=2))
    return 1 if "galat" in hasil else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
