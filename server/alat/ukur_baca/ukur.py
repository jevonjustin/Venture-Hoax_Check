"""Mengukur waktu dan CER pembaca teks pada screenshot uji (Sesi 5.2).

Dijalankan dari folder server (lihat README.md untuk perintah lengkap):

    ukur.py jalankan KANDIDAT [--ulang N]   menjalankan satu kandidat (memanggil model)
    ukur.py hitung-ulang [KANDIDAT ...]     menghitung ulang metrik dari teks tersimpan, tanpa model
    ukur.py ringkas                         rata-rata per kandidat (semua gambar dan tanpa 08)
    ukur.py kata-tak-terbaca                kata acuan yang tidak terbaca oleh satu pun kandidat
    ukur.py daftar                          nama kandidat yang dikenal

Semua gambar diproses di memori lewat praproses.py. Hasil mentah (teks tiap kandidat per gambar)
dan CSV ditulis ke server/data_lokal/hasil_ukur/, yang masuk .gitignore.
"""

import argparse
import csv
import json
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cer as modul_cer  # noqa: E402
import praproses  # noqa: E402

DATA_LOKAL = Path(__file__).resolve().parents[2] / "data_lokal"
FOLDER_GAMBAR = DATA_LOKAL / "screenshot_uji"
FOLDER_ACUAN = DATA_LOKAL / "transkripsi"
FOLDER_HASIL = DATA_LOKAL / "hasil_ukur"

GAMBAR_TANPA_TEKS = "15"  # hanya dipakai untuk karakter_karangan
GAMBAR_BANYAK_WILDCARD = "08"  # dikeluarkan di ringkasan "tanpa 08"

KOLOM_DASAR = ["nama_file", "lebar_asli", "tinggi_asli", "diperbesar", "lebar_kirim", "tinggi_kirim", "ukuran_jpeg_byte"]
KOLOM_WAKTU = ["detik_baca"]
KOLOM_METRIK = ["cer_isi", "cer_penuh", "ui_terbaca", "karakter_karangan", "karakter_hasil"]
KOLOM = KOLOM_DASAR + KOLOM_WAKTU + KOLOM_METRIK


# ---------------------------------------------------------------------------
# Kandidat. Tiap pembaca menerima gambar PIL (hasil praproses) dan mengembalikan teksnya.
# ---------------------------------------------------------------------------

def _larik_bgr(gambar):
    import numpy as np

    return np.array(gambar)[:, :, ::-1]  # OpenCV dan Paddle memakai urutan BGR


