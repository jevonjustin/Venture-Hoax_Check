"""Validasi keluaran LLM dan perhitungan metrik. Hanya fungsi murni (tanpa jaringan)."""

import json
import re
import statistics

from prompt import KATA_PENILAIAN


def normalisasi(teks: str) -> str:
    return re.sub(r"\s+", " ", teks).strip().lower()


def urai_json(konten: str):
    """Mengurai JSON; pagar kode ```json ... ``` dibuang dulu. Mengembalikan None kalau gagal."""
    t = (konten or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return None


def validasi(konten: str, id_boleh: tuple[str, ...]) -> tuple[dict | None, list[str], list[str]]:
    """Mengembalikan (data atau None, id di luar daftar, daftar masalah). Valid = masalah kosong."""
    data = urai_json(konten)
    masalah: list[str] = []
    id_luar: list[str] = []
    if not isinstance(data, dict):
        return None, id_luar, ["bukan objek JSON"]
    if set(data) != {"klaim_utama", "ciri"}:
        masalah.append("kunci tidak sesuai skema")
    if not isinstance(data.get("klaim_utama"), str):
        masalah.append("klaim_utama bukan string")
    ciri = data.get("ciri")
    if not isinstance(ciri, list):
        masalah.append("ciri bukan daftar")
    else:
        for c in ciri:
            if not (isinstance(c, dict) and set(c) == {"id", "kutipan"} and isinstance(c["id"], str)
                    and isinstance(c["kutipan"], list) and all(isinstance(k, str) for k in c["kutipan"])):
                masalah.append("butir ciri tidak sesuai skema")
                break
            if c["id"] not in id_boleh:
                id_luar.append(c["id"])
    if id_luar:
        masalah.append("id di luar daftar")
    return (data if not masalah else None), id_luar, masalah


def kutipan_jujur(data: dict, teks_masukan: str) -> tuple[int, int]:
    """(jumlah kutipan ditemukan, jumlah kutipan) setelah normalisasi spasi dan huruf besar-kecil."""
    acuan = normalisasi(teks_masukan)
    ada = total = 0
    for c in data["ciri"]:
        for k in c["kutipan"]:
            total += 1
            kn = normalisasi(k)
            if kn and kn in acuan:
                ada += 1
    return ada, total


def kata_penilaian_tambahan(klaim: str, teks_masukan: str) -> list[str]:
    """Kata penilaian yang ada di klaim_utama tetapi tidak ada di teks masukan."""
    kn, tn = normalisasi(klaim), normalisasi(teks_masukan)
    hasil = []
    for k in KATA_PENILAIAN:
        # Di klaim dicek per kata; di teks masukan cukup sebagai potongan, karena OCR sering menempelkan kata
        # ("TERDETEKSIPALSU") dan kata itu tetap berasal dari teks asli.
        if re.search(rf"\b{k}\b", kn) and k not in tn:
            hasil.append(k)
    return hasil


def persentil(nilai: list[float], p: float) -> float | None:
    if not nilai:
        return None
    s = sorted(nilai)
    i = min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))
    return s[i]


def median(nilai: list[float]) -> float | None:
    return statistics.median(nilai) if nilai else None


def jaccard(a: str, b: str) -> float:
    x, y = set(normalisasi(a).split()), set(normalisasi(b).split())
    return len(x & y) / len(x | y) if (x | y) else 1.0
