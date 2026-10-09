"""Evaluasi pencarian dan perbandingan model e5 (Sesi 5.3).

Subperintah:
  siapkan-ocr          baca screenshot 09-15 dengan RapidOCR -> uji/ocr/NN.txt (sekali saja)
  sampel-parafrase     tulis uji/sampel_parafrase.json: artikel acak untuk ditulis ulang manual
  siapkan-negatif      tulis uji/negatif_berita.json: kalimat berita asli (CNN/Kompas/Tempo) dari kaggle_linkgish
  ukur                 bangun vektor (bila belum ada) dan ukur satu model -> uji/hasil_UKURAN_VARIAN.json
  ringkas              tabel perbandingan dari semua hasil_*.json

Semua data uji ada di server/data_lokal/cek_fakta/uji/ (tidak masuk repo). Artikel target dikenali lewat
judul ternormalisasi, sehingga uji tetap sah setelah database dibangun ulang.
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from pathlib import Path

import numpy as np

from skema import DATA_LOKAL, FOLDER_DB, MENTAH, baca_jsonl, kunci_judul, kunci_slug

UJI = FOLDER_DB / "uji"
SCREENSHOT = DATA_LOKAL / "screenshot_uji"
SEED = 20261008


def tulis_json(jalur: Path, data):
    jalur.parent.mkdir(parents=True, exist_ok=True)
    jalur.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def muat_json(jalur: Path):
    return json.loads(jalur.read_text(encoding="utf-8"))


# ---------- penyiapan data uji ----------

def siapkan_ocr():
    from cari import baca_gambar

    (UJI / "ocr").mkdir(parents=True, exist_ok=True)
    sumber = {r["nama_file"][:2]: r for r in csv.DictReader(open(DATA_LOKAL / "sumber_gambar.csv", encoding="utf-8-sig"))}
    uji = []
    for nomor in ["09", "10", "11", "12", "13", "14", "15"]:
        berkas = next(SCREENSHOT.glob(f"{nomor}.*"))
        teks = baca_gambar(berkas)
        (UJI / "ocr" / f"{nomor}.txt").write_text(teks, encoding="utf-8")
        url = sumber[nomor]["url_artikel"]
        slug = kunci_slug(url)
        # judul dari slug: buang kata label di depan ('salah-', 'penipuan-'), sisanya huruf-angka saja
        uji.append({"gambar": nomor, "url_artikel": url, "slug": slug, "karakter": len(teks),
                    "kunci": re.sub(r"[^a-z0-9]+", "", slug.split("-", 1)[-1])})
        print(nomor, len(teks), "karakter")
    tulis_json(UJI / "ocr_target.json", uji)


def sampel_parafrase(n: int = 50):
    artikel = [a for a in baca_jsonl(FOLDER_DB / "artikel.jsonl")
               if a["label"] in ("salah", "penipuan") and len(a["narasi"]) >= 80]
    acak = random.Random(SEED).sample(artikel, n)
    tulis_json(UJI / "sampel_parafrase.json",
               [{"no": i + 1, "kunci": kunci_judul(a["judul"]), "judul": a["judul"], "narasi": a["narasi"][:350]}
                for i, a in enumerate(acak)])
    print(f"{n} artikel ditulis ke {UJI / 'sampel_parafrase.json'}")


def siapkan_negatif(per_media: dict | None = None):
    import openpyxl

    per_media = per_media or {"cnn": 7, "kompas": 7, "tempo": 6}
    berkas = {"cnn": "dataset_cnn_10k_cleaned.xlsx", "kompas": "dataset_kompas_4k_cleaned.xlsx",
              "tempo": "dataset_tempo_6k_cleaned.xlsx"}
    awalan = re.compile(r"^.{0,60}?(?:CNN Indonesia\s*--|KOMPAS\.com\s*-|TEMPO\.CO,[^-]{0,40}-)\s*", re.I)
    hasil = []
    rng = random.Random(SEED)
    for media, jumlah in per_media.items():
        wb = openpyxl.load_workbook(MENTAH / "kaggle_linkgish" / "Cleaned" / berkas[media], read_only=True)
        it = wb.worksheets[0].iter_rows(values_only=True)
        kolom = [str(h) for h in next(it)]
        baris = [dict(zip(kolom, r)) for r in it]
        wb.close()
        kandidat = []
        for r in baris:
            teks = awalan.sub("", str(r.get("FullText") or "")).strip()
            kalimat = re.split(r"(?<=[.!?])\s+", teks)
            if len(kalimat) >= 2 and 60 <= len(kalimat[0] + " " + kalimat[1]) <= 320:
                kandidat.append({"media": media, "kueri": kalimat[0] + " " + kalimat[1], "judul_berita": r.get("Title")})
        hasil += rng.sample(kandidat, jumlah)
    tulis_json(UJI / "negatif_berita.json", hasil)
    print(f"{len(hasil)} kalimat berita ditulis ke {UJI / 'negatif_berita.json'}")


# ---------- pengukuran ----------

def persentil(xs, p):
    return float(np.percentile(xs, p)) if len(xs) else float("nan")


def sebaran(xs):
    return {"n": len(xs), "min": round(min(xs), 4) if xs else None, "p10": round(persentil(xs, 10), 4),
            "p50": round(persentil(xs, 50), 4), "p90": round(persentil(xs, 90), 4), "maks": round(max(xs), 4) if xs else None}


def ukur(ukuran: str, varian: str, ulang: bool):
    import psutil

    from embed import Indeks, bangun_vektor, jalur_vektor

    proses = psutil.Process()
    hasil = {"ukuran": ukuran, "varian": varian}
    jv = jalur_vektor(FOLDER_DB, ukuran, varian)
    if ulang or not jv.exists():
        print(f"Membangun vektor {ukuran}/{varian} ...")
        meta = bangun_vektor(FOLDER_DB, ukuran, varian)
        hasil["ram_puncak_bangun_mb"] = round(proses.memory_info().peak_wset / 1e6)
        print(meta)
    else:
        meta = muat_json(jv.with_suffix(".json"))
    hasil |= {"detik_bangun": meta["detik_bangun"], "jumlah_artikel": meta["jumlah"], "dimensi": meta["dimensi"],
              "byte_vektor": jv.stat().st_size}

    # RAM sesudah memuat model + vektor dalam proses yang sama (untuk proses pemuatan bersih, jalankan ulang tanpa --ulang)
    rss0 = proses.memory_info().rss
    ind = Indeks(FOLDER_DB, ukuran, varian)
    ind.embedder.encode_kueri(["pemanasan"])
    hasil["ram_tambahan_mb"] = round((proses.memory_info().rss - rss0) / 1e6)
    from unduh_model import jalur_model
    hasil["byte_model"] = jalur_model(ukuran, varian).stat().st_size

    # 1. screenshot OCR 09-15
    ocr = muat_json(UJI / "ocr_target.json")
    ocr_hasil = []
    for o in ocr:
        teks = re.sub(r"\s+", " ", (UJI / "ocr" / f"{o['gambar']}.txt").read_text(encoding="utf-8")).strip()
        if len(re.findall(r"\w", teks)) < 20:
            ocr_hasil.append({"gambar": o["gambar"], "catatan": "tanpa teks", "teratas": None})
            continue
        top = ind.cari([teks], 5)[0]
        # artikel sumber bisa tersimpan dengan slug lain (format Komdigi), jadi cocokkan juga lewat judul
        urut = [kunci_slug(a["url"]) == o["slug"] or kunci_judul(a["judul"]) == o["kunci"] for a, _ in top]
        ocr_hasil.append({"gambar": o["gambar"], "peringkat_benar": (urut.index(True) + 1) if True in urut else None,
                          "skor_teratas": round(top[0][1], 4), "judul_teratas": top[0][0]["judul"],
                          "skor_benar": round(top[urut.index(True)][1], 4) if True in urut else None})
    hasil["ocr"] = ocr_hasil

    # 2. parafrase
    para = muat_json(UJI / "parafrase.json")
    kunci_semua = {kunci_judul(a["judul"]): i for i, a in enumerate(ind.artikel)}
    peringkat, skor_benar, skor_salah, tidak_ada = [], [], [], 0
    keluar = ind.cari_vektor(ind.embedder.encode_kueri([p["kueri"] for p in para]), 5)
    for p, baris in zip(para, keluar):
        if p["kunci"] not in kunci_semua:
            tidak_ada += 1
            continue
        tujuan = kunci_semua[p["kunci"]]
        idx = [i for i, _ in baris]
        peringkat.append(idx.index(tujuan) + 1 if tujuan in idx else None)
        (skor_benar if idx[0] == tujuan else skor_salah).append(baris[0][1])
    n = len(peringkat)
    hasil["parafrase"] = {"n": n, "target_tidak_ada_di_db": tidak_ada,
                          "recall@1": round(sum(1 for r in peringkat if r == 1) / n, 4) if n else None,
                          "recall@5": round(sum(1 for r in peringkat if r) / n, 4) if n else None,
                          "skor_top1_benar": sebaran(skor_benar), "skor_top1_salah": sebaran(skor_salah)}
    hasil["parafrase_skor_top1_semua"] = [round(b[0][1], 4) for b in keluar]

    # 3. negatif
    neg = muat_json(UJI / "negatif.json")
    keluar_neg = ind.cari_vektor(ind.embedder.encode_kueri([x["kueri"] for x in neg]), 1)
    skor_neg = [b[0][1] for b in keluar_neg]
    hasil["negatif"] = {"skor_top1": sebaran(skor_neg),
                        "per_jenis": {j: sebaran([s for x, s in zip(neg, skor_neg) if x["jenis"] == j])
                                      for j in sorted({x["jenis"] for x in neg})}}
    hasil["negatif_skor_top1_semua"] = [round(s, 4) for s in skor_neg]
    hasil["negatif_teratas"] = [{"kueri": x["kueri"][:90], "skor": round(s, 4), "judul": ind.artikel[b[0][0]]["judul"][:90]}
                                for x, s, b in zip(neg, skor_neg, keluar_neg)]

    # 4. waktu per kueri (encode + cari, kueri tunggal)
    contoh = [p["kueri"] for p in para[:10]]
    waktu = []
    for _ in range(3):
        for q in contoh:
            t = time.perf_counter()
            ind.cari([q], 5)
            waktu.append(time.perf_counter() - t)
    hasil["detik_per_kueri_median"] = round(float(np.median(waktu)), 4)
    hasil["detik_per_kueri_p90"] = round(persentil(waktu, 90), 4)
    tulis_json(UJI / f"hasil_{ukuran}_{varian}.json", hasil)
    print(json.dumps({k: v for k, v in hasil.items() if not k.endswith("_semua") and k != "negatif_teratas"},
                     ensure_ascii=False, indent=1))


def ringkas():
    hasil = [muat_json(p) for p in sorted(UJI.glob("hasil_*.json"))]
    kolom = [("model", lambda h: f"e5-{h['ukuran']}/{h['varian']}"),
             ("artikel", lambda h: h["jumlah_artikel"]),
             ("recall@1 parafrase", lambda h: h["parafrase"]["recall@1"]),
             ("recall@5 parafrase", lambda h: h["parafrase"]["recall@5"]),
             ("OCR benar@1", lambda h: sum(1 for o in h["ocr"] if o.get("peringkat_benar") == 1)),
             ("OCR benar@5", lambda h: sum(1 for o in h["ocr"] if o.get("peringkat_benar"))),
             ("skor cocok p50", lambda h: h["parafrase"]["skor_top1_benar"]["p50"]),
             ("skor negatif p50", lambda h: h["negatif"]["skor_top1"]["p50"]),
             ("skor negatif p90", lambda h: h["negatif"]["skor_top1"]["p90"]),
             ("bangun (dtk)", lambda h: h["detik_bangun"]),
             ("dtk/kueri", lambda h: h["detik_per_kueri_median"]),
             ("model (MB)", lambda h: round(h["byte_model"] / 1e6)),
             ("vektor (MB)", lambda h: round(h["byte_vektor"] / 1e6)),
             ("RAM tambahan (MB)", lambda h: h["ram_tambahan_mb"])]
    print("| " + " | ".join(k for k, _ in kolom) + " |")
    print("|" + "---|" * len(kolom))
    for h in hasil:
        print("| " + " | ".join(str(f(h)) for _, f in kolom) + " |")
    # usulan ambang: persentil 95 skor negatif, dan recall parafrase pada ambang itu
    for h in hasil:
        neg = h["negatif_skor_top1_semua"]
        pos = h["parafrase_skor_top1_semua"]
        for nama, t in (("p95 negatif", persentil(neg, 95)), ("maks negatif", max(neg))):
            tertangkap = sum(1 for s in pos if s >= t) / len(pos)
            print(f"e5-{h['ukuran']}/{h['varian']}: ambang {nama} = {t:.3f} -> {tertangkap:.0%} parafrase di atas ambang")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    for nama in ("siapkan-ocr", "sampel-parafrase", "siapkan-negatif", "ringkas"):
        s.add_parser(nama)
    u = s.add_parser("ukur")
    u.add_argument("--ukuran", choices=["small", "base"], required=True)
    u.add_argument("--varian", choices=["fp32", "int8"], default="fp32")
    u.add_argument("--ulang", action="store_true", help="bangun ulang vektor walau sudah ada")
    v = s.add_parser("vektor", help="hanya membangun vektor")
    v.add_argument("--ukuran", choices=["small", "base"], required=True)
    v.add_argument("--varian", choices=["fp32", "int8"], default="fp32")
    a = p.parse_args()
    if a.cmd == "siapkan-ocr":
        siapkan_ocr()
    elif a.cmd == "sampel-parafrase":
        sampel_parafrase()
    elif a.cmd == "siapkan-negatif":
        siapkan_negatif()
    elif a.cmd == "ukur":
        ukur(a.ukuran, a.varian, a.ulang)
    elif a.cmd == "vektor":
        from embed import bangun_vektor
        print(bangun_vektor(FOLDER_DB, a.ukuran, a.varian))
    elif a.cmd == "ringkas":
        ringkas()


if __name__ == "__main__":
    main()
