"""Mengunggah server ke Docker Space publik Hugging Face jevonjustin/veritas (Sesi 8.1).

Yang diunggah hanya: Dockerfile, .dockerignore, space\\README.md (menjadi README.md Space), requirements.txt,
requirements-space.txt, dan berkas .py di folder app. Tidak pernah: .env, data_lokal, data_hf, tests, alat, .venv.
Berkas app/ di Space yang sudah tidak ada di lokal dihapus dalam commit yang sama.

Variabel Space non-rahasia (CEKHOAKS_HF_DATASET, CEKHOAKS_HOST, CEKHOAKS_PORT) diatur lewat API. Secrets
(HF_TOKEN baca-saja, GROQ_API_KEY, GEMINI_API_KEY) TIDAK diisi skrip ini: isi sendiri di Settings Space.
Token dari variabel lingkungan HF_TOKEN (izin tulis).

Pakai (dari folder server):
  .venv\\Scripts\\python.exe alat\\hf\\unggah_space.py --periksa   # hanya daftar berkas; tanpa token dan jaringan
  .venv\\Scripts\\python.exe alat\\hf\\unggah_space.py             # unggah (minta konfirmasi)
"""

import argparse
import sys
from pathlib import Path

from umum import BAGIAN_TERLARANG, DATASET, SERVER, SPACE, ambil_token, cetak_daftar, konfirmasi, masuk

VARIABEL = {"CEKHOAKS_HF_DATASET": DATASET, "CEKHOAKS_HOST": "0.0.0.0", "CEKHOAKS_PORT": "7860"}
BERKAS_TETAP = {
    "Dockerfile": "Dockerfile",
    ".dockerignore": ".dockerignore",
    "README.md": "space/README.md",
    "requirements.txt": "requirements.txt",
    "requirements-space.txt": "requirements-space.txt",
}
# Berkas Space yang dibuat Hugging Face sendiri; tidak dihapus walau tidak ada di lokal.
BERKAS_BAWAAN_SPACE = {".gitattributes"}


class BerkasTerlarang(ValueError):
    pass


def periksa_aman(tujuan: str) -> None:
    bagian = set(Path(tujuan).parts)
    if bagian & BAGIAN_TERLARANG or any(b.startswith(".env") for b in bagian):
        raise BerkasTerlarang(f"berkas terlarang masuk daftar unggah: {tujuan}")


def daftar_berkas(server: Path = SERVER) -> list[tuple[str, Path]]:
    """(jalur di Space, berkas lokal), urut. Melempar BerkasTerlarang bila ada jalur yang tidak boleh diunggah."""
    berkas = [(tujuan, server / sumber) for tujuan, sumber in BERKAS_TETAP.items()]
    for py in sorted((server / "app").rglob("*.py")):
        relatif = py.relative_to(server)
        if "__pycache__" in relatif.parts:
            continue
        berkas.append((relatif.as_posix(), py))
    for tujuan, _ in berkas:
        periksa_aman(tujuan)
    return berkas


def operasi_hapus(di_space: set[str], diunggah: set[str]) -> list[str]:
    """Berkas di Space yang tidak lagi diunggah (sisa versi lama), kecuali berkas bawaan Space."""
    return sorted(f for f in di_space - diunggah - BERKAS_BAWAAN_SPACE)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--periksa", action="store_true", help="hanya tampilkan daftar berkas, tanpa jaringan")
    parser.add_argument("--ya", action="store_true", help="lewati konfirmasi")
    args = parser.parse_args(argv)

    berkas = daftar_berkas()
    hilang = [str(s) for _, s in berkas if not s.is_file()]
    if hilang:
        print("Berkas berikut tidak ada:\n  " + "\n  ".join(hilang), file=sys.stderr)
        return 2
    print(f"Berkas yang akan diunggah ke Space {SPACE}:")
    cetak_daftar(berkas)
    print("Variabel Space (bukan rahasia): " + ", ".join(f"{k}={v}" for k, v in VARIABEL.items()))
    if args.periksa:
        return 0

    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

    api = HfApi(token=ambil_token())
    masuk(api)
    api.create_repo(SPACE, repo_type="space", space_sdk="docker", space_hardware="cpu-basic", private=False, exist_ok=True)
    info = api.repo_info(SPACE, repo_type="space")
    if info.private:
        print(f"Peringatan: Space {SPACE} privat. Aplikasi pengunjung butuh Space publik (ubah di Settings Space).")
    di_space = set(api.list_repo_files(SPACE, repo_type="space"))
    hapus = operasi_hapus(di_space, {t for t, _ in berkas})
    if hapus:
        print("Berkas lama di Space yang akan dihapus: " + ", ".join(hapus))
    konfirmasi("Unggah berkas di atas dan atur variabel Space?", args.ya)

    for kunci, nilai in VARIABEL.items():
        api.add_space_variable(SPACE, kunci, nilai)
    print("Variabel Space diatur.")
    operasi = [CommitOperationAdd(path_in_repo=t, path_or_fileobj=str(s)) for t, s in berkas]
    operasi += [CommitOperationDelete(path_in_repo=f) for f in hapus]
    api.create_commit(SPACE, repo_type="space", operations=operasi, commit_message="Server Veritas (Sesi 8.1)")
    print(
        f"Selesai. Space akan dibangun ulang: https://huggingface.co/spaces/{SPACE}\n"
        "Secrets HF_TOKEN (baca-saja), GROQ_API_KEY, dan GEMINI_API_KEY diisi sendiri di Settings Space."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
