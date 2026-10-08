"""Praproses gambar uji yang meniru jalur HP, seluruhnya di memori.

Urutan:
1. Gambar yang lebarnya di bawah 1080 px diperbesar ke lebar 1080 px dengan Lanczos.
   Ini meniru gambar terusan yang dibuka layar penuh di galeri Samsung A55 lalu di-screenshot.
2. Praproses aplikasi: sisi terpanjang maksimal 2000 px, lalu JPEG kualitas 90.

Berkas aslinya tidak pernah diubah. Menerima .jpg, .jpeg, .png, dan .webp.
"""

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

EKSTENSI_DITERIMA = {".jpg", ".jpeg", ".png", ".webp"}
LEBAR_LAYAR_HP = 1080
SISI_MAKS_APLIKASI = 2000
KUALITAS_JPEG = 90


@dataclass(frozen=True)
class HasilPraproses:
    gambar: Image.Image  # hasil decode JPEG yang dikirim, RGB
    lebar_asli: int
    tinggi_asli: int
    diperbesar: bool
    lebar_kirim: int
    tinggi_kirim: int
    ukuran_jpeg_byte: int


def muat_gambar(jalur: Path) -> Image.Image:
    """Membuka gambar (jpg/png/webp) sebagai RGB. Gambar transparan dilapisi latar putih."""
    if jalur.suffix.lower() not in EKSTENSI_DITERIMA:
        raise ValueError(f"Ekstensi {jalur.suffix} tidak diterima: {jalur.name}")
    with Image.open(jalur) as sumber:
        sumber.load()
        if sumber.mode in ("RGBA", "LA", "P"):
            rgba = sumber.convert("RGBA")
            latar = Image.new("RGB", rgba.size, "white")
            latar.paste(rgba, mask=rgba.getchannel("A"))
            return latar
        return sumber.convert("RGB")


def _perbesar_ke_lebar_hp(gambar: Image.Image) -> tuple[Image.Image, bool]:
    if gambar.width >= LEBAR_LAYAR_HP:
        return gambar, False
    tinggi = round(gambar.height * LEBAR_LAYAR_HP / gambar.width)
    return gambar.resize((LEBAR_LAYAR_HP, tinggi), Image.Resampling.LANCZOS), True


def _kecilkan_ke_batas_aplikasi(gambar: Image.Image) -> Image.Image:
    terpanjang = max(gambar.size)
    if terpanjang <= SISI_MAKS_APLIKASI:
        return gambar
    skala = SISI_MAKS_APLIKASI / terpanjang
    ukuran = (round(gambar.width * skala), round(gambar.height * skala))
    return gambar.resize(ukuran, Image.Resampling.LANCZOS)


def praproses(jalur: Path) -> HasilPraproses:
    asli = muat_gambar(jalur)
    setelah_hp, diperbesar = _perbesar_ke_lebar_hp(asli)
    untuk_kirim = _kecilkan_ke_batas_aplikasi(setelah_hp)

    buf = io.BytesIO()
    untuk_kirim.save(buf, format="JPEG", quality=KUALITAS_JPEG)
    data_jpeg = buf.getvalue()
    with Image.open(io.BytesIO(data_jpeg)) as hasil:
        hasil.load()
        gambar_kirim = hasil.convert("RGB")

    return HasilPraproses(
        gambar=gambar_kirim,
        lebar_asli=asli.width,
        tinggi_asli=asli.height,
        diperbesar=diperbesar,
        lebar_kirim=gambar_kirim.width,
        tinggi_kirim=gambar_kirim.height,
        ukuran_jpeg_byte=len(data_jpeg),
    )
