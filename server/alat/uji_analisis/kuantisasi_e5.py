"""Kuantisasi int8 dinamis model e5-base lokal (Sesi 5.6) dengan onnxruntime.quantization.quantize_dynamic.

Masukan : server\\data_lokal\\model\\e5-base\\model.onnx (fp32, tidak diubah).
Keluaran: server\\data_lokal\\evaluasi\\model_int8\\model_int8.onnx. Berkas yang sudah ada tidak ditimpa tanpa --timpa.
Butuh paket `onnx` di .venv (belum terpasang saat skrip ini ditulis; pemasangan atas izin pemilik).
Tanpa jaringan. Setelah ini: bangun vektor int8 dengan model tersebut: alat\\cek_fakta\\evaluasi.py vektor --model ... --keluar ...
"""

import argparse
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
MASUKAN = SERVER / "data_lokal" / "model" / "e5-base" / "model.onnx"
KELUARAN = SERVER / "data_lokal" / "evaluasi" / "model_int8" / "model_int8.onnx"


def kuantisasi(masukan: Path, keluaran: Path, timpa: bool = False) -> int:
    if not masukan.exists():
        print(f"DITOLAK: model masukan tidak ada: {masukan}", file=sys.stderr)
        return 2
    if keluaran.exists() and not timpa:
        print(f"DITOLAK: {keluaran} sudah ada (gunakan --timpa untuk menggantinya)", file=sys.stderr)
        return 2
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except ImportError as e:
        print(f"DITOLAK: paket belum terpasang ({e.name}); onnxruntime.quantization butuh paket onnx", file=sys.stderr)
        return 2
    keluaran.parent.mkdir(parents=True, exist_ok=True)
    # Bobot int8 untuk MatMul/Gemm; aktivasi dikuantisasi saat jalan (dinamis), jadi tidak perlu data kalibrasi.
    quantize_dynamic(str(masukan), str(keluaran), weight_type=QuantType.QInt8)
    print(f"ditulis: {keluaran} ({keluaran.stat().st_size / 1e6:.0f} MB; fp32 {masukan.stat().st_size / 1e6:.0f} MB)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--masukan", default=str(MASUKAN))
    p.add_argument("--keluaran", default=str(KELUARAN))
    p.add_argument("--timpa", action="store_true")
    a = p.parse_args(argv)
    return kuantisasi(Path(a.masukan), Path(a.keluaran), a.timpa)


if __name__ == "__main__":
    sys.exit(main())