def buat_rapidocr(latin: bool):
    from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

    params = {"Global.log_level": "warning"}
    if latin:
        # Model Latin hanya tersedia untuk PP-OCRv5 (mobile); detektor tetap bawaan.
        params.update({"Rec.lang_type": LangRec.LATIN, "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE})
    mesin = RapidOCR(params=params)

    def baca(gambar):
        hasil = mesin(_larik_bgr(gambar))
        return "\n".join(hasil.txts) if hasil.txts else ""

    return baca, {"mesin": "rapidocr", "latin": latin}


def buat_paddleocr():
    from paddleocr import PaddleOCR

    mesin = PaddleOCR(
        lang="id",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,  # oneDNN di Paddle 3.3 untuk Windows CPU melempar NotImplementedError
    )

    def baca(gambar):
        hasil = mesin.predict(_larik_bgr(gambar))
        teks = [t for r in hasil for t in r["rec_texts"]]
        return "\n".join(teks)

    return baca, {"mesin": "paddleocr", "lang": "id (model rec latin)", "ocr_version": "PP-OCRv5"}


def kandidat_dikenal() -> list[str]:
    return ["praproses", "rapidocr", "rapidocr_latin", "paddleocr"]


# ---------------------------------------------------------------------------
# Acuan, CSV, dan metrik
# ---------------------------------------------------------------------------

def daftar_gambar() -> list[Path]:
    return sorted(p for p in FOLDER_GAMBAR.iterdir() if p.suffix.lower() in praproses.EKSTENSI_DITERIMA)


def muat_acuan(gambar: list[Path], folder: Path) -> dict:
    """Memuat semua transkripsi. [?ragu atau berkas hilang menghentikan program (kode keluar 2)."""
    acuan = {}
    for jalur in gambar:
        berkas = folder / f"{jalur.stem}.txt"
        if not berkas.exists():
            raise SystemExit(f"Galat: transkripsi {berkas} tidak ada.")
        try:
            acuan[jalur.stem] = modul_cer.baca_acuan(berkas.read_text(encoding="utf-8"), berkas.name)
        except modul_cer.TranskripsiBelumFinal as e:
            raise SystemExit(f"Galat: {e}")
    return acuan


def _bulat(x, n=4):
    return "" if x is None else round(x, n)


def kolom_metrik(acuan, teks: str) -> dict:
    m = modul_cer.hitung(acuan, teks)
    return {
        "cer_isi": _bulat(m.cer_isi),
        "cer_penuh": _bulat(m.cer_penuh),
        "ui_terbaca": _bulat(m.ui_terbaca),
        "karakter_karangan": m.karakter_karangan,
        "karakter_hasil": m.karakter_hasil,
    }


def tulis_csv(nama: str, baris: list[dict]) -> Path:
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    jalur = FOLDER_HASIL / f"{nama}.csv"
    with jalur.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM, restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(baris)
    return jalur


def baca_csv(nama: str) -> list[dict]:
    with (FOLDER_HASIL / f"{nama}.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Perintah
# ---------------------------------------------------------------------------

def perintah_jalankan(args) -> int:
    nama = args.kandidat
    if nama not in kandidat_dikenal():
        print(f"Kandidat tidak dikenal: {nama}. Lihat: ukur.py daftar", file=sys.stderr)
        return 2
    gambar = daftar_gambar()
    if not gambar:
        print(f"Tidak ada gambar di {FOLDER_GAMBAR}", file=sys.stderr)
        return 2
    acuan = {} if nama == "praproses" else muat_acuan(gambar, args.acuan)  # periksa [?ragu sebelum model dimuat

    baca, meta = None, {}
    if nama == "rapidocr":
        baca, meta = buat_rapidocr(latin=False)
    elif nama == "rapidocr_latin":
        baca, meta = buat_rapidocr(latin=True)
    elif nama == "paddleocr":
        baca, meta = buat_paddleocr()

    siap = [praproses.praproses(j) for j in gambar]
    if baca:
        # Pemanggilan pertama memuat model dan lebih lambat; dibuang dari pengukuran.
        print("Pemanasan ...", flush=True)
        baca(siap[0].gambar)

    folder_teks = FOLDER_HASIL / nama
    folder_teks.mkdir(parents=True, exist_ok=True)
    baris_csv = []
    for jalur, p in zip(gambar, siap):
        baris = {
            "nama_file": jalur.name,
            "lebar_asli": p.lebar_asli,
            "tinggi_asli": p.tinggi_asli,
            "diperbesar": "ya" if p.diperbesar else "tidak",
            "lebar_kirim": p.lebar_kirim,
            "tinggi_kirim": p.tinggi_kirim,
            "ukuran_jpeg_byte": p.ukuran_jpeg_byte,
        }
        if baca:
            durasi, teks = [], ""
            for i in range(args.ulang):
                mulai = time.perf_counter()
                t = baca(p.gambar)
                durasi.append(time.perf_counter() - mulai)
                if i == 0:
                    teks = t
            baris["detik_baca"] = round(statistics.median(durasi), 3)
            (folder_teks / f"{jalur.stem}.txt").write_text(teks, encoding="utf-8")
            baris.update(kolom_metrik(acuan[jalur.stem], teks))
        baris_csv.append(baris)
        print({k: baris.get(k, "") for k in ("nama_file", "diperbesar", "detik_baca", "cer_isi", "karakter_karangan")}, flush=True)

    meta.update({"ulang": args.ulang, "waktu": time.strftime("%Y-%m-%d %H:%M:%S"), "python": sys.version.split()[0]})
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    (FOLDER_HASIL / f"{nama}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"CSV: {tulis_csv(nama, baris_csv)}")
    return 0


def perintah_hitung_ulang(args) -> int:
    gambar = daftar_gambar()
    acuan = muat_acuan(gambar, args.acuan)
    nama_semua = args.kandidat or sorted(p.name[:-4] for p in FOLDER_HASIL.glob("*.csv") if p.name != "ringkasan.csv" and not p.name.startswith("praproses"))
    for nama in nama_semua:
        baris = baca_csv(nama)
        for b in baris:
            teks = (FOLDER_HASIL / nama / f"{Path(b['nama_file']).stem}.txt").read_text(encoding="utf-8")
            b.update(kolom_metrik(acuan[Path(b["nama_file"]).stem], teks))
        print(f"{nama}: {len(baris)} baris dihitung ulang -> {tulis_csv(nama, baris)}")
    return 0


def _rata(nilai: list[float]):
    return statistics.mean(nilai) if nilai else None


def ringkas_satu(nama: str, kecualikan: set[str]) -> dict:
    baris = [b for b in baca_csv(nama) if Path(b["nama_file"]).stem not in kecualikan]
    bukan_kosong = [b for b in baris if Path(b["nama_file"]).stem != GAMBAR_TANPA_TEKS]

    def angka(kolom, daftar=bukan_kosong):
        return [float(b[kolom]) for b in daftar if b.get(kolom) not in ("", None)]

    detik = angka("detik_baca")
    return {
        "kandidat": nama,
        "n_gambar": len(bukan_kosong),
        "detik_rata": _rata(detik),
        "detik_median": statistics.median(detik) if detik else None,
        "cer_isi": _rata(angka("cer_isi")),
        "cer_penuh": _rata(angka("cer_penuh")),
        "ui_terbaca": _rata(angka("ui_terbaca")),
        "karangan_rata": _rata(angka("karakter_karangan", baris)),  # termasuk gambar 15
        "karangan_15": next((int(b["karakter_karangan"]) for b in baris if Path(b["nama_file"]).stem == GAMBAR_TANPA_TEKS), None),
    }


def perintah_ringkas(args) -> int:
    nama_semua = sorted(p.name[:-4] for p in FOLDER_HASIL.glob("*.csv") if p.name not in ("ringkasan.csv", "praproses.csv"))
    hasil = []
    for variasi, kecualikan in (("semua gambar", set()), ("tanpa 08", {GAMBAR_BANYAK_WILDCARD})):
        for nama in nama_semua:
            r = ringkas_satu(nama, kecualikan)
            r["variasi"] = variasi
            hasil.append(r)
    kolom = ["variasi", "kandidat", "n_gambar", "detik_rata", "detik_median", "cer_isi", "cer_penuh", "ui_terbaca", "karangan_rata", "karangan_15"]
    with (FOLDER_HASIL / "ringkasan.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolom)
        w.writeheader()
        w.writerows({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in hasil)

    def f(x, d=2):
        return "-" if x is None else f"{x:.{d}f}"

    for variasi in ("semua gambar", "tanpa 08"):
        print(f"\n### Rata-rata per kandidat ({variasi}; gambar 15 hanya untuk karakter karangan)\n")
        print("| kandidat | n | detik rata-rata | detik median | CER isi | CER penuh | UI terbaca | karangan rata-rata | karangan di 15 |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in (x for x in hasil if x["variasi"] == variasi):
            print(f"| {r['kandidat']} | {r['n_gambar']} | {f(r['detik_rata'])} | {f(r['detik_median'])} | {f(r['cer_isi'], 3)} | {f(r['cer_penuh'], 3)} | {f(r['ui_terbaca'], 2)} | {f(r['karangan_rata'], 0)} | {r['karangan_15']} |")
    return 0


def _kata(teks: str) -> list[str]:
    return [k for k in re.split(r"[^0-9a-z]+", modul_cer.normalisasi(teks)) if k]


def perintah_kata_tak_terbaca(args) -> int:
    """Kata isi acuan (tanpa baris [UI] dan tanpa [?]) yang tidak muncul di hasil satu kandidat pun.

    Kata dianggap terbaca kalau muncul sebagai kata utuh di hasil salah satu kandidat, atau (untuk kata
    sepanjang 4 huruf lebih) sebagai potongan teks hasil yang spasinya dibuang, supaya kata yang
    ditempel ke kata lain oleh mesin tidak ikut terdaftar.
    """
    gambar = daftar_gambar()
    muat_acuan(gambar, args.acuan)  # memeriksa [?ragu dan berkas yang hilang
    kandidat = sorted(p.name for p in FOLDER_HASIL.iterdir() if p.is_dir())
    kandidat = [k for k in kandidat if any((FOLDER_HASIL / k).glob("*.txt"))]
    print(f"Kandidat yang dibandingkan ({len(kandidat)}): {', '.join(kandidat)}\n")
    total = 0
    for jalur in gambar:
        stem = jalur.stem
        kata_hasil, rapat = set(), ""
        for k in kandidat:
            berkas = FOLDER_HASIL / k / f"{stem}.txt"
            if berkas.exists():
                teks = berkas.read_text(encoding="utf-8")
                kata_hasil.update(_kata(teks))
                rapat += "".join(_kata(teks)) + "|"
        baris_isi = [b.replace("[?]", " ") for b in (args.acuan / f"{stem}.txt").read_text(encoding="utf-8").splitlines() if not b.startswith("[UI] ")]
        kata_acuan = set(_kata("\n".join(baris_isi)))
        hilang = sorted(k for k in kata_acuan if k not in kata_hasil and not (len(k) >= 4 and k in rapat))
        total += len(hilang)
        print(f"{stem}: {len(hilang)} kata dari {len(kata_acuan)}" + (f"  ->  {' '.join(hilang)}" if hilang else ""))
    print(f"\nTotal kata: {total}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--acuan", type=Path, default=FOLDER_ACUAN, help="folder transkripsi acuan (NN.txt)")
    sub = ap.add_subparsers(dest="perintah", required=True)
    j = sub.add_parser("jalankan")
    j.add_argument("kandidat")
    j.add_argument("--ulang", type=int, default=1, help="jumlah pengulangan baca per gambar; waktu = median")
    sub.add_parser("hitung-ulang").add_argument("kandidat", nargs="*")
    sub.add_parser("ringkas")
    sub.add_parser("kata-tak-terbaca")
    sub.add_parser("daftar")
    args = ap.parse_args()
    if args.perintah == "daftar":
        print("\n".join(kandidat_dikenal()))
        return 0
    return {
        "jalankan": perintah_jalankan,
        "hitung-ulang": perintah_hitung_ulang,
        "ringkas": perintah_ringkas,
        "kata-tak-terbaca": perintah_kata_tak_terbaca,
    }[args.perintah](args)


if __name__ == "__main__":
    raise SystemExit(main())
