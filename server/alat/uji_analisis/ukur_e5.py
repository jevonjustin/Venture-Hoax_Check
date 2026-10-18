"""Mengukur e5 (Sesi 5.6): waktu muat model, latensi per kueri (median, p90), dan RAM proses untuk kombinasi
{fp32, int8} x panjang token kueri {256, 512}. Hasil ditulis ke markdown yang diberi path.

Tidak ada jaringan dan tidak ada LLM. Kueri dibaca dari cache OCR alat evaluasi (cache\\ocr\\*.json; dipakai
teks_bersih bila ada, selain itu teks) atau dari berkas teks (satu kueri per baris, --kueri-berkas). Isi kueri
tidak pernah dicetak atau ditulis ke laporan; hanya jumlah dan angka.

Tiap kombinasi diukur di proses anak tersendiri supaya RAM tidak bercampur antar model. RAM = working set proses
setelah model (dan vektor, bila diberi) dimuat dan semua kueri dijalankan, dikurangi working set sebelum memuat.
Model int8 hasil kuantisasi lokal diberikan lewat --model-int8 (dan --vektor-int8); model_qint8_avx512_vnni.onnx
hanya dipakai bila path-nya diberikan eksplisit, dan dicatat lewat --label-int8.

Contoh (dari folder server):
  .venv\\Scripts\\python alat\\uji_analisis\\ukur_e5.py --keluaran data_lokal\\hasil_ukur\\ukur_e5.md
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER))

from app.pipeline import cocok  # noqa: E402

DATA_LOKAL = SERVER / "data_lokal"
EVALUASI = DATA_LOKAL / "evaluasi"
MODEL_FP32 = DATA_LOKAL / "model" / "e5-base" / "model.onnx"
TOKENIZER = DATA_LOKAL / "model" / "e5-base" / "tokenizer.json"
VEKTOR_FP32 = DATA_LOKAL / "cek_fakta" / "vektor_base_fp32.npy"
MAKS_POSISI = 512  # batas posisi e5-base


class GalatUkur(Exception):
    """Kesalahan pemakaian; pesannya siap dicetak."""


def baca_kueri(cache_ocr: Path | None, berkas: Path | None, maks: int | None) -> list[str]:
    kueri: list[str] = []
    if berkas:
        kueri = [cocok.rapikan_kueri(b) for b in berkas.read_text(encoding="utf-8").splitlines()]
    elif cache_ocr:
        for jalur in sorted(cache_ocr.glob("*.json")):
            try:
                d = json.loads(jalur.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(d, dict):
                kueri.append(cocok.rapikan_kueri(str(d.get("teks_bersih") or d.get("teks") or "")))
    kueri = [k for k in kueri if k]
    if maks:
        kueri = kueri[:maks]
    if not kueri:
        raise GalatUkur("tidak ada kueri (cache OCR kosong atau berkas teks kosong)")
    return kueri


def persentil(nilai: list[float], p: float) -> float:
    urut = sorted(nilai)
    return urut[min(len(urut) - 1, int(round(p * (len(urut) - 1))))]


def ukur_satu(model: Path, vektor: Path | None, maks_token: int, kueri: list[str], tokenizer: Path = TOKENIZER) -> dict:
    """Satu kombinasi di proses ini. Mengembalikan angka mentah (detik, milidetik, MB)."""
    import numpy as np  # noqa: F401  (dipakai onnxruntime/tokenizers dan np.load)

    ram_awal = cocok.ram_proses_mb()
    mulai = time.perf_counter()
    emb = cocok.EmbedderE5(model, tokenizer, maks_token)
    detik_model = time.perf_counter() - mulai
    detik_vektor = 0.0
    if vektor:
        import numpy as np

        mulai = time.perf_counter()
        np.load(vektor)
        detik_vektor = time.perf_counter() - mulai
    # Berapa kueri yang terpotong pada batas ini (tokenizer tanpa pemotongan).
    tok_penuh = emb.tok
    tok_penuh.no_truncation()
    panjang = [len(e.ids) for e in tok_penuh.encode_batch(["query: " + k for k in kueri])]
    tok_penuh.enable_truncation(max_length=maks_token)
    emb.encode_kueri([kueri[0]])  # pemanasan, tidak dihitung
    ms = []
    for k in kueri:
        t0 = time.perf_counter()
        emb.encode_kueri([k])
        ms.append((time.perf_counter() - t0) * 1000)
    ram_akhir = cocok.ram_proses_mb()
    return {
        "detik_model": detik_model, "detik_vektor": detik_vektor, "n": len(kueri),
        "median_ms": statistics.median(ms), "p90_ms": persentil(ms, 0.9), "maks_ms": max(ms),
        "terpotong": sum(p > maks_token for p in panjang), "median_token": statistics.median(panjang),
        "ram_mb": (ram_akhir - ram_awal) if ram_awal is not None and ram_akhir is not None else None,
    }


def jalankan_anak(varian: str, model: Path, vektor: Path | None, maks_token: int, sumber: list[str]) -> dict:
    perintah = [sys.executable, str(Path(__file__).resolve()), "--satu", "--model", str(model),
                "--maks-token", str(maks_token), *sumber]
    if vektor:
        perintah += ["--vektor", str(vektor)]
    hasil = subprocess.run(perintah, capture_output=True, text=True, encoding="utf-8")
    if hasil.returncode != 0:
        raise GalatUkur(f"pengukuran {varian}/{maks_token} gagal: {hasil.stderr.strip().splitlines()[-1:] or ['?']}")
    return json.loads(hasil.stdout.strip().splitlines()[-1])


def fmt(x, nd=1) -> str:
    return "-" if x is None else f"{x:.{nd}f}".replace(".", ",")


def tulis_laporan(jalur: Path, baris: list[tuple[str, int, dict]], catatan: list[str]) -> None:
    teks = [
        "# Pengukuran e5-base (waktu muat, latensi kueri, RAM)", "",
        f"- Waktu: {time.strftime('%Y-%m-%d %H:%M:%S')}; kueri: {baris[0][2]['n']} (isi tidak dicetak)",
        "- Latensi = satu kueri per panggilan (tanpa batch), satu thread proses tersendiri, setelah satu pemanasan.",
        "- RAM = tambahan working set proses (model + vektor bila diberi + semua kueri).", *catatan, "",
        "| varian | token kueri | muat model (dtk) | muat vektor (dtk) | median (ms) | p90 (ms) | maks (ms) | "
        "kueri terpotong | median token | RAM (MB) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for varian, mt, r in baris:
        teks.append(
            f"| {varian} | {mt} | {fmt(r['detik_model'], 2)} | {fmt(r['detik_vektor'], 2)} | {fmt(r['median_ms'])} | "
            f"{fmt(r['p90_ms'])} | {fmt(r['maks_ms'])} | {r['terpotong']}/{r['n']} | {fmt(r['median_token'], 0)} | "
            f"{fmt(r['ram_mb'], 0)} |"
        )
    teks.append("")
    jalur.parent.mkdir(parents=True, exist_ok=True)
    jalur.write_text("\n".join(teks), encoding="utf-8")


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--keluaran", help="path markdown hasil (wajib kecuali --satu)")
    p.add_argument("--cache-ocr", default=str(EVALUASI / "cache" / "ocr"), help="folder cache OCR alat evaluasi")
    p.add_argument("--kueri-berkas", default=None, help="berkas teks, satu kueri per baris (menggantikan cache OCR)")
    p.add_argument("--maks-kueri", type=int, default=None, help="batasi jumlah kueri")
    p.add_argument("--varian", default="fp32,int8", help="bagian dari fp32,int8")
    p.add_argument("--token", default="256,512", help="panjang token kueri, dipisah koma (maks 512)")
    p.add_argument("--model-fp32", default=str(MODEL_FP32))
    p.add_argument("--vektor-fp32", default=str(VEKTOR_FP32), help="path vektor fp32 ('' = tidak dimuat)")
    p.add_argument("--model-int8", default=None, help="path model ONNX int8 (wajib bila varian int8 diukur)")
    p.add_argument("--vektor-int8", default=None, help="path vektor int8 .npy (opsional, ikut dimuat)")
    p.add_argument("--label-int8", default="kuantisasi dinamis lokal", help="catatan asal model int8 untuk laporan")
    p.add_argument("--satu", action="store_true", help="(internal) ukur satu kombinasi, cetak JSON")
    p.add_argument("--model", help="(internal) dengan --satu")
    p.add_argument("--vektor", default=None, help="(internal) dengan --satu")
    p.add_argument("--maks-token", type=int, default=256, help="(internal) dengan --satu")
    return p


def main(argv: list[str] | None = None) -> int:
    a = buat_parser().parse_args(argv)
    try:
        kueri = baca_kueri(None if a.kueri_berkas else Path(a.cache_ocr), Path(a.kueri_berkas) if a.kueri_berkas else None, a.maks_kueri)
        if a.satu:
            print(json.dumps(ukur_satu(Path(a.model), Path(a.vektor) if a.vektor else None, a.maks_token, kueri)))
            return 0
        if not a.keluaran:
            raise GalatUkur("--keluaran wajib")
        varian = [v.strip() for v in a.varian.split(",") if v.strip()]
        panjang = [int(t) for t in a.token.split(",") if t.strip()]
        if not set(varian) <= {"fp32", "int8"} or not varian:
            raise GalatUkur("--varian harus bagian dari fp32,int8")
        if any(not 1 <= t <= MAKS_POSISI for t in panjang):
            raise GalatUkur(f"--token harus 1..{MAKS_POSISI}")
        if "int8" in varian and not a.model_int8:
            raise GalatUkur("varian int8 butuh --model-int8 (path ONNX); model hasil kuantisasi lokal dibuat kuantisasi_e5.py")
        sumber = ["--kueri-berkas", a.kueri_berkas] if a.kueri_berkas else ["--cache-ocr", a.cache_ocr]
        if a.maks_kueri:
            sumber += ["--maks-kueri", str(a.maks_kueri)]
        pilihan = {
            "fp32": (Path(a.model_fp32), Path(a.vektor_fp32) if a.vektor_fp32 else None),
            "int8": (Path(a.model_int8) if a.model_int8 else None, Path(a.vektor_int8) if a.vektor_int8 else None),
        }
        for v in varian:
            for berkas in pilihan[v]:
                if berkas and not berkas.exists():
                    raise GalatUkur(f"berkas tidak ditemukan: {berkas}")
        baris = []
        for v in varian:
            for t in panjang:
                print(f"mengukur {v} token={t} ...", flush=True)
                baris.append((v, t, jalankan_anak(v, pilihan[v][0], pilihan[v][1], t, sumber)))
        catatan = []
        if "int8" in varian:
            catatan.append(f"- Model int8: {Path(a.model_int8).name} ({a.label_int8}).")
        tulis_laporan(Path(a.keluaran), baris, catatan)
        print(f"laporan ditulis: {a.keluaran}")
        return 0
    except GalatUkur as e:
        print(f"DITOLAK: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
