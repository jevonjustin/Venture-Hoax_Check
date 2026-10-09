"""Langkah A pengukuran pembersihan teks (Sesi 5.4): RapidOCR + pipeline/bersih.py pada screenshot uji.

Dijalankan dari folder server dengan venv server (.venv):

    .venv\\Scripts\\python alat\\ukur_bersih\\langkah_a.py

Menulis server\\data_lokal\\hasil_bersih\\NN.json (teks mentah, baris dengan kotak, dan hasil tiap varian
pembersihan) serta laporan_a.md. Tidak memanggil jaringan dan tidak menulis gambar.
"""

import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER))

from PIL import Image  # noqa: E402

from app.pipeline import bersih  # noqa: E402
from app.pipeline.baca import Pembaca  # noqa: E402

FOLDER_GAMBAR = SERVER / "data_lokal" / "screenshot_uji"
FOLDER_ACUAN = SERVER / "data_lokal" / "transkripsi"
FOLDER_HASIL = SERVER / "data_lokal" / "hasil_bersih"

VARIAN = {
    "bawaan": frozenset(),
    "bawaan+baca_juga": frozenset({bersih.VARIAN_BACA_JUGA}),
}
MIN_HURUF_KATA = 3


def kata(teks: str) -> set[str]:
    return {k for k in re.findall(r"\w+", teks.lower()) if len(k) >= MIN_HURUF_KATA}


def baca_acuan(nomor: str) -> tuple[set[str], set[str]]:
    """(kata isi, kata UI) dari transkripsi. Potongan [?] tidak dihitung. Kata UI yang juga ada di isi dikeluarkan."""
    isi, ui = [], []
    for baris in (FOLDER_ACUAN / f"{nomor}.txt").read_text(encoding="utf-8-sig").splitlines():
        baris = re.sub(r"\[\?[^\]]*\]", " ", baris)
        if baris.startswith("[UI]"):
            ui.append(baris[4:])
        else:
            isi.append(baris)
    k_isi = kata(" ".join(isi))
    return k_isi, kata(" ".join(ui)) - k_isi


def metrik(isi: set[str], ui: set[str], mentah: str, teks_bersih: str) -> dict:
    r, b = kata(mentah), kata(teks_bersih)
    terbaca = isi & r
    return {
        "kata_isi": len(isi),
        "isi_terbaca_mentah": len(terbaca),
        "isi_terbaca_bersih": len(isi & b),
        "isi_hilang": sorted(terbaca - b),
        "ui_terbaca_mentah": len(ui & r),
        "ui_hilang": len((ui & r) - b),
    }


def persen(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "-"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    pembaca = Pembaca()
    pembaca._muat()
    semua: dict[str, dict] = {}
    for jalur in sorted(FOLDER_GAMBAR.iterdir()):
        nomor = jalur.stem
        data = jalur.read_bytes()
        with Image.open(io.BytesIO(data)) as g:
            lebar, tinggi = g.size
        hasil = pembaca._baca(data)
        isi, ui = baca_acuan(nomor)
        entri = {
            "gambar": jalur.name, "lebar": lebar, "tinggi": tinggi, "teks_mentah": hasil.teks,
            "baris": [{"teks": b.teks, "kotak": b.kotak, "skor": b.skor} for b in hasil.baris], "varian": {},
        }
        for nama, v in VARIAN.items():
            r = bersih.bersihkan(hasil.baris, lebar, tinggi, v)
            entri["varian"][nama] = {
                "teks": r.teks, "dibuang": [{"alasan": d.alasan, "teks": d.teks} for d in r.dibuang],
                "metrik": metrik(isi, ui, hasil.teks, r.teks),
            }
        (FOLDER_HASIL / f"{nomor}.json").write_text(json.dumps(entri, ensure_ascii=False, indent=1), encoding="utf-8")
        semua[nomor] = entri
        print(f"{nomor}: {len(hasil.baris)} baris, dibuang {len(entri['varian']['bawaan']['dibuang'])}", flush=True)

    L = ["# Laporan langkah A: pembersihan teks pada 18 screenshot uji", ""]
    for nama in VARIAN:
        L += [f"## Varian `{nama}`", "",
              "| Gambar | Baris | Dibuang | Kata isi | Terbaca mentah | Terbaca bersih | Dipertahankan | Kata UI terbaca | UI hilang |",
              "|---|---|---|---|---|---|---|---|---|"]
        total = Counter()
        for nomor, e in semua.items():
            m = e["varian"][nama]["metrik"]
            d = len(e["varian"][nama]["dibuang"])
            total.update({"baris": len(e["baris"]), "dibuang": d, **{k: m[k] for k in m if k != "isi_hilang"}})
            L.append(f"| {nomor} | {len(e['baris'])} | {d} | {m['kata_isi']} | {m['isi_terbaca_mentah']} | "
                     f"{m['isi_terbaca_bersih']} | {persen(m['isi_terbaca_bersih'], m['isi_terbaca_mentah'])} | "
                     f"{m['ui_terbaca_mentah']} | {m['ui_hilang']} |")
        L.append(f"| **Jumlah** | {total['baris']} | {total['dibuang']} | {total['kata_isi']} | {total['isi_terbaca_mentah']} | "
                 f"{total['isi_terbaca_bersih']} | **{persen(total['isi_terbaca_bersih'], total['isi_terbaca_mentah'])}** | "
                 f"{total['ui_terbaca_mentah']} | {total['ui_hilang']} |")
        L += ["", "Kata isi transkripsi yang terbaca di teks mentah tetapi hilang di teks bersih:", ""]
        ada = False
        for nomor, e in semua.items():
            h = e["varian"][nama]["metrik"]["isi_hilang"]
            if h:
                ada = True
                L.append(f"- {nomor}: {', '.join(h)}")
        if not ada:
            L.append("- (tidak ada)")
        L += ["", "Rincian pembuangan per alasan (jumlah baris pada 18 gambar):", ""]
        alasan = Counter(d["alasan"] for e in semua.values() for d in e["varian"][nama]["dibuang"])
        L += [f"- {a}: {n}" for a, n in alasan.most_common()] or ["- (tidak ada)"]
        L.append("")

    L += ["## Baris yang dibuang per gambar (varian `bawaan`)", ""]
    for nomor, e in semua.items():
        d = e["varian"]["bawaan"]["dibuang"]
        L.append(f"### {nomor} ({len(d)} baris)")
        L += [f"- [{x['alasan']}] {x['teks']}" for x in d] or ["- (tidak ada)"]
        L.append("")
    L += ["## Tambahan yang hanya dibuang varian lain (bukan aturan bawaan)", ""]
    for nama in ("bawaan+baca_juga",):
        L += [f"### {nama}", ""]
        for nomor, e in semua.items():
            bawaan = {(x["alasan"], x["teks"]) for x in e["varian"]["bawaan"]["dibuang"]}
            tambah = [x for x in e["varian"][nama]["dibuang"] if (x["alasan"], x["teks"]) not in bawaan]
            L += [f"- {nomor}: [{x['alasan']}] {x['teks']}" for x in tambah]
        L.append("")
    (FOLDER_HASIL / "laporan_a.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Laporan: {FOLDER_HASIL / 'laporan_a.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
