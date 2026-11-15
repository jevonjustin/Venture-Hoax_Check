"""Membuat QR code link unduhan Veritas (PNG siap cetak dan SVG), lalu membaca ulang hasilnya.

Jalankan dari root repo dengan Python venv server (sudah berisi OpenCV dan Pillow):
    server/.venv/Scripts/python docs/showcase/buat_qr.py

Hasil: docs/showcase/qr_veritas.png dan docs/showcase/qr_veritas.svg.
Keluar dengan kode 1 bila ada pembacaan ulang yang tidak sama persis dengan URL.
"""
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

URL = "https://github.com/jevonjustin/Venture-Hoax_Check/releases/latest/download/veritas.apk"
FOLDER = Path(__file__).resolve().parent
BERKAS_PNG = FOLDER / "qr_veritas.png"
BERKAS_SVG = FOLDER / "qr_veritas.svg"
ZONA_TENANG = 4  # modul kosong di tiap sisi, sesuai standar QR
PIKSEL_PER_MODUL = 40
DPI = 300


def buat_matriks() -> np.ndarray:
    """Matriks modul QR (True = hitam), tanpa zona tenang."""
    p = cv2.QRCodeEncoder_Params()
    # Koreksi galat Q (sekitar 25% kerusakan masih terbaca): lebih tahan noda dan lipatan
    # daripada M, tetapi modulnya tetap lebih besar daripada H sehingga mudah dipindai dari jauh.
    p.correction_level = cv2.QRCODE_ENCODER_CORRECT_LEVEL_Q
    gambar = cv2.QRCodeEncoder_create(p).encode(URL)
    # OpenCV menghasilkan 1 piksel per modul dengan zona tenang sendiri; ambil modulnya saja.
    hitam = gambar < 128
    baris = np.where(hitam.any(axis=1))[0]
    kolom = np.where(hitam.any(axis=0))[0]
    return hitam[baris[0]:baris[-1] + 1, kolom[0]:kolom[-1] + 1]


def dengan_zona_tenang(m: np.ndarray) -> np.ndarray:
    return np.pad(m, ZONA_TENANG, constant_values=False)


def simpan_png(m: np.ndarray) -> None:
    penuh = dengan_zona_tenang(m)
    piksel = np.where(penuh, 0, 255).astype(np.uint8)
    piksel = np.kron(piksel, np.ones((PIKSEL_PER_MODUL, PIKSEL_PER_MODUL), dtype=np.uint8))
    Image.fromarray(piksel, mode="L").save(BERKAS_PNG, dpi=(DPI, DPI), optimize=True)


def simpan_svg(m: np.ndarray) -> None:
    n = m.shape[0] + 2 * ZONA_TENANG
    jalur = []
    for y, x in zip(*np.nonzero(m)):
        jalur.append(f"M{x + ZONA_TENANG} {y + ZONA_TENANG}h1v1h-1z")
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="100mm" height="100mm" '
        'shape-rendering="crispEdges">\n'
        f"<title>{URL}</title>\n"
        f'<rect width="{n}" height="{n}" fill="#ffffff"/>\n'
        f'<path fill="#000000" d="{"".join(jalur)}"/>\n'
        "</svg>\n"
    )
    BERKAS_SVG.write_text(svg, encoding="utf-8")


def matriks_dari_svg() -> np.ndarray:
    """Membangun ulang matriks dari jalur SVG, untuk memastikan SVG sama dengan PNG."""
    teks = BERKAS_SVG.read_text(encoding="utf-8")
    n = int(re.search(r'viewBox="0 0 (\d+) \1"', teks).group(1))
    m = np.zeros((n, n), dtype=bool)
    for x, y in re.findall(r"M(\d+) (\d+)h1v1h-1z", teks):
        m[int(y), int(x)] = True
    return m


def baca(gambar: np.ndarray) -> dict:
    hasil = {}
    for nama, detektor in (("QRCodeDetector", cv2.QRCodeDetector()), ("QRCodeDetectorAruco", cv2.QRCodeDetectorAruco())):
        teks, _, _ = detektor.detectAndDecode(gambar)
        hasil[nama] = teks
    return hasil


def main() -> int:
    m = buat_matriks()
    simpan_png(m)
    simpan_svg(m)

    png = np.array(Image.open(BERKAS_PNG).convert("L"))
    sisi_modul = m.shape[0]
    versi = (sisi_modul - 17) // 4
    cm = png.shape[0] / DPI * 2.54
    print(f"URL      : {URL} ({len(URL)} karakter)")
    print(f"QR       : versi {versi}, {sisi_modul}x{sisi_modul} modul, koreksi galat Q, zona tenang {ZONA_TENANG} modul")
    print(f"PNG      : {BERKAS_PNG.name} {png.shape[1]}x{png.shape[0]} px, {DPI} dpi = {cm:.1f} cm per sisi")

    sama_svg = np.array_equal(matriks_dari_svg(), dengan_zona_tenang(m))
    print(f"SVG      : {BERKAS_SVG.name}, matriks sama dengan PNG: {sama_svg}")

    semua_cocok = sama_svg
    # Wajib: ukuran asli dan 1/8 (sekitar 5 piksel per modul, setara foto kamera HP dari jarak wajar).
    wajib = {
        "asli": png,
        "kecil 1/8": cv2.resize(png, None, fx=1 / 8, fy=1 / 8, interpolation=cv2.INTER_AREA),
    }
    # Uji tekanan (informasi saja, tidak menggagalkan): 2-3 piksel per modul dan buram.
    tekanan = {
        "kecil 1/12 + buram": cv2.GaussianBlur(
            cv2.resize(png, None, fx=1 / 12, fy=1 / 12, interpolation=cv2.INTER_AREA), (3, 3), 0
        ),
        "kecil 1/16 + buram": cv2.GaussianBlur(
            cv2.resize(png, None, fx=1 / 16, fy=1 / 16, interpolation=cv2.INTER_AREA), (3, 3), 0
        ),
    }
    for kelompok, varian in (("wajib", wajib), ("tekanan", tekanan)):
        for nama_varian, g in varian.items():
            for detektor, teks in baca(g).items():
                cocok = teks == URL
                if kelompok == "wajib":
                    semua_cocok &= cocok
                hasil = "COCOK" if cocok else "TIDAK COCOK: " + repr(teks)
                print(f"Baca ulang {kelompok:<7} [{nama_varian:>18}] {detektor:<19}: {hasil}")
    print("HASIL    :", "semua pembacaan wajib sama persis dengan URL" if semua_cocok else "ADA YANG GAGAL")
    return 0 if semua_cocok else 1


if __name__ == "__main__":
    sys.exit(main())
