"""Mengunduh model multilingual-e5 (ONNX resmi, lisensi MIT) dari Hugging Face ke server/data_lokal/model/.

Berkas yang diunduh per model: onnx/model.onnx (FP32), tokenizer.json, dan opsional model int8.
Unduhan bisa dilanjutkan kalau terputus dan ukuran akhir diperiksa terhadap Content-Length.
"""

import argparse
import sys
from pathlib import Path

import requests

from skema import DATA_LOKAL

MODEL = {"small": "intfloat/multilingual-e5-small", "base": "intfloat/multilingual-e5-base"}
BERKAS = {"fp32": "onnx/model.onnx", "int8": "onnx/model_qint8_avx512_vnni.onnx"}
FOLDER_MODEL = DATA_LOKAL / "model"


def jalur_model(ukuran: str, varian: str) -> Path:
    return FOLDER_MODEL / f"e5-{ukuran}" / Path(BERKAS[varian]).name


def jalur_tokenizer(ukuran: str) -> Path:
    return FOLDER_MODEL / f"e5-{ukuran}" / "tokenizer.json"


def unduh(repo: str, berkas: str, tujuan: Path):
    url = f"https://huggingface.co/{repo}/resolve/main/{berkas}"
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    sementara = tujuan.with_suffix(tujuan.suffix + ".part")
    sudah = sementara.stat().st_size if sementara.exists() else 0
    head = requests.head(url, allow_redirects=True, timeout=30)
    total = int(head.headers.get("Content-Length", 0))
    if tujuan.exists() and tujuan.stat().st_size == total:
        print(f"sudah ada: {tujuan.name} ({total / 1e6:.0f} MB)")
        return
    header = {"Range": f"bytes={sudah}-"} if sudah else {}
    with requests.get(url, headers=header, stream=True, timeout=(15, 60)) as r:
        r.raise_for_status()
        mode = "ab" if r.status_code == 206 else "wb"
        with open(sementara, mode) as f:
            diunduh = sudah if mode == "ab" else 0
            for potongan in r.iter_content(1 << 20):
                f.write(potongan)
                diunduh += len(potongan)
                print(f"\r{tujuan.name}: {diunduh / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
    if sementara.stat().st_size != total:
        raise SystemExit(f"\nUkuran {tujuan.name} tidak cocok ({sementara.stat().st_size} != {total}); jalankan ulang.")
    sementara.replace(tujuan)
    print()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ukuran", nargs="+", choices=list(MODEL), default=list(MODEL))
    p.add_argument("--varian", nargs="+", choices=list(BERKAS), default=["fp32"])
    a = p.parse_args()
    for u in a.ukuran:
        unduh(MODEL[u], "tokenizer.json", jalur_tokenizer(u))
        for v in a.varian:
            unduh(MODEL[u], BERKAS[v], jalur_model(u, v))
    print("Selesai.")


if __name__ == "__main__":
    sys.exit(main())
