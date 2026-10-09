"""Mengukur kandidat API LLM untuk analisis teks OCR (Sesi 5.4a).

Contoh (dari server\\alat\\ukur_llm):
  ..\\..\\.venv-cekfakta\\Scripts\\python ukur.py anggaran
  ..\\..\\.venv-cekfakta\\Scripts\\python ukur.py jalankan --model gpt-oss-120b
  ..\\..\\.venv-cekfakta\\Scripts\\python ukur.py ringkas
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

from klien import Klien, muat_kunci
from konfigurasi import (FOLDER_HASIL, FOLDER_OCR, GAMBAR_PENCARIAN, KANDIDAT, SUMBER_GAMBAR, TEKS_ULANGAN)
from metrik import jaccard, kata_penilaian_tambahan, kutipan_jujur, median, normalisasi, persentil
from samarkan import samarkan

SEMUA_KODE = [f"{i:02d}" for i in range(1, 19)]
ALAT_CEKFAKTA = Path(__file__).resolve().parents[1] / "cek_fakta"


def baca_ocr(kode: str) -> str:
    return (FOLDER_OCR / f"{kode}.txt").read_text(encoding="utf-8")


def rencana() -> list[tuple[str, int]]:
    """17 teks (gambar 15 kosong tidak dikirim), lalu 6 ulangan stabilitas."""
    ada = [k for k in SEMUA_KODE if re.search(r"\w", baca_ocr(k))]
    return [(k, 1) for k in ada] + [(k, 2) for k in TEKS_ULANGAN]


def taksir_token(kode_ulangan, prompt_chars: int) -> int:
    teks = samarkan(baca_ocr(kode_ulangan[0]))
    return int((prompt_chars + len(teks)) / 3.5) + 600  # + perkiraan keluaran


def cmd_anggaran(_):
    from prompt import prompt_sistem
    rc = rencana()
    n = len(rc)
    pc = len(prompt_sistem())
    tok = sum(taksir_token(r, pc) for r in rc)
    print(f"Permintaan per model: {n} (batas atas {2 * n} kalau semua perlu ulang format)")
    print(f"Perkiraan token per model: {tok} (batas atas {2 * tok})")
    for k, m in KANDIDAT.items():
        waktu = n * (m.jeda_detik + 2) / 60
        info = ""
        if m.batas:
            info = (f" | kuota harian: {2 * n}/{m.batas['rpd']} permintaan, {2 * tok}/{m.batas['tpd']} token"
                    f" ({100 * 2 * tok / m.batas['tpd']:.0f}% TPD pada batas atas)")
        print(f"- {k}: perkiraan {waktu:.0f} menit{info}")


def baca_hasil(kunci: str) -> dict:
    """Entri terakhir per (kode, ulangan)."""
    p = FOLDER_HASIL / kunci / "mentah.jsonl"
    hasil = {}
    if p.exists():
        for baris in p.read_text(encoding="utf-8").splitlines():
            if baris.strip():
                e = json.loads(baris)
                hasil[(e["kode"], e["ulangan"])] = e
    return hasil


def cmd_jalankan(a):
    m = KANDIDAT[a.model]
    kunci = muat_kunci(m)
    if not kunci:
        print(f"[{a.model}] kunci {m.env} kosong, dilewati.")
        return 0
    folder = FOLDER_HASIL / a.model
    folder.mkdir(parents=True, exist_ok=True)
    sudah = baca_hasil(a.model)
    rc = rencana()
    if a.hanya:
        rc = [r for r in rc if r[0] in a.hanya.split(",")]
    klien = Klien(m, kunci)
    print(f"[{a.model}] {len(rc)} permintaan terjadwal, jeda awal {m.jeda_detik} detik.")
    for no, (kode, ulangan) in enumerate(rc, 1):
        lama = sudah.get((kode, ulangan))
        if lama and lama["hasil"]["percobaan"][-1].get("konten") is not None and not a.ulangi:
            continue
        teks = samarkan(baca_ocr(kode))
        hasil = klien.analisis(teks)
        entri = {"kode": kode, "ulangan": ulangan, "model": m.nama, "teks_dikirim": teks, "hasil": hasil,
                 "waktu": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(folder / "mentah.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entri, ensure_ascii=False) + "\n")
        p = hasil["percobaan"][-1]
        print(f"  {no}/{len(rc)} gambar {kode}#{ulangan}: {'valid' if hasil['valid'] else 'GAGAL'}"
              f" {p.get('waktu_ms', 0)} ms, 429={hasil['n429']}, galat={len(hasil['galat'])}", flush=True)
    (folder / "pengaturan.json").write_text(
        json.dumps({"model": m.nama, "diukur": time.strftime("%Y-%m-%d"), **klien.pengaturan()}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"[{a.model}] selesai. Pengaturan akhir: {klien.pengaturan()}")
    return 0


# ---------------- ringkasan ----------------

def sumber_artikel() -> dict[str, str]:
    """kode gambar -> id numerik artikel turnbackhoax (dari url_artikel di sumber_gambar.csv)."""
    hasil = {}
    with open(SUMBER_GAMBAR, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            mm = re.search(r"/articles/(\d+)", r["url_artikel"])
            if mm:
                hasil[r["nama_file"].split(".")[0]] = mm.group(1)
    return hasil


def cari_peringkat(indeks, kueri: str, id_artikel: str):
    """(peringkat, skor sumber, skor peringkat 1, selisih 1-2). Peringkat None kalau di luar top 50."""
    hasil = indeks.cari([re.sub(r"\s+", " ", kueri).strip()], 50)[0]
    peringkat = skor = None
    for i, (art, s) in enumerate(hasil, 1):
        if id_artikel in art["url"]:
            peringkat, skor = i, s
            break
    return peringkat, skor, hasil[0][1], hasil[0][1] - hasil[1][1]


def fmt(x, d=3):
    return "-" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))


def hitung_model(kunci: str, ids_boleh) -> dict:
    h = baca_hasil(kunci)
    baris = list(h.values())
    # 429, status lain, dan galat dihitung dari SEMUA catatan (termasuk percobaan yang kemudian diulang)
    n429 = n_status_lain = n_galat = 0
    p = FOLDER_HASIL / kunci / "mentah.jsonl"
    for t in p.read_text(encoding="utf-8").splitlines():
        if t.strip():
            r = json.loads(t)["hasil"]
            n429 += r["n429"]
            n_status_lain += sum(1 for c in r["status_non200"] if c != 429)
            n_galat += len(r["galat"])
    waktu, n_valid, n_id_luar, n_id_luar_awal = [], 0, 0, 0
    ada = tot = 0
    n_ada_isi = n_tanpa_isi = 0
    tambahan = []
    klaim = {}
    for e in baris:
        r = e["hasil"]
        akhir = r["percobaan"][-1]
        if akhir.get("konten") is None:
            n_tanpa_isi += 1   # kuota habis, 503, atau jaringan: bukan kegagalan format
            continue
        n_ada_isi += 1
        n_id_luar_awal += len(r["percobaan"][0].get("id_luar") or [])
        if akhir.get("waktu_ms"):
            waktu.append(akhir["waktu_ms"])
        if r["valid"]:
            n_valid += 1
            d = r["data"]
            a_, t_ = kutipan_jujur(d, e["teks_dikirim"])
            ada += a_
            tot += t_
            kata = kata_penilaian_tambahan(d["klaim_utama"], e["teks_dikirim"])
            if kata:
                tambahan.append((e["kode"], e["ulangan"], kata))
            if e["ulangan"] == 1:
                klaim[e["kode"]] = d["klaim_utama"]
        else:
            n_id_luar += len((akhir.get("id_luar") or []))
    return {
        "n": n_ada_isi, "n_tanpa_isi": n_tanpa_isi, "n_valid": n_valid,
        "valid_pct": 100 * n_valid / n_ada_isi if n_ada_isi else 0,
        "id_luar_akhir": n_id_luar, "id_luar_awal": n_id_luar_awal,
        "kutipan_ada": ada, "kutipan_total": tot, "kejujuran_pct": 100 * ada / tot if tot else None,
        "klaim_menilai": tambahan, "median_ms": median(waktu), "p95_ms": persentil(waktu, 95),
        "n429": n429, "n_status_lain": n_status_lain, "n_galat": n_galat, "klaim": klaim, "entri": h,
    }


def stabilitas(entri: dict) -> list[dict]:
    hasil = []
    for k in TEKS_ULANGAN:
        a, b = entri.get((k, 1)), entri.get((k, 2))
        if not (a and b and a["hasil"]["valid"] and b["hasil"]["valid"]):
            hasil.append({"kode": k, "tersedia": False})
            continue
        da, db = a["hasil"]["data"], b["hasil"]["data"]
        hasil.append({
            "kode": k, "tersedia": True,
            "klaim_sama": normalisasi(da["klaim_utama"]) == normalisasi(db["klaim_utama"]),
            "jaccard": jaccard(da["klaim_utama"], db["klaim_utama"]),
            "ciri_sama": {c["id"] for c in da["ciri"]} == {c["id"] for c in db["ciri"]},
        })
    return hasil


def cmd_ringkas(a):
    from prompt import id_untuk_llm
    ids = id_untuk_llm()
    modelnya = [k for k in KANDIDAT if (FOLDER_HASIL / k / "mentah.jsonl").exists()]
    if not modelnya:
        print("Belum ada hasil.")
        return 1
    ring = {k: hitung_model(k, ids) for k in modelnya}

    # pencarian
    sys.path.insert(0, str(ALAT_CEKFAKTA))
    from embed import Indeks
    from skema import FOLDER_DB
    indeks = Indeks(FOLDER_DB, "base", "fp32")
    sumber = sumber_artikel()
    pencarian = []  # baris: gambar, sumber, model, peringkat, skor1, selisih, skor_sumber
    for g in GAMBAR_PENCARIAN:
        if g not in sumber:
            continue
        mentah = baca_ocr(g)
        r = cari_peringkat(indeks, mentah, sumber[g])
        pencarian.append((g, sumber[g], "OCR mentah", *r))
        for k in modelnya:
            kl = ring[k]["klaim"].get(g, "")
            if kl.strip():
                pencarian.append((g, sumber[g], k, *cari_peringkat(indeks, kl, sumber[g])))
            else:
                pencarian.append((g, sumber[g], k, "tanpa klaim", None, None, None))

    # CSV
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    with open(FOLDER_HASIL / "metrik.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "n_dengan_isi", "n_tanpa_isi", "valid_pct", "id_luar_akhir", "id_luar_pertama_kali", "kutipan_ada", "kutipan_total",
                    "kejujuran_pct", "klaim_menilai", "median_ms", "p95_ms", "n429", "status_lain_non200", "n_galat"])
        for k, r in ring.items():
            w.writerow([k, r["n"], r["n_tanpa_isi"], fmt(r["valid_pct"], 1), r["id_luar_akhir"], r["id_luar_awal"], r["kutipan_ada"],
                        r["kutipan_total"], fmt(r["kejujuran_pct"], 1), len(r["klaim_menilai"]),
                        fmt(r["median_ms"], 0), fmt(r["p95_ms"], 0), r["n429"], r["n_status_lain"], r["n_galat"]])
    with open(FOLDER_HASIL / "pencarian.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gambar", "id_artikel_sumber", "kueri", "peringkat_sumber", "skor_sumber", "skor_peringkat1", "selisih_1_2"])
        for g, ida, nm, per, sk, s1, sel in pencarian:
            w.writerow([g, ida, nm, per or ">50", fmt(sk), fmt(s1), fmt(sel)])
    with open(FOLDER_HASIL / "klaim_utama.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gambar"] + modelnya)
        for g in SEMUA_KODE:
            w.writerow([g] + [ring[k]["klaim"].get(g, "") for k in modelnya])

    # laporan markdown
    syarat = {}
    for k, r in ring.items():
        syarat[k] = (r["valid_pct"] >= 95 and r["id_luar_akhir"] == 0 and not r["klaim_menilai"]
                     and r["median_ms"] is not None and r["median_ms"] < 4000)
    L = []
    L.append("# Hasil Sesi 5.4a\n")
    L.append("## Metrik per model\n")
    L.append("| Model | Dengan isi (tanpa isi) | Valid % | Id luar daftar (akhir/awal) | Kejujuran kutipan | Klaim bernilai | Median ms | p95 ms | 429 | Status lain (400/503) | Galat | Lolos syarat |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, r in ring.items():
        kj = f"{r['kutipan_ada']}/{r['kutipan_total']} ({fmt(r['kejujuran_pct'], 1)}%)"
        L.append(f"| {k} | {r['n']} ({r['n_tanpa_isi']}) | {fmt(r['valid_pct'], 1)} | {r['id_luar_akhir']}/{r['id_luar_awal']} | {kj} | "
                 f"{len(r['klaim_menilai'])} | {fmt(r['median_ms'], 0)} | {fmt(r['p95_ms'], 0)} | {r['n429']} | {r['n_status_lain']} | {r['n_galat']} | "
                 f"{'ya' if syarat[k] else 'tidak'} |")
    L.append("\n## Pengaturan dipakai\n")
    L.append("| Model | Berpikir | Format keluaran | Ditolak API |")
    L.append("|---|---|---|---|")
    for k in modelnya:
        pj = FOLDER_HASIL / k / "pengaturan.json"
        p = json.loads(pj.read_text(encoding="utf-8")) if pj.exists() else {}
        L.append(f"| {k} | {p.get('berpikir')} | {p.get('format_keluaran')} | {', '.join(p.get('ditolak', [])) or '-'} |")
    L.append("\n## Klaim utama per gambar\n")
    L.append("| Gambar | " + " | ".join(modelnya) + " |")
    L.append("|---|" + "---|" * len(modelnya))
    for g in SEMUA_KODE:
        sel = [(ring[k]["klaim"].get(g) or "(kosong)").replace("|", "/").replace("\n", " ") for k in modelnya]
        L.append(f"| {g} | " + " | ".join(sel) + " |")
    L.append("\n## Manfaat untuk pencarian (e5-base fp32)\n")
    L.append("| Gambar | Kueri | Peringkat sumber | Skor sumber | Skor peringkat 1 | Selisih 1-2 |")
    L.append("|---|---|---|---|---|---|")
    for g, ida, nm, per, sk, s1, sel in pencarian:
        L.append(f"| {g} | {nm} | {per or '>50'} | {fmt(sk)} | {fmt(s1)} | {fmt(sel)} |")
    L.append("\n## Stabilitas (6 teks diulang)\n")
    L.append("| Model | Klaim sama persis | Jaccard rata-rata | Id ciri sama | Teks dibandingkan |")
    L.append("|---|---|---|---|---|")
    for k in modelnya:
        s = [x for x in stabilitas(ring[k]["entri"]) if x["tersedia"]]
        if s:
            L.append(f"| {k} | {sum(x['klaim_sama'] for x in s)}/{len(s)} | {sum(x['jaccard'] for x in s) / len(s):.2f} | "
                     f"{sum(x['ciri_sama'] for x in s)}/{len(s)} | {len(s)} |")
        else:
            L.append(f"| {k} | - | - | - | 0 |")
    L.append("\n## Klaim yang memuat kata penilaian tambahan\n")
    for k, r in ring.items():
        for kode, ul, kata in r["klaim_menilai"]:
            L.append(f"- {k}, gambar {kode}#{ul}: {', '.join(kata)}")
    (FOLDER_HASIL / "laporan.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(L))
    return 0


def main():
    p = argparse.ArgumentParser(description="Alat ukur API LLM (Sesi 5.4a)")
    s = p.add_subparsers(dest="perintah", required=True)
    s.add_parser("anggaran", help="hitung anggaran permintaan").set_defaults(f=cmd_anggaran)
    j = s.add_parser("jalankan", help="ukur satu model")
    j.add_argument("--model", required=True, choices=list(KANDIDAT))
    j.add_argument("--hanya", help="kode gambar dipisah koma, untuk uji kecil (misalnya 09,10)")
    j.add_argument("--ulangi", action="store_true", help="kirim ulang juga yang sudah punya keluaran")
    j.set_defaults(f=cmd_jalankan)
    s.add_parser("ringkas", help="metrik, tabel klaim, pencarian, stabilitas").set_defaults(f=cmd_ringkas)
    a = p.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
