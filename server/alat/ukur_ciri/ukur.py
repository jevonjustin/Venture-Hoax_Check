"""Membandingkan detektor regex dan klaim heuristik dengan hasil gpt-oss-120b tersimpan (Sesi 5.4).

Dijalankan dari folder server dengan venv server (.venv). Tidak memanggil API apa pun: yang dipakai hanya
keluaran LLM yang sudah tersimpan di data_lokal\\hasil_llm\\gpt-oss-120b\\mentah.jsonl.

    .venv\\Scripts\\python alat\\ukur_ciri\\ukur.py

Menulis data_lokal\\hasil_ciri\\laporan.md:
  1. Per gambar: ciri regex (dengan kekuatan pola) dan ciri yang ditandai LLM.
  2. Per ciri: berapa kali regex kuat, regex lemah, LLM, dan yang sama-sama menemukan.
  3. Hasil penggabungan (kutipan LLM diverifikasi terhadap teks) untuk LLM berhasil dan LLM gagal (None).
  4. Klaim utama heuristik berdampingan dengan klaim_utama LLM, termasuk teks yang klaim LLM-nya kosong.

Pengukuran salah tandai pada teks berlabel (dataset Ghazi) belum ada: dataset itu belum diunduh dan tiga dataset
Kaggle yang ada hanya berisi artikel cek fakta, bukan teks berlabel bukan hoaks.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER))

from app.pipeline import ciri, klaim  # noqa: E402
from app.pipeline.tipe import KandidatLLM  # noqa: E402

DATA_LOKAL = SERVER / "data_lokal"
MENTAH_LLM = DATA_LOKAL / "hasil_llm" / "gpt-oss-120b" / "mentah.jsonl"
KLAIM_CSV = DATA_LOKAL / "hasil_llm" / "klaim_utama.csv"
HASIL_BERSIH = DATA_LOKAL / "hasil_bersih"
FOLDER_HASIL = DATA_LOKAL / "hasil_ciri"
KOLOM_LLM = "gpt-oss-120b"


def muat_llm() -> dict[str, dict]:
    """kode gambar -> {"teks": teks yang dikirim ke LLM, "klaim": str, "ciri": [KandidatLLM]} (ulangan pertama yang valid)."""
    hasil: dict[str, dict] = {}
    for baris in MENTAH_LLM.read_text(encoding="utf-8").splitlines():
        r = json.loads(baris)
        data = (r.get("hasil") or {}).get("data")
        if r["kode"] in hasil or not (r.get("hasil") or {}).get("valid") or not data:
            continue
        hasil[r["kode"]] = {
            "teks": r["teks_dikirim"],
            "klaim": data.get("klaim_utama", ""),
            "ciri": [KandidatLLM(c["id"], list(c["kutipan"])) for c in data.get("ciri", [])],
        }
    return hasil


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not MENTAH_LLM.exists():
        print(f"{MENTAH_LLM} tidak ada.", file=sys.stderr)
        return 2
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    llm = muat_llm()
    L = ["# Laporan ukur_ciri (Sesi 5.4)", "",
         f"Teks yang dipakai: {len(llm)} teks OCR dari Sesi 5.4a (yang dikirim ke gpt-oss-120b, data pribadi sudah disamarkan). "
         "Ini perbandingan, bukan akurasi: tidak ada label ciri yang benar untuk gambar-gambar ini.", ""]
    hitung = {i: Counter() for i in ciri.ID_BISA_DITANDAI}

    L += ["## 1. Ciri per gambar: regex (kekuatan) dan gpt-oss-120b", "", "| Gambar | Regex | gpt-oss-120b | Sama |", "|---|---|---|---|"]
    gabungan = {}
    for kode in sorted(llm):
        teks = llm[kode]["teks"]
        regex = ciri.deteksi_regex(teks)
        id_regex = {c.id: c for c in regex}
        id_llm = {c.id for c in llm[kode]["ciri"]}
        for i in ciri.ID_BISA_DITANDAI:
            c = id_regex.get(i)
            if c:
                hitung[i]["regex_" + c.kekuatan] += 1
            if i in id_llm:
                hitung[i]["llm"] += 1
            if c and i in id_llm:
                hitung[i]["sama"] += 1
        sama = sorted(set(id_regex) & id_llm)
        L.append(f"| {kode} | {', '.join(f'{c.id} ({c.kekuatan})' for c in regex) or '-'} | {', '.join(sorted(id_llm)) or '-'} | {', '.join(sama) or '-'} |")
        gabungan[kode] = (
            ciri.gabung_ciri(regex, llm[kode]["ciri"], teks),
            ciri.gabung_ciri(regex, None, teks),
            [(k.id, q) for k in llm[kode]["ciri"] for q in k.kutipan if ciri._kutipan_asli(teks, q) is None],
        )

    L += ["", "## 2. Rekap per ciri", "", "| Ciri | Regex kuat | Regex lemah | LLM | Regex dan LLM sama |", "|---|---|---|---|---|"]
    for i, c in hitung.items():
        L.append(f"| {i} | {c['regex_kuat']} | {c['regex_lemah']} | {c['llm']} | {c['sama']} |")

    L += ["", "## 3. Hasil penggabungan", "",
          "Kolom \"LLM berhasil\" memakai ciri dan kutipan gpt-oss-120b yang tersimpan (kutipan diverifikasi terhadap teks). "
          "Kolom \"LLM gagal\" adalah hasil regex saja.", "",
          "| Gambar | LLM berhasil | LLM gagal (None) | Kutipan LLM tak terverifikasi |", "|---|---|---|---|"]
    for kode, (berhasil, gagal, tak_terverifikasi) in gabungan.items():
        f = lambda daftar: ", ".join(f"{c.id} ({c.keyakinan})" for c in daftar) or "-"
        L.append(f"| {kode} | {f(berhasil)} | {f(gagal)} | {len(tak_terverifikasi)} |")
    total_tak = sum(len(g[2]) for g in gabungan.values())
    L += ["", f"Kutipan LLM yang tidak ditemukan di teks (setelah normalisasi dasar): {total_tak}."]
    for kode, (_, _, tak) in gabungan.items():
        for i, q in tak:
            L.append(f"- {kode} {i}: {q}")

    L += ["", "## 4. Klaim utama: heuristik (dari teks bersih) dan gpt-oss-120b", ""]
    with open(KLAIM_CSV, encoding="utf-8-sig", newline="") as f:
        klaim_llm = {r["gambar"]: r[KOLOM_LLM] for r in csv.DictReader(f)}
    L += ["| Gambar | Heuristik | gpt-oss-120b |", "|---|---|---|"]
    kosong_llm, heuristik_ada = [], 0
    for kode in sorted(klaim_llm):
        berkas = HASIL_BERSIH / f"{kode}.json"
        if not berkas.exists():
            continue
        teks_bersih = json.loads(berkas.read_text(encoding="utf-8"))["varian"]["bawaan"]["teks"]
        bukti = [b for c in ciri.deteksi_regex(teks_bersih) for b in c.bukti]
        h = klaim.klaim_heuristik(teks_bersih, bukti)
        heuristik_ada += bool(h)
        if not klaim_llm[kode]:
            kosong_llm.append((kode, h))
        L.append(f"| {kode} | {h or '(kosong)'} | {klaim_llm[kode] or '(kosong)'} |")
    L += ["", f"Heuristik menghasilkan klaim untuk {heuristik_ada} dari {len(klaim_llm)} gambar.",
          "", "Gambar yang klaim LLM-nya kosong dan klaim heuristiknya:", ""]
    L += [f"- {k}: {h or '(kosong)'}" for k, h in kosong_llm] or ["- (tidak ada)"]
    (FOLDER_HASIL / "laporan.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Laporan: {FOLDER_HASIL / 'laporan.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
