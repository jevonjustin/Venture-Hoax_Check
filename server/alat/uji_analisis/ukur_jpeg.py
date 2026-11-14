"""Mengukur pengaruh kualitas JPEG dan sisi terpanjang potongan pada hasil analisis (Sesi 8.2). Tanpa LLM, tanpa jaringan.

Gambar set uji beku (server\\data_lokal\\evaluasi) dan gambar demo (server\\data_lokal\\demo) hanya dibaca. Setiap gambar
disandikan ulang seperti PenyandiJpeg di HP (diperkecil proporsional sampai sisi terpanjang <= SISI, lalu JPEG
kualitas Q), lalu dikirim ke /analisis lewat TestClient (OCR, pembersih, regex, pencarian e5 sungguhan; LLM mati).
Pembanding: varian aplikasi saat ini (2000 px, kualitas 90).

Kriteria "hasil tidak berubah" per gambar: teks_terbaca persis sama (jadi teks yang dikirim ke LLM juga sama) dan
tingkat tanpa LLM sama. Yang dicetak hanya angka dan id gambar, bukan teks.

Pakai (dari folder server; memuat e5 sekitar 1,5 GB RAM, sekitar 5 menit):
  .venv\\Scripts\\python.exe alat\\uji_analisis\\ukur_jpeg.py
"""

import csv
import io
import os
import statistics
import sys
from pathlib import Path

os.environ["CEKHOAKS_LLM"] = "mati"
os.environ.pop("PAKSA_TINGKAT", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app import konfigurasi  # noqa: E402

DATA = konfigurasi.DATA_LOKAL
ACUAN = (2000, 90)
VARIAN = [(2000, 80), (2000, 75), (2000, 70), (1600, 80), (1280, 80), (1280, 75)]


def daftar_gambar() -> list[tuple[str, Path]]:
    with open(DATA / "evaluasi" / "metadata.csv", encoding="utf-8") as f:
        uji = [(b["id"], DATA / "evaluasi" / "gambar" / b["berkas"]) for b in csv.DictReader(f) if b["set"] == "uji"]
    demo = [(p.stem.split("_")[0] + "_demo", p) for p in sorted((DATA / "demo").glob("[1-4]_*.png"))]
    return uji + demo


def sandikan(gambar: Image.Image, sisi: int, kualitas: int) -> bytes:
    """Meniru PenyandiJpeg.ukuranTarget + Bitmap.compress(JPEG, kualitas)."""
    lebar, tinggi = gambar.size
    terpanjang = max(lebar, tinggi)
    if terpanjang > sisi:
        skala = sisi / terpanjang
        gambar = gambar.resize((max(1, round(lebar * skala)), max(1, round(tinggi * skala))), Image.BILINEAR)
    keluaran = io.BytesIO()
    gambar.save(keluaran, format="JPEG", quality=kualitas)
    return keluaran.getvalue()


def analisis(klien: TestClient, data: bytes) -> tuple[int, str | None, str | None]:
    r = klien.post("/analisis", files={"gambar": ("p.jpg", data, "image/jpeg")})
    if r.status_code != 200:
        return r.status_code, (r.json().get("galat") or {}).get("kode"), None
    isi = r.json()
    return 200, isi["tingkat"], isi.get("teks_terbaca") or ""


def main() -> int:
    from app import main as server

    konfigurasi.pengaturan.jeda_min_detik = 0.0
    konfigurasi.pengaturan.jeda_maks_detik = 0.0
    gambar = daftar_gambar()
    print(f"{len(gambar)} gambar; acuan {ACUAN}; varian {VARIAN}")
    ringkas = {v: {"byte": [], "teks_beda": [], "tingkat_beda": []} for v in [ACUAN] + VARIAN}
    with TestClient(server.app) as klien:
        for n, (id_, jalur) in enumerate(gambar, 1):
            asli = Image.open(jalur).convert("RGB")
            data_acuan = sandikan(asli, *ACUAN)
            st0, tk0, tx0 = analisis(klien, data_acuan)
            ringkas[ACUAN]["byte"].append(len(data_acuan))
            for v in VARIAN:
                data = sandikan(asli, *v)
                st, tk, tx = analisis(klien, data)
                ringkas[v]["byte"].append(len(data))
                if (st, tx) != (st0, tx0):
                    ringkas[v]["teks_beda"].append(id_)
                if (st, tk) != (st0, tk0):
                    ringkas[v]["tingkat_beda"].append(f"{id_}:{tk0}->{tk}")
            if n % 10 == 0:
                print(f"  {n}/{len(gambar)}", flush=True)
    print(f"\n{'varian':<12} {'median KB':>9} {'rata KB':>8} {'hemat':>6}  teks beda  tingkat beda")
    dasar = statistics.mean(ringkas[ACUAN]["byte"])
    for v, r in ringkas.items():
        rata = statistics.mean(r["byte"])
        print(f"{str(v):<12} {statistics.median(r['byte']) / 1024:9.0f} {rata / 1024:8.0f} {1 - rata / dasar:6.0%}  "
              f"{len(r['teks_beda']):>9}  {len(r['tingkat_beda']):>12}  {' '.join(r['tingkat_beda'])}")
        if r["teks_beda"]:
            print(f"{'':<12} teks beda: {' '.join(r['teks_beda'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
