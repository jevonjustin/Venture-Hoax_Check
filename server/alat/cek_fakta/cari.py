"""Mencari artikel cek fakta yang mirip dari terminal: kalimat atau gambar (dibaca dengan RapidOCR seperti di server).

Contoh:
  python cari.py "Air keran Jakarta mengandung zat berbahaya"
  python cari.py --gambar C:\\path\\ke\\gambar.png
"""

import argparse
import re
import sys
from pathlib import Path

from skema import FOLDER_DB


def baca_gambar(jalur: Path) -> str:
    """Pembacaan sama dengan server/app/pipeline/baca.py: RapidOCR bawaan, larik BGR, baris digabung dengan newline."""
    import numpy as np
    from PIL import Image
    from rapidocr import RapidOCR

    mesin = RapidOCR(params={"Global.log_level": "warning"})
    with Image.open(jalur) as g:
        larik = np.array(g.convert("RGB"))[:, :, ::-1]
    hasil = mesin(larik)
    return "\n".join(hasil.txts) if hasil.txts else ""


def rapikan_kueri(teks: str) -> str:
    return re.sub(r"\s+", " ", teks).strip()


def cetak_hasil(hasil: list[tuple[dict, float]]):
    for no, (a, skor) in enumerate(hasil, 1):
        print(f"{no}. skor {skor:.3f} | {a['label']:<14s} | {a['sumber']} | {a['tanggal'] or '-'}")
        print(f"   {a['judul']}")
        print(f"   {a['url']}" + ("   (URL format lama)" if a.get("url_format_lama") else ""))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Cari artikel cek fakta yang mirip")
    p.add_argument("kalimat", nargs="?", help="kalimat yang dicari")
    p.add_argument("--gambar", type=Path, help="path gambar; teksnya dibaca dengan RapidOCR")
    p.add_argument("--ukuran", choices=["small", "base"], default="base")
    p.add_argument("--varian", choices=["fp32", "int8"], default="fp32")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--folder", type=Path, default=FOLDER_DB)
    a = p.parse_args()
    if bool(a.kalimat) == bool(a.gambar):
        p.error("isi tepat satu: kalimat atau --gambar")

    from embed import Indeks

    if a.gambar:
        if not a.gambar.exists():
            print(f"Berkas tidak ditemukan: {a.gambar}", file=sys.stderr)
            return 2
        teks = baca_gambar(a.gambar)
        print(f"Teks terbaca ({len(teks)} karakter): {rapikan_kueri(teks)[:300]}\n")
        if not re.search(r"\w", teks):
            print("Tidak ada teks yang terbaca.")
            return 1
    else:
        teks = a.kalimat
    indeks = Indeks(a.folder, a.ukuran, a.varian)
    cetak_hasil(indeks.cari([rapikan_kueri(teks)], a.top)[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
