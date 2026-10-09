"""Menggabungkan dataset Kaggle dan hasil pengumpulan menjadi satu database artikel cek fakta.

Keluaran (server/data_lokal/cek_fakta/): artikel.jsonl dan laporan_gabung.txt.
Prioritas saat duplikat: hasil pengumpulan situs > Kaggle TurnBackHoax > Komdigi.
Bisa dijalankan ulang kapan saja: python bangun.py
"""

import argparse
import collections
import csv
import random
import re
import sys
from pathlib import Path

from skema import (
    FOLDER_DB, KOLOM, MENTAH, baca_jsonl, id_stabil, judul_bersih, kunci_judul, kunci_slug, kunci_url,
    label_asli_dari_judul, narasi_dari_komdigi, narasi_dari_teks_tbh, label_dengan_hasil_periksa, tanggal_iso, tulis_jsonl,
    url_format_lama,
)

PRIORITAS = {"situs_turnbackhoax": 0, "kaggle_aginanjar": 1, "kaggle_linkgish": 1, "kaggle_ireddragonicy": 2}
SELISIH_HARI_JUDUL = 7


# ---------- pemuat sumber ----------

def _csv(jalur: Path):
    csv.field_size_limit(10**9)
    with open(jalur, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def _xlsx(jalur: Path):
    import openpyxl

    wb = openpyxl.load_workbook(jalur, read_only=True)
    baris = wb.worksheets[0].iter_rows(values_only=True)
    judul_kolom = [str(h) for h in next(baris)]
    for r in baris:
        yield dict(zip(judul_kolom, r))
    wb.close()


def muat_linkgish_tbh(mentah: Path = MENTAH) -> list[dict]:
    jalur = mentah / "kaggle_linkgish" / "Cleaned" / "dataset_turnbackhoax_10_cleaned.xlsx"
    hasil = []
    for r in _xlsx(jalur):
        if not r.get("Url"):
            continue
        hasil.append({
            "judul": (r.get("Title") or "").strip(), "url": r["Url"].strip(), "tanggal": tanggal_iso(r.get("Timestamp")),
            "narasi": narasi_bersih_lg(r.get("Clean Narasi")), "asal_data": "kaggle_linkgish",
        })
    return hasil


def narasi_bersih_lg(nilai) -> str:
    from skema import rapikan

    return rapikan(str(nilai)) if nilai else ""


def muat_aginanjar(mentah: Path = MENTAH, narasi_lg: dict[str, str] | None = None) -> list[dict]:
    narasi_lg = narasi_lg or {}
    hasil = []
    for r in _csv(next((mentah / "kaggle_aginanjar").glob("*.csv"))):
        url = (r.get("link") or "").strip()
        narasi = narasi_lg.get(kunci_url(url)) or narasi_dari_teks_tbh(r.get("teks", ""))
        hasil.append({"judul": (r.get("judul") or "").strip(), "url": url, "tanggal": tanggal_iso(r.get("tanggal")),
                      "narasi": narasi, "asal_data": "kaggle_aginanjar"})
    return hasil


def muat_komdigi(mentah: Path = MENTAH) -> list[dict]:
    hasil = []
    for r in _csv(mentah / "kaggle_ireddragonicy" / "komdigi_hoaks.csv"):
        judul = (r.get("title") or "").strip()
        body = r.get("body_text") or ""
        ref = re.findall(r"https?://\S+", body.split("Link Counter", 1)[1]) if "Link Counter" in body else []
        hasil.append({
            "judul": judul, "url": (r.get("url") or "").strip(), "tanggal": tanggal_iso(r.get("published_at")),
            "narasi": narasi_dari_komdigi(body), "asal_data": "kaggle_ireddragonicy",
            # semua artikel kategori ini adalah klarifikasi hoaks; judul tanpa kurung dianggap HOAKS
            "label_asli": label_asli_dari_judul(judul) or "HOAKS", "ref_url": [u.rstrip(".,;)") for u in ref],
        })
    return hasil


def muat_situs(folder: Path = FOLDER_DB) -> list[dict]:
    hasil = []
    for d in baca_jsonl(folder / "tbh_artikel.jsonl"):
        if d.get("galat"):
            continue  # halaman tidak terbaca; tidak punya narasi maupun tanggal yang pasti
        hasil.append({"judul": d["judul"], "url": d["url"], "tanggal": tanggal_iso(d.get("tanggal")), "narasi": d.get("narasi", ""),
                      "asal_data": "situs_turnbackhoax", "id_situs": d.get("id_situs"), "hasil_periksa": d.get("hasil_periksa", ""),
                      "label_asli": d.get("label_asli") or label_asli_dari_judul(d["judul"])})
    return hasil


# ---------- penggabungan (fungsi murni, diuji) ----------

def _hari(iso: str | None):
    import datetime

    return datetime.date.fromisoformat(iso) if iso else None


def _tanggal_dekat(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True
    return abs((_hari(a) - _hari(b)).days) <= SELISIH_HARI_JUDUL


def gabung(rekaman: list[dict]) -> tuple[list[dict], dict]:
    """Membuang duplikat. Rekaman berprioritas lebih tinggi (angka lebih kecil) dipertahankan, narasi yang
    kosong diisi dari duplikatnya. Mengembalikan (artikel, statistik)."""
    urut = sorted(range(len(rekaman)), key=lambda i: (PRIORITAS[rekaman[i]["asal_data"]], i))
    simpan: list[dict] = []
    per_url: dict[str, int] = {}
    per_slug: dict[str, int] = {}
    per_judul: dict[str, list[int]] = collections.defaultdict(list)
    stat = collections.Counter()

    for i in urut:
        r = dict(rekaman[i])
        if not r.get("url"):
            stat["dibuang_tanpa_url"] += 1
            continue
        if not r.get("label_asli"):
            r["label_asli"] = label_asli_dari_judul(r["judul"])
        r["label"] = label_dengan_hasil_periksa(r["label_asli"], r.get("hasil_periksa", ""))
        if r["label"] == "bukan_cek_fakta":
            stat["dibuang_bukan_cek_fakta"] += 1
            continue

        ku, ks, kj = kunci_url(r["url"]), kunci_slug(r["url"]), kunci_judul(r["judul"])
        cocok, alasan = None, ""
        if ku in per_url:
            cocok, alasan = per_url[ku], "url"
        elif ks and "turnbackhoax.id" in r["url"] and ks in per_slug:
            cocok, alasan = per_slug[ks], "slug"
        else:
            for u in r.get("ref_url", []):
                k2 = kunci_slug(u) if "turnbackhoax.id" in u else ""
                if kunci_url(u) in per_url:
                    cocok, alasan = per_url[kunci_url(u)], "ref_url"
                    break
                if k2 and k2 in per_slug:
                    cocok, alasan = per_slug[k2], "ref_slug"
                    break
        if cocok is None and len(kj) >= 12:
            for j in per_judul.get(kj, []):
                if _tanggal_dekat(r["tanggal"], simpan[j]["tanggal"]):
                    cocok, alasan = j, "judul"
                    break

        if cocok is not None:
            tujuan = simpan[cocok]
            if not tujuan["narasi"] and r.get("narasi"):
                tujuan["narasi"] = r["narasi"]
            if not tujuan["tanggal"] and r["tanggal"]:
                tujuan["tanggal"] = r["tanggal"]
            if r["asal_data"] != tujuan["asal_data"] and r["asal_data"] not in tujuan["asal_lain"]:
                tujuan["asal_lain"].append(r["asal_data"])
            stat[f"duplikat_{alasan}"] += 1
            # alamat yang sama dengan salah satu duplikat tetap dikenali pada baris berikutnya
            per_url.setdefault(ku, cocok)
            if ks and "turnbackhoax.id" in r["url"]:
                per_slug.setdefault(ks, cocok)
            continue

        r["sumber"] = "Komdigi" if r["asal_data"] == "kaggle_ireddragonicy" else "TurnBackHoax"
        r["asal_lain"] = []
        idx = len(simpan)
        simpan.append(r)
        per_url[ku] = idx
        if ks and "turnbackhoax.id" in r["url"]:
            per_slug[ks] = idx
        if len(kj) >= 12:
            per_judul[kj].append(idx)

    artikel = []
    for r in simpan:
        id_artikel = f"tbh-{r['id_situs']}" if r.get("id_situs") else id_stabil(kunci_slug(r["url"]) or kunci_url(r["url"]))
        artikel.append({
            "id": id_artikel, "judul": r["judul"], "narasi": r["narasi"] or "", "label_asli": r["label_asli"],
            "label": r["label"], "sumber": r["sumber"], "url": r["url"], "tanggal": r["tanggal"],
            "asal_data": r["asal_data"], "asal_lain": r["asal_lain"], "url_format_lama": url_format_lama(r["url"]),
        })
    urut_id = sorted(artikel, key=lambda a: (a["tanggal"] or "", a["id"]), reverse=True)
    return urut_id, dict(stat)


# ---------- laporan ----------

def laporan(artikel: list[dict], stat: dict, jumlah_masuk: dict) -> str:
    L = ["LAPORAN PENGGABUNGAN DATABASE CEK FAKTA", ""]
    L.append("Baris masuk per sumber: " + ", ".join(f"{k}={v}" for k, v in sorted(jumlah_masuk.items())))
    L.append("Pembuangan dan duplikat: " + ", ".join(f"{k}={v}" for k, v in sorted(stat.items())))
    L.append(f"\nJUMLAH AKHIR: {len(artikel)}")
    L.append("\nPer asal_data (pemenang saat duplikat):")
    for k, v in collections.Counter(a["asal_data"] for a in artikel).most_common():
        L.append(f"  {k:24s} {v}")
    L.append("\nPer label:")
    for k, v in collections.Counter(a["label"] for a in artikel).most_common():
        L.append(f"  {k:16s} {v}")
    L.append("\nPer tahun:")
    for k, v in sorted(collections.Counter((a["tanggal"] or "tanpa tanggal")[:4] for a in artikel).items()):
        L.append(f"  {k:14s} {v}")
    L.append("\nCakupan narasi (terisi / total) per asal_data:")
    for asal in sorted({a["asal_data"] for a in artikel}):
        grup = [a for a in artikel if a["asal_data"] == asal]
        L.append(f"  {asal:24s} {sum(1 for a in grup if a['narasi'])} / {len(grup)}")
    lama = [a for a in artikel if a["url_format_lama"]]
    L.append(f"\nBaris yang hanya punya URL format lama (kemungkinan 404): {len(lama)}")
    L.append(f"Baris tanpa tanggal: {sum(1 for a in artikel if not a['tanggal'])}")
    return "\n".join(L) + "\n"


def contoh_lainnya(artikel: list[dict], n: int = 20, seed: int = 7) -> list[dict]:
    kandidat = [a for a in artikel if a["label"] == "lainnya"]
    random.Random(seed).shuffle(kandidat)
    return kandidat[:n]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Gabung dataset Kaggle dan hasil pengumpulan")
    p.add_argument("--folder", type=Path, default=FOLDER_DB, help="folder database (bawaan: data_lokal/cek_fakta)")
    p.add_argument("--mentah", type=Path, default=MENTAH, help="folder dataset_mentah")
    p.add_argument("--contoh-lainnya", type=int, default=0, help="cetak N judul acak berlabel 'lainnya'")
    a = p.parse_args()

    lg = muat_linkgish_tbh(a.mentah)
    narasi_lg = {kunci_url(r["url"]): r["narasi"] for r in lg if r["narasi"]}
    agi = muat_aginanjar(a.mentah, narasi_lg)
    kom = muat_komdigi(a.mentah)
    situs = muat_situs(a.folder)
    masuk = {"kaggle_aginanjar": len(agi), "kaggle_linkgish_turnbackhoax": len(lg), "kaggle_ireddragonicy": len(kom),
             "situs_turnbackhoax": len(situs)}
    artikel, stat = gabung(situs + agi + lg + kom)
    n = tulis_jsonl(a.folder / "artikel.jsonl", artikel)
    teks = laporan(artikel, stat, masuk)
    (a.folder / "laporan_gabung.txt").write_text(teks, encoding="utf-8")
    print(teks)
    print(f"Ditulis {n} artikel ke {a.folder / 'artikel.jsonl'}")
    if a.contoh_lainnya:
        print(f"\n{a.contoh_lainnya} contoh acak berlabel 'lainnya':")
        for c in contoh_lainnya(artikel, a.contoh_lainnya):
            print(f"  [{c['asal_data']}] {c['judul']}")


if __name__ == "__main__":
    main()
