"""Menguji pipeline dari terminal: python -m app.cek PATH_GAMBAR

Menjalankan pipeline yang sama dengan endpoint /analisis dan mencetak JSON dengan format respons
API (termasuk format galat seragam): RapidOCR, pembersihan, ciri regex, klaim heuristik, dan pencarian cek fakta.
Teks mentah, teks bersih, baris yang dibuang, ciri, dan kandidat artikel dicetak ke stderr. Tanpa jeda buatan.
Menghormati PAKSA_TINGKAT.
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
from .pipeline import ciri, cocok, klaim, orkestrator, template
from .pipeline.tipe import Konteks


async def _tidak_putus() -> bool:
    return False


def cetak_diagnostik(diagnostik: dict) -> None:
    """Hasil antara untuk developer, ke stderr supaya stdout tetap JSON murni.

    Ciri regex, klaim heuristik, dan penjelasan template dihitung di sini dari teks bersih untuk dibandingkan
    dengan hasil akhir di JSON (yang memakai penggabungan yang sama)."""
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

    kandidat = diagnostik.get("kandidat")
    if kandidat is not None:
        print(f"\n=== Kandidat cek fakta, pencarian {cocok.pencarian.ringkasan()} ({len(kandidat)}) ===", file=keluar)
        for k in kandidat:
            lama = "  (URL format lama)" if k.url_format_lama else ""
            print(f"{k.skor:.3f} | {k.label:<14s} | {k.sumber} | {k.tanggal or '-'}{lama}", file=keluar)
            print(f"    {k.judul}", file=keluar)
    info_llm = diagnostik.get("llm")
    if info_llm is not None:
        print("\n=== LLM ===", file=keluar)
        for j in info_llm.get("jejak") or []:
            kode = f", kode {j['kode']}" if j.get("kode") else ""
            tok = j.get("token") or {}
            token = f", token {tok.get('prompt', '-')}/{tok.get('completion', '-')}" if tok else ""
            tunggu = f", tunggu {j['tunggu']:.1f} dtk" if j.get("tunggu") is not None else ""
            kuota = j.get("kuota")
            ket_kuota = f", kuota batas {kuota['batas']} terpakai {kuota['terpakai']} diminta {kuota['diminta']}" if kuota else ""
            print(f"percobaan {j['penyedia']}: status {j['status']}, {j['ms']} ms{kode}{token}{tunggu}{ket_kuota}", file=keluar)
        if info_llm.get("penyedia") is None:
            print("tidak dipakai (dimatikan, kunci kosong, atau semua penyedia gagal): ciri hanya dari regex", file=keluar)
        else:
            print(
                f"penyedia {info_llm['penyedia']}, {info_llm['durasi_ms']} ms, percobaan {info_llm['percobaan']}, "
                f"kutipan ditolak {info_llm['kutipan_ditolak']}", file=keluar,
            )
            print(f"klaim LLM: {info_llm['klaim'] or '(kosong)'}", file=keluar)
            print(
                f"kesetiaan {info_llm['kesetiaan']:.2f}, klaim dipakai: {'ya' if info_llm['klaim_dipakai'] else 'tidak'}",
                file=keluar,
            )
            for k in info_llm["kandidat"]:
                print(f"kandidat {k.id}: {' | '.join(k.kutipan)}", file=keluar)
    if "klaim_sumber" in diagnostik:
        print(
            f"\n=== Klaim utama final: sumber {diagnostik['klaim_sumber']}; kandidat heuristik gugur karena "
            f"kata ganti kedua, orang pertama, atau sapaan: {diagnostik.get('klaim_gugur_percakapan', 0)} ===", file=keluar,
        )
    dibuang = diagnostik.get("ciri_dibuang")
    if dibuang:
        print(f"\n=== Bukti dan ciri yang dibuang ({len(dibuang)}) ===", file=keluar)
        for d in dibuang:
            print(f"{d['id']} [{d['alasan']}]: {d['bukti']}", file=keluar)
    putusan = diagnostik.get("putusan")
    if putusan is not None:
        print(f"\n=== Putusan: {putusan.tingkat.value}, varian: {putusan.varian or '-'} ===", file=keluar)
    print(file=keluar)


async def _siapkan_dan_analisis(data: bytes, paksa: str | None, diagnostik: dict) -> dict:
    """Memuat pencarian (pembaca teks dimuat lazy saat dipakai), lalu menganalisis."""
    if konfigurasi.pengaturan.paksa_tingkat != konfigurasi.PAKSA_TEKS_TIDAK_TERBACA:
        print("Memuat pencarian cek fakta ...", file=sys.stderr, flush=True)
        await cocok.pencarian.siapkan()
    return await analisis_gambar(data, paksa, diagnostik)


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
    hasil = asyncio.run(_siapkan_dan_analisis(data, konfigurasi.pengaturan.paksa_tingkat, diagnostik))
    cetak_diagnostik(diagnostik)
    print(json.dumps(hasil, ensure_ascii=False, indent=2))
    return 1 if "galat" in hasil else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
