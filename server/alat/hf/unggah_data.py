"""Mengunggah data pencarian ke dataset PRIVAT Hugging Face jevonjustin/veritas-data (Sesi 8.1).

Yang diunggah hanya berkas yang dibaca server (app.pipeline.cocok.berkas_dibaca): artikel.jsonl dan vektor e5-base
fp32 dari data_lokal\\cek_fakta, serta model dan tokenizer e5-base dari data_lokal\\model. Susunan di dataset sama
dengan data_lokal (cek_fakta/..., model/...), sesuai yang diunduh app/data_hf.py di Space.

Menolak jalan bila dataset tujuan tidak privat. Token dari variabel lingkungan HF_TOKEN (izin tulis).

Pakai (dari folder server):
  .venv\\Scripts\\python.exe alat\\hf\\unggah_data.py --periksa   # hanya daftar dan ukuran; tanpa token dan jaringan
  .venv\\Scripts\\python.exe alat\\hf\\unggah_data.py             # unggah (minta konfirmasi)
"""

import argparse
import sys
from pathlib import Path

import umum  # noqa: F401  (menambahkan folder server ke sys.path)
from umum import DATASET, cetak_daftar, konfirmasi, masuk, ambil_token

from app.konfigurasi import DATA_LOKAL, Pengaturan  # noqa: E402
from app.pipeline import cocok  # noqa: E402

FOLDER_SUMBER = {"cek_fakta": DATA_LOKAL / "cek_fakta", "model": DATA_LOKAL / "model"}


def daftar_berkas(cfg: Pengaturan | None = None, sumber: dict[str, Path] | None = None) -> list[tuple[str, Path]]:
    """(jalur di dataset, berkas lokal) untuk setiap berkas yang dibaca pencarian server dengan pengaturan bawaan."""
    cfg = cfg or Pengaturan()
    sumber = sumber or FOLDER_SUMBER
    return [
        (f"{folder}/{nama}", sumber[folder] / Path(nama))
        for folder, daftar in cocok.berkas_dibaca(cfg).items()
        for nama in daftar
    ]


def pastikan_privat(api, buat: bool) -> None:
    if buat:
        api.create_repo(DATASET, repo_type="dataset", private=True, exist_ok=True)
    info = api.repo_info(DATASET, repo_type="dataset")
    if info.private is not True:
        print(
            f"Dataset {DATASET} TIDAK privat. Unggahan ditolak.\n"
            f"Ubah ke Private di https://huggingface.co/datasets/{DATASET}/settings lalu jalankan lagi.",
            file=sys.stderr,
        )
        sys.exit(4)
    print(f"Dataset {DATASET}: privat")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--periksa", action="store_true", help="hanya tampilkan daftar dan ukuran, tanpa jaringan")
    parser.add_argument("--ya", action="store_true", help="lewati konfirmasi")
    args = parser.parse_args(argv)

    berkas = daftar_berkas()
    hilang = [str(s) for _, s in berkas if not s.is_file()]
    if hilang:
        print("Berkas berikut tidak ada:\n  " + "\n  ".join(hilang), file=sys.stderr)
        return 2
    print(f"Berkas yang akan diunggah ke dataset {DATASET}:")
    cetak_daftar(berkas)
    if args.periksa:
        return 0

    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi(token=ambil_token())
    masuk(api)
    pastikan_privat(api, buat=True)
    konfirmasi("Unggah berkas di atas (bisa memakan waktu lama untuk 1 GB lebih)?", args.ya)
    pastikan_privat(api, buat=False)  # periksa sekali lagi tepat sebelum mengunggah
    api.create_commit(
        DATASET,
        repo_type="dataset",
        operations=[CommitOperationAdd(path_in_repo=tujuan, path_or_fileobj=str(sumber)) for tujuan, sumber in berkas],
        commit_message="Data pencarian Veritas (artikel, vektor e5-base fp32, model e5-base)",
    )
    di_repo = set(api.list_repo_files(DATASET, repo_type="dataset"))
    kurang = [t for t, _ in berkas if t not in di_repo]
    if kurang:
        print("Unggahan belum lengkap, berkas belum ada di dataset: " + ", ".join(kurang), file=sys.stderr)
        return 5
    print(f"Selesai. https://huggingface.co/datasets/{DATASET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
