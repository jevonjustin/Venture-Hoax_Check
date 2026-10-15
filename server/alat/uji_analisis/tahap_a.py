"""Menjalankan pipeline Tahap A (tanpa LLM) pada screenshot uji dan menulis tabel ringkasan.

Perintah (dari folder server, dengan venv server):
  .venv\\Scripts\\python.exe alat\\uji_analisis\\tahap_a.py

Hasil: server\\data_lokal\\hasil_analisis\\tahap_a.md. Gambar hanya dibaca dari disk dan tidak ditulis ke mana pun.
Teks gambar dan judul artikel ikut tertulis di berkas hasil (lokal, di data_lokal yang diabaikan git).
"""

import asyncio
import csv
import io
import re
import sys
import uuid
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER))

from PIL import Image  # noqa: E402

from app import konfigurasi  # noqa: E402
from app.galat import GalatApi  # noqa: E402
from app.pipeline import cocok, orkestrator  # noqa: E402
from app.pipeline.tipe import Konteks  # noqa: E402

FOLDER_GAMBAR = SERVER / "data_lokal" / "screenshot_uji"
FILE_SUMBER = SERVER / "data_lokal" / "sumber_gambar.csv"
FOLDER_HASIL = SERVER / "data_lokal" / "hasil_analisis"
LABEL_SALAH = {"salah", "penipuan"}


def kunci_slug(url: str) -> str:
    jalur = re.sub(r"^https?://[^/]+", "", (url or "").strip().lower()).split("?")[0].rstrip("/")
    return re.sub(r"^\d+-", "", jalur.rsplit("/", 1)[-1])


def muat_sumber() -> dict[str, str]:
    with open(FILE_SUMBER, encoding="utf-8-sig") as f:
        return {b["nama_file"]: b["url_artikel"] for b in csv.DictReader(f)}


def sebagai_png(jalur: Path) -> bytes:
    """Server hanya menerima JPEG/PNG; WebP diubah di memori (aplikasi selalu mengirim JPEG)."""
    data = jalur.read_bytes()
    if jalur.suffix.lower() != ".webp":
        return data
    keluaran = io.BytesIO()
    with Image.open(io.BytesIO(data)) as g:
        g.convert("RGB").save(keluaran, format="PNG")
    return keluaran.getvalue()


async def tidak_putus() -> bool:
    return False


def sel(teks: str) -> str:
    return re.sub(r"\s+", " ", teks).replace("|", "\\|").strip()


def ringkas_artikel(k) -> str:
    return f"{k.skor:.3f} {k.label} rel={k.relevansi:.2f} — {sel(k.judul)[:70]}"


