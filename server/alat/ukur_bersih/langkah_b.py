"""Langkah B pengukuran pembersihan teks (Sesi 5.4): pencarian e5 dengan teks mentah dan teks bersih.

Dijalankan dari folder server dengan venv alat cek fakta (.venv-cekfakta), SETELAH langkah A:

    .venv-cekfakta\\Scripts\\python alat\\ukur_bersih\\langkah_b.py

Hanya screenshot 09-14 (artikel sumbernya ada di sumber_gambar.csv). Menulis pencarian.csv dan laporan_b.md
di server\\data_lokal\\hasil_bersih\\. Enam gambar terlalu sedikit untuk menetapkan ambang skor; ambang final
ada di Sesi 5.6.
"""

import csv
import json
import re
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER / "alat" / "cek_fakta"))

from embed import Indeks  # noqa: E402
from skema import FOLDER_DB  # noqa: E402

DATA_LOKAL = SERVER / "data_lokal"
FOLDER_HASIL = DATA_LOKAL / "hasil_bersih"
GAMBAR = ["09", "10", "11", "12", "13", "14"]
KUERI = {"mentah": None, "bersih": "bawaan", "bersih+baca_juga": "bawaan+baca_juga"}


def sumber_artikel() -> dict[str, str]:
    hasil = {}
    with open(DATA_LOKAL / "sumber_gambar.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            m = re.search(r"/articles/(\d+)", r["url_artikel"])
            if m:
                hasil[r["nama_file"].split(".")[0]] = m.group(1)
    return hasil


def cari(indeks, teks: str, id_artikel: str) -> dict:
    kueri = re.sub(r"\s+", " ", teks).strip()
    if not kueri:
        return {"peringkat": None, "skor_sumber": None, "skor_1": None, "selisih_1_2": None}
    hasil = indeks.cari([kueri], 50)[0]
    peringkat = skor = None
    for i, (art, s) in enumerate(hasil, 1):
        if id_artikel in art["url"]:
            peringkat, skor = i, s
            break
    return {"peringkat": peringkat, "skor_sumber": skor, "skor_1": hasil[0][1], "selisih_1_2": hasil[0][1] - hasil[1][1]}


def f(x, d=3):
    return "-" if x is None else f"{x:.{d}f}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sumber = sumber_artikel()
    indeks = Indeks(FOLDER_DB, "base", "fp32")
    baris = []
    for g in GAMBAR:
        berkas = FOLDER_HASIL / f"{g}.json"
        if not berkas.exists():
            print(f"{berkas} tidak ada. Jalankan langkah A dulu.", file=sys.stderr)
            return 2
        e = json.loads(berkas.read_text(encoding="utf-8"))
        for nama, varian in KUERI.items():
            teks = e["teks_mentah"] if varian is None else e["varian"][varian]["teks"]
            baris.append({"gambar": g, "kueri": nama, "karakter": len(teks), "id_artikel": sumber[g], **cari(indeks, teks, sumber[g])})
            print(g, nama, baris[-1]["peringkat"], f(baris[-1]["skor_sumber"]), flush=True)

    with open(FOLDER_HASIL / "pencarian.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(baris[0]))
        w.writeheader()
        w.writerows(baris)

    L = ["# Laporan langkah B: pencarian e5-base fp32, artikel sumber gambar 09-14", "",
         "Kueri = teks gambar setelah spasi dirapikan. Selisih = skor peringkat 1 dikurangi skor peringkat 2. "
         "Enam gambar terlalu sedikit untuk menetapkan ambang; ambang skor final tetap di Sesi 5.6.", "",
         "| Gambar | Kueri | Karakter | Peringkat sumber | Skor sumber | Skor peringkat 1 | Selisih 1-2 |", "|---|---|---|---|---|---|---|"]
    for b in baris:
        L.append(f"| {b['gambar']} | {b['kueri']} | {b['karakter']} | {b['peringkat'] or '>50'} | {f(b['skor_sumber'])} | "
                 f"{f(b['skor_1'])} | {f(b['selisih_1_2'])} |")
    L += ["", "## Perbandingan skor sumber: bersih dikurangi mentah", "", "| Gambar | Bersih | Bersih+baca_juga |", "|---|---|---|"]
    for g in GAMBAR:
        by = {b["kueri"]: b for b in baris if b["gambar"] == g}

        def sel(k):
            a, m = by[k]["skor_sumber"], by["mentah"]["skor_sumber"]
            return "-" if a is None or m is None else f"{a - m:+.3f}"

        L.append(f"| {g} | {sel('bersih')} | {sel('bersih+baca_juga')} |")
    (FOLDER_HASIL / "laporan_b.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Laporan: {FOLDER_HASIL / 'laporan_b.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
