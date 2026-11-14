"""Evaluasi kecil Gemini sebagai cadangan LLM (Sesi 8.2). MEMANGGIL API Gemini (paling banyak --maks-panggilan).

Mengambil 10 gambar set uji beku (campuran positif dan negatif) yang sudah punya cache OCR dan cache Groq dari
evaluasi Sesi 5.6, lalu mengirim teks yang SUDAH disamarkan (samarkan.samarkan, sama seperti orkestrator) ke
Gemini dengan badan permintaan produksi (llm._badan) dan batas waktu produksi. Groq tidak dipanggil: hasil Groq
dibaca dari cache. Ciri dan klaim kedua penyedia dinilai dengan pemeriksaan produksi yang sama:
- llm.petakan_kandidat: kutipan yang tidak ada di teks (ciri karangan) ditolak;
- ciri.gabung_ciri: ciri final bersama regex, beserta kutipan yang dibuang pengaman struktural;
- llm.alasan_klaim_ditolak: pemeriksaan kesetiaan klaim (profil ambang aktif).

Gambar dan cache Sesi 5.6 hanya dibaca. Hasil Gemini dan laporan (memuat teks klaim, jadi tetap lokal) ditulis ke
server\\data_lokal\\uji_hp\\tahap8\\. Hasil Gemini di-cache di sana, jadi menjalankan ulang tidak memanggil API lagi.

Pakai (dari folder server):
  .venv\\Scripts\\python.exe alat\\uji_analisis\\banding_gemini.py --periksa      # pilih gambar saja, tanpa API
  .venv\\Scripts\\python.exe alat\\uji_analisis\\banding_gemini.py --maks-panggilan 12
"""

import argparse
import asyncio
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import konfigurasi  # noqa: E402
from app.pipeline import ciri, llm, samarkan  # noqa: E402
from app.pipeline.tipe import KandidatLLM  # noqa: E402

EVAL = konfigurasi.DATA_LOKAL / "evaluasi"
KELUAR = konfigurasi.DATA_LOKAL / "uji_hp" / "tahap8"
CACHE_GEMINI = KELUAR / "gemini_cache.json"
LAPORAN = KELUAR / "banding_gemini.md"
KOMPOSISI = {"kuat": 3, "hati_hati": 3, "tidak_ditemukan": 4}
JEDA_MIN = 8.0