async def jalankan_semua() -> str:
    if konfigurasi.kesalahan:
        raise SystemExit(f"Pengaturan tidak sah: {konfigurasi.kesalahan}")
    await cocok.pencarian.siapkan()
    p = cocok.pencarian
    if p.status != cocok.STATUS_SIAP:
        raise SystemExit(f"Pencarian tidak siap: {p.ringkasan()}")
    sumber = muat_sumber()
    indeks = {}
    for a in p._artikel:
        indeks.setdefault(kunci_slug(a.get("url", "")), a)
    cfg = konfigurasi.pengaturan

    baris_tabel, detail, ringkasan = [], [], {"kuat": 0, "hati_hati": 0, "tidak_ditemukan": 0, "galat": 0}
    jumlah_sumber = jumlah_sumber_peringkat1 = 0
    palsu: list[str] = []
    durasi_total = []

    for jalur in sorted(FOLDER_GAMBAR.iterdir()):
        nama = jalur.stem
        diag: dict = {}
        ctx = Konteks(id_permintaan=uuid.uuid4().hex, jeda_detik=(0.0, 0.0), klien_putus=tidak_putus, diagnostik=diag)
        url_sumber = sumber.get(jalur.name, "")
        a_sumber = indeks.get(kunci_slug(url_sumber)) if url_sumber else None
        try:
            hasil = await orkestrator.jalankan(sebagai_png(jalur), ctx)
        except GalatApi as e:
            ringkasan["galat"] += 1
            baris_tabel.append(f"| {nama} | galat `{e.kode}` | | | | | |")
            continue
        durasi_total.append(hasil.durasi_ms)
        putusan = diag["putusan"]
        kandidat = diag["kandidat"]
        ringkasan[hasil.tingkat.value] += 1

        if a_sumber:
            jumlah_sumber += 1
            rank = next((i for i, k in enumerate(kandidat, 1) if k.url == a_sumber.get("url")), None)
            sumber_ket = "ya (peringkat 1)" if rank == 1 else (f"peringkat {rank}" if rank else "tidak di 5 teratas")
            jumlah_sumber_peringkat1 += rank == 1
        else:
            sumber_ket = "sumber tidak ada di DB" if url_sumber else "tanpa artikel sumber"

        tampil_salah = [k for k in putusan.cek_fakta if k.label in LABEL_SALAH]
        curiga = bool(not a_sumber and (tampil_salah or putusan.ciri_dibantah))
        if curiga:
            palsu.append(nama)

        teratas = kandidat[0] if kandidat else None
        ciri = ", ".join(f"{c.id} ({c.keyakinan})" for c in hasil.ciri)
        tingkat_ket = hasil.tingkat.value + (f" / {putusan.varian}" if putusan.varian else "")
        baris_tabel.append(
            f"| {nama}{' ⚠' if curiga else ''} | {tingkat_ket} | "
            f"{f'{teratas.skor:.3f} {teratas.label}' if teratas else '-'} | {sumber_ket} | "
            f"{len(putusan.cek_fakta)} tampil, {len(putusan.tersaring)} tersaring | {sel(ciri) or '-'} | {hasil.durasi_ms} |"
        )

        d = [f"### {nama} — {tingkat_ket}{' ⚠ calon kecocokan palsu' if curiga else ''}", ""]
        d.append(f"- Sumber: {sumber_ket}" + (f" — {sel(a_sumber.get('judul', ''))[:80]}" if a_sumber else ""))
        d.append(f"- Teks bersih: {sel(hasil.teks_terbaca)[:200]}")
        d.append(f"- Klaim heuristik: {sel(hasil.klaim_utama or '(kosong)')[:160]}")
        d.append("- Kandidat teratas:")
        tampil_url = {k.url for k in putusan.cek_fakta}
        saring_url = {k.url for k in putusan.tersaring}
        for k in kandidat:
            status = "TAMPIL" if k.url in tampil_url else ("TERSARING" if k.url in saring_url else "di bawah ambang mirip")
            tanda = " ★sumber" if a_sumber and k.url == a_sumber.get("url") else ""
            d.append(f"  - [{status}] {ringkas_artikel(k)}{tanda}")
        for c in hasil.ciri:
            d.append(f"- Ciri `{c.id}` ({c.keyakinan}): " + "; ".join(sel(b)[:90] for b in c.bukti))
        detail.append("\n".join(d))

    urut = sorted(durasi_total)
    median = urut[len(urut) // 2] if urut else 0
    hasil_md = [
        "# Hasil Tahap A (tanpa LLM)", "",
        f"Pencarian: {p.ringkasan()}. Ambang: cocok {cfg.ambang_cocok}, mirip {cfg.ambang_mirip}, "
        f"relevansi minimum {cfg.relevansi_minimum}, selisih konflik {cfg.selisih_konflik}.", "",
        f"Tingkat: kuat {ringkasan['kuat']}, hati_hati {ringkasan['hati_hati']}, "
        f"tidak_ditemukan {ringkasan['tidak_ditemukan']}, galat {ringkasan['galat']}. "
        f"Artikel sumber ada di DB untuk {jumlah_sumber} gambar, peringkat 1 pada {jumlah_sumber_peringkat1}. "
        f"Durasi median {median} ms (termasuk OCR).", "",
        "⚠ = gambar tanpa artikel sumber di DB yang tetap mendapat artikel salah/penipuan yang tampil atau ciri "
        "`pernah_dibantah`: calon kecocokan palsu, perlu dinilai manual. `rel` = relevansi leksikal judul (0-1).", "",
        "| Gambar | Tingkat / varian | Kandidat #1 | Artikel sumber | cek_fakta | Ciri (keyakinan) | ms |",
        "|---|---|---|---|---|---|---|",
        *baris_tabel, "", "## Rincian", "", *detail, "",
    ]
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    jalur_hasil = FOLDER_HASIL / "tahap_a.md"
    jalur_hasil.write_text("\n".join(hasil_md), encoding="utf-8")
    return str(jalur_hasil)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    jalur = asyncio.run(jalankan_semua())
    print(f"Tabel ditulis ke {jalur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
