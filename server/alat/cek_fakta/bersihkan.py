"""Membersihkan tbh_artikel.jsonl: membuang baris rusak dan duplikat URL, dengan cadangan berkas lama.

Dijalankan hanya saat tidak ada pengumpul yang berjalan (diperiksa otomatis). Berkas lama disalin dulu ke
tbh_artikel.jsonl.cadangan-WAKTU; tbh_checkpoint.json tidak disentuh.

Untuk tiap URL dipilih salinan terbaik: tanpa tanda galat, lalu punya hasil_periksa, lalu punya label_asli,
lalu narasi terpanjang, lalu yang paling akhir diambil. Urutan akhir mengikuti kemunculan pertama tiap URL.
"""

import argparse
import datetime
import json
import os
import shutil
import sys
from pathlib import Path

from kumpul_tbh import proses_pengumpul_lain
from skema import FOLDER_DB, tanggal_iso


def nilai(d: dict) -> tuple:
    return (not d.get("galat"), bool(d.get("hasil_periksa")), bool(d.get("label_asli")), len(d.get("narasi") or ""),
            d.get("diambil") or "")


def bersihkan_baris(baris: list[bytes]) -> tuple[list[dict], dict]:
    """Mengembalikan (rekaman terpilih, statistik).

    Yang dibuang hanya baris yang bukan JSON utuh ("rusak"), baris tanpa url atau judul, dan duplikat URL.
    Baris tanpa narasi tetap dipakai (masih bisa dicari lewat judul). Baris tanpa tanggal, atau dengan tanggal
    yang bukan tanggal sungguhan (misalnya 0000-00-00), tetap dipakai dengan tanggal None.
    """
    stat = {"baris": len(baris), "rusak": 0, "url_hilang": 0, "judul_hilang": 0, "duplikat_dibuang": 0,
            "tanggal_kosong": 0, "tanggal_diperbaiki_ke_null": 0, "narasi_kosong": 0}
    urutan: list[str] = []
    terbaik: dict[str, dict] = {}
    for b in baris:
        if not b.strip():
            continue
        try:
            d = json.loads(b.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            stat["rusak"] += 1
            continue
        if not isinstance(d, dict):
            stat["rusak"] += 1
            continue
        if not (d.get("url") or "").strip():
            stat["url_hilang"] += 1
            continue
        if not (d.get("judul") or "").strip():
            stat["judul_hilang"] += 1
            continue
        mentah = d.get("tanggal")
        tanggal = tanggal_iso(mentah)
        if mentah and not tanggal:
            stat["tanggal_diperbaiki_ke_null"] += 1
        d["tanggal"] = tanggal
        d.setdefault("narasi", "")
        u = d["url"]
        if u not in terbaik:
            urutan.append(u)
            terbaik[u] = d
        else:
            stat["duplikat_dibuang"] += 1
            if nilai(d) > nilai(terbaik[u]):
                terbaik[u] = d
    stat["unik"] = len(urutan)
    stat["galat_tersisa"] = sum(1 for u in urutan if terbaik[u].get("galat"))
    stat["tanggal_kosong"] = sum(1 for u in urutan if not terbaik[u]["tanggal"])
    stat["narasi_kosong"] = sum(1 for u in urutan if not terbaik[u].get("narasi"))
    return [terbaik[u] for u in urutan], stat


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Bersihkan tbh_artikel.jsonl (buang baris rusak dan duplikat)")
    p.add_argument("--folder", type=Path, default=FOLDER_DB)
    p.add_argument("--hanya-lapor", action="store_true", help="hanya hitung dan laporkan, tanpa menulis apa pun")
    p.add_argument("--abaikan-pengumpul", action="store_true", help="khusus uji pada salinan; jangan dipakai pada data asli")
    a = p.parse_args()

    if not a.abaikan_pengumpul:
        lain = proses_pengumpul_lain()
        if lain:
            print(f"DITOLAK: pengumpul masih berjalan (PID {', '.join(map(str, lain))}). Tunggu sampai selesai.", file=sys.stderr)
            return 4
        if (a.folder / "tbh.lock").exists():
            print(f"DITOLAK: {a.folder / 'tbh.lock'} ada. Pastikan pengumpul sudah berhenti, lalu hapus berkas itu.", file=sys.stderr)
            return 4

    jalur = a.folder / "tbh_artikel.jsonl"
    mentah = jalur.read_bytes()
    baris = mentah.split(b"\n")
    if baris and baris[-1] == b"":
        baris.pop()
    terpilih, stat = bersihkan_baris(baris)
    print(f"Baris dibaca: {stat['baris']}")
    print(f"Dibuang: rusak={stat['rusak']}, url hilang={stat['url_hilang']}, judul hilang={stat['judul_hilang']}, "
          f"duplikat={stat['duplikat_dibuang']}")
    print(f"Dipertahankan: URL unik={stat['unik']} (narasi kosong={stat['narasi_kosong']}, tanggal kosong atau tidak sah="
          f"{stat['tanggal_kosong']} [diperbaiki ke null={stat['tanggal_diperbaiki_ke_null']}], rekaman galat={stat['galat_tersisa']})")
    if a.hanya_lapor:
        return 0

    cadangan = jalur.with_name(f"{jalur.name}.cadangan-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(jalur, cadangan)
    if cadangan.stat().st_size != len(mentah):
        print("Cadangan tidak utuh; dibatalkan.", file=sys.stderr)
        return 1
    print(f"Cadangan: {cadangan}")
    sementara = jalur.with_name(jalur.name + ".bersih.tmp")
    with open(sementara, "w", encoding="utf-8", newline="\n") as f:
        for d in terpilih:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    os.replace(sementara, jalur)
    print(f"Ditulis {len(terpilih)} baris ke {jalur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