def sha_teks(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def baca(jalur: Path):
    try:
        return json.loads(jalur.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def prompt_sha(penyedia) -> str:
    badan = llm._badan(penyedia, "", konfigurasi.pengaturan)
    return sha_teks(json.dumps(badan, sort_keys=True, ensure_ascii=False))[:16]


def pilih_gambar() -> list[dict]:
    """Gambar uji pertama (urut id) per label yang punya cache OCR dan cache Groq dengan teks dan prompt sama."""
    with open(EVAL / "metadata.csv", encoding="utf-8") as f:
        baris = [b for b in csv.DictReader(f) if b["set"] == "uji"]
    psha = prompt_sha(llm.GROQ)
    terpilih, jumlah = [], Counter()
    for b in sorted(baris, key=lambda b: b["id"]):
        label = b["label_harapan"]
        if jumlah[label] >= KOMPOSISI.get(label, 0):
            continue
        sha_gambar = hashlib.sha256((EVAL / "gambar" / b["berkas"]).read_bytes()).hexdigest()
        ocr = baca(EVAL / "cache" / "ocr" / f"{sha_gambar}.json")
        groq = baca(EVAL / "cache" / "llm" / f"{sha_gambar}.json")
        if not ocr or not groq or "1" not in groq.get("jalan", {}):
            continue
        teks = ocr["teks_bersih"]
        samar = samarkan.samarkan(teks)
        if groq["kunci"].get("teks_sha") != sha_teks(samar) or groq["kunci"].get("prompt_sha") != psha:
            continue
        jumlah[label] += 1
        terpilih.append({"id": b["id"], "label": label, "teks": teks, "samar": samar, "groq": groq["jalan"]["1"]})
    return terpilih


class TransportBerbatas:
    """transport_urllib produksi dengan jeda minimal dan batas jumlah panggilan; hanya Gemini."""

    def __init__(self, maks: int, jeda: float):
        self.maks, self.jeda, self.dipakai, self.terakhir = maks, jeda, 0, 0.0

    def __call__(self, penyedia, badan, kunci, timeout):
        if penyedia.nama != llm.GEMINI.nama:
            raise llm.GagalJaringan
        if self.dipakai >= self.maks:
            raise llm.GagalJaringan
        tunggu = self.terakhir + self.jeda - time.monotonic()
        if tunggu > 0:
            time.sleep(tunggu)
        self.dipakai += 1
        try:
            return llm.transport_urllib(penyedia, badan, kunci, timeout)
        finally:
            self.terakhir = time.monotonic()


async def panggil_gemini(samar: str, transport: TransportBerbatas) -> tuple[dict | None, list]:
    cfg = konfigurasi.pengaturan
    kunci = llm.muat_kunci(llm.GEMINI.env)
    if not kunci:
        raise SystemExit("GEMINI_API_KEY belum diisi (variabel lingkungan atau server/.env).")
    jejak: list = []
    t0 = time.monotonic()
    # Jeda transport tidak boleh memakan anggaran waktu produksi: jeda dilakukan sebelum mulai dihitung.
    tunggu = transport.terakhir + transport.jeda - time.monotonic()
    if tunggu > 0:
        await asyncio.sleep(tunggu)
    mulai = time.monotonic()
    hasil = await llm._coba_penyedia(
        llm.GEMINI, kunci, samar, cfg, transport, mulai, cfg.llm_timeout_gemini, jejak,
    )
    jejak_ringkas = [{k: v for k, v in j.items() if k in ("status", "ms", "kode", "token")} for j in jejak]
    if hasil is None:
        return None, jejak_ringkas
    return {
        "klaim_utama": hasil.klaim_utama,
        "kandidat": [{"id": k.id, "kutipan": list(k.kutipan)} for k in hasil.kandidat],
        "durasi_ms": int((time.monotonic() - mulai) * 1000),
        "percobaan": hasil.percobaan,
        "waktu_total_ms": int((time.monotonic() - t0) * 1000),
    }, jejak_ringkas


def nilai(hasil: dict | None, g: dict) -> dict:
    """Menilai hasil satu penyedia dengan pemeriksaan produksi."""
    regex = ciri.deteksi_regex(g["teks"])
    if hasil is None:
        final = ciri.gabung_ciri(regex, None, g["teks"])
        return {"gagal": True, "ciri_final": [c.id for c in final]}
    kandidat = [KandidatLLM(c["id"], list(c["kutipan"])) for c in hasil["kandidat"]]
    sah, ditolak = llm.petakan_kandidat(kandidat, g["samar"], g["teks"])
    catatan: list = []
    final = ciri.gabung_ciri(regex, sah, g["teks"], catatan=catatan)
    alasan = llm.alasan_klaim_ditolak(hasil["klaim_utama"], g["samar"])
    return {
        "gagal": False,
        "usulan": sorted(c.id for c in kandidat),
        "kutipan_total": sum(len(c.kutipan) for c in kandidat),
        "kutipan_karangan": ditolak,
        "ciri_karangan": sorted({c.id for c in kandidat} - {c.id for c in sah}),
        "dibuang_pengaman": sorted({c["id"] for c in catatan}),
        "ciri_final": [c.id for c in final],
        "klaim": hasil["klaim_utama"],
        "klaim_ditolak": alasan[0] if alasan else None,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--periksa", action="store_true", help="hanya pilih gambar; tanpa API")
    p.add_argument("--maks-panggilan", type=int, default=12)
    p.add_argument("--jeda", type=float, default=JEDA_MIN)
    a = p.parse_args(argv)
    if a.jeda < JEDA_MIN:
        raise SystemExit(f"--jeda minimal {JEDA_MIN} detik")

    gambar = pilih_gambar()
    print("Profil ambang:", konfigurasi.pengaturan.profil_ambang, "| model Gemini:", llm.GEMINI.model)
    print("Gambar:", ", ".join(f"{g['id']}({g['label']})" for g in gambar))
    if len(gambar) < sum(KOMPOSISI.values()):
        print("Peringatan: gambar dengan cache lengkap kurang dari target.")
    if a.periksa:
        return 0

    KELUAR.mkdir(parents=True, exist_ok=True)
    cache = baca(CACHE_GEMINI) or {}
    transport = TransportBerbatas(a.maks_panggilan, a.jeda)
    for g in gambar:
        kunci = sha_teks(g["samar"]) + ":" + prompt_sha(llm.GEMINI)
        if kunci in cache:
            continue
        if transport.dipakai >= transport.maks:
            print("Batas panggilan tercapai; sisa gambar dilewati.")
            break
        hasil, jejak = asyncio.run(panggil_gemini(g["samar"], transport))
        cache[kunci] = {"id": g["id"], "hasil": hasil, "jejak": jejak}
        CACHE_GEMINI.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        status = "ok" if hasil else "gagal"
        print(f"  {g['id']}: gemini {status}, percobaan HTTP {[j['status'] for j in jejak]}, "
              f"{[j['ms'] for j in jejak]} ms")
    print(f"Panggilan Gemini sesi ini: {transport.dipakai}")

    baris_md = [
        "# Banding Groq (cache Sesi 5.6) dan Gemini (Sesi 8.2)", "",
        f"Profil ambang `{konfigurasi.pengaturan.profil_ambang}`, Gemini `{llm.GEMINI.model}`, "
        f"batas waktu Gemini {konfigurasi.pengaturan.llm_timeout_gemini} detik. Berkas ini memuat teks klaim: tetap lokal.", "",
        "| id | label | regex | Groq: ciri final | Gemini: ciri final | Groq karangan | Gemini karangan | "
        "Groq klaim ditolak | Gemini klaim ditolak | Gemini ms |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    ringkas = Counter()
    rinci = []
    for g in gambar:
        entri = cache.get(sha_teks(g["samar"]) + ":" + prompt_sha(llm.GEMINI))
        if entri is None:
            continue
        regex_ids = sorted(c.id for c in ciri.deteksi_regex(g["teks"]))
        ng, nm = nilai(g["groq"], g), nilai(entri["hasil"], g)
        ringkas["gambar"] += 1
        ringkas["gemini_gagal"] += nm["gagal"]
        if not nm["gagal"]:
            ringkas["sama_ciri_final"] += ng["ciri_final"] == nm["ciri_final"]
            ringkas["groq_kutipan_karangan"] += ng["kutipan_karangan"]
            ringkas["gemini_kutipan_karangan"] += nm["kutipan_karangan"]
            ringkas["groq_kutipan"] += ng["kutipan_total"]
            ringkas["gemini_kutipan"] += nm["kutipan_total"]
            ringkas["groq_klaim_ditolak"] += ng["klaim_ditolak"] is not None
            ringkas["gemini_klaim_ditolak"] += nm["klaim_ditolak"] is not None
        ms = entri["hasil"]["durasi_ms"] if entri["hasil"] else "-"
        baris_md.append(
            f"| {g['id']} | {g['label']} | {', '.join(regex_ids) or '-'} | {', '.join(ng['ciri_final']) or '-'} | "
            f"{'GAGAL' if nm['gagal'] else ', '.join(nm['ciri_final']) or '-'} | "
            f"{ng['kutipan_karangan']}/{ng['kutipan_total']} {','.join(ng['ciri_karangan'])} | "
            f"{'-' if nm['gagal'] else str(nm['kutipan_karangan']) + '/' + str(nm['kutipan_total']) + ' ' + ','.join(nm['ciri_karangan'])} | "
            f"{ng['klaim_ditolak'] or '-'} | {'-' if nm['gagal'] else nm['klaim_ditolak'] or '-'} | {ms} |"
        )
        rinci += [f"## {g['id']} ({g['label']})", "", f"- Groq klaim: {ng['klaim']}",
                  f"- Gemini klaim: {'(gagal)' if nm['gagal'] else nm['klaim']}",
                  f"- Usulan ciri Groq: {', '.join(ng['usulan']) or '-'}; dibuang pengaman: {', '.join(ng['dibuang_pengaman']) or '-'}",
                  f"- Usulan ciri Gemini: {'-' if nm['gagal'] else ', '.join(nm['usulan']) or '-'}; dibuang pengaman: "
                  f"{'-' if nm['gagal'] else ', '.join(nm['dibuang_pengaman']) or '-'}",
                  f"- Jejak Gemini: {entri['jejak']}", ""]
    baris_md += ["", "## Ringkasan", ""] + [f"- {k}: {v}" for k, v in ringkas.items()] + [""] + rinci
    LAPORAN.write_text("\n".join(baris_md), encoding="utf-8")
    print("Ringkasan:", dict(ringkas))
    print("Laporan:", LAPORAN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
