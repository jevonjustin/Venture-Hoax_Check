"""Klien tunggal untuk endpoint chat/completions yang kompatibel dengan OpenAI.

Kunci API dimuat dari server/.env di dalam proses ini saja. Kunci tidak pernah dicetak, ditulis ke berkas,
atau dimasukkan ke pesan galat (semua teks galat disaring lewat _bersihkan).
"""

import json
import os
import re
import time

import httpx

from konfigurasi import BATAS_WAKTU_DETIK, FOLDER_ENV, MAKS_429, MAKS_TOKEN_KELUARAN, Model
from metrik import validasi
from prompt import id_untuk_llm, pesan_pengguna, prompt_sistem, skema_json


def muat_kunci(m: Model) -> str:
    """Mengembalikan kunci, atau string kosong kalau tidak diisi. Tidak mengubah os.environ milik proses lain."""
    if m.env in os.environ and os.environ[m.env].strip():
        return os.environ[m.env].strip()
    if FOLDER_ENV.exists():
        for baris in FOLDER_ENV.read_text(encoding="utf-8").splitlines():
            baris = baris.strip()
            if baris and not baris.startswith("#") and "=" in baris:
                k, v = baris.split("=", 1)
                if k.strip() == m.env:
                    return v.strip().strip('"').strip("'")
    return ""


class Klien:
    def __init__(self, m: Model, kunci: str):
        self.m = m
        self._kunci = kunci
        self.http = httpx.Client(timeout=BATAS_WAKTU_DETIK)
        self.id_boleh = id_untuk_llm()
        self.sistem = prompt_sistem()
        self.i_berpikir = 0
        self.i_format = 0
        self.jeda = float(m.jeda_detik)
        self.ditolak: list[str] = []   # parameter yang ditolak API (untuk laporan)
        self._terakhir = 0.0

    # --- bantu ---
    def _bersihkan(self, s: str) -> str:
        return s.replace(self._kunci, "[KUNCI]") if self._kunci else s

    @property
    def berpikir(self):
        return self.m.berpikir[self.i_berpikir]

    @property
    def format_keluaran(self):
        return self.m.format_keluaran[self.i_format]

    def pengaturan(self) -> dict:
        return {"berpikir": self.berpikir, "format_keluaran": self.format_keluaran, "ditolak": self.ditolak}

    def _badan(self, teks: str) -> dict:
        b = {
            "model": self.m.nama,
            "temperature": 0,
            "max_tokens": MAKS_TOKEN_KELUARAN,
            "messages": [{"role": "system", "content": self.sistem}, {"role": "user", "content": pesan_pengguna(teks)}],
        }
        if self.berpikir is not None:
            b["reasoning_effort"] = self.berpikir
        if self.format_keluaran == "json_schema":
            b["response_format"] = {"type": "json_schema", "json_schema": {"name": "analisis", "strict": True, "schema": skema_json()}}
        elif self.format_keluaran == "json_object":
            b["response_format"] = {"type": "json_object"}
        return b

    def _turun(self, badan_galat: str) -> bool:
        """Setelah 400: pindah ke pilihan berikutnya pada parameter yang dicurigai. False kalau sudah habis."""
        t = badan_galat.lower()
        mau_format = any(k in t for k in ("response_format", "json_schema", "schema", "json_object"))
        mau_pikir = any(k in t for k in ("reason", "thinking", "effort"))
        urutan = ["format"] if mau_format and not mau_pikir else ["pikir"] if mau_pikir else ["pikir", "format"]
        for jenis in urutan + [j for j in ("pikir", "format") if j not in urutan]:
            if jenis == "pikir" and self.i_berpikir < len(self.m.berpikir) - 1:
                self.ditolak.append(f"reasoning_effort={self.berpikir}")
                self.i_berpikir += 1
                return True
            if jenis == "format" and self.i_format < len(self.m.format_keluaran) - 1:
                self.ditolak.append(f"response_format={self.format_keluaran}")
                self.i_format += 1
                return True
        return False

    def _tunggu_jeda(self):
        sisa = self._terakhir + self.jeda - time.monotonic()
        if sisa > 0:
            time.sleep(sisa)

    # --- satu panggilan HTTP (dengan penanganan 400 dan 429) ---
    def _panggil(self, teks: str, cat: dict) -> tuple[str | None, int, dict]:
        """Mengembalikan (konten atau None, waktu_ms panggilan sukses, penggunaan token)."""
        n429 = 0
        while True:
            self._tunggu_jeda()
            t0 = time.monotonic()
            try:
                r = self.http.post(f"{self.m.url}/chat/completions", json=self._badan(teks),
                                   headers={"Authorization": f"Bearer {self._kunci}"})
            except httpx.HTTPError as e:
                self._terakhir = time.monotonic()
                cat["galat"].append(self._bersihkan(f"jaringan: {type(e).__name__}"))
                return None, 0, {}
            self._terakhir = time.monotonic()
            ms = int((self._terakhir - t0) * 1000)
            if r.status_code == 200:
                try:
                    j = r.json()
                    return j["choices"][0]["message"].get("content") or "", ms, j.get("usage", {})
                except (ValueError, KeyError, IndexError, TypeError):
                    cat["galat"].append("respons 200 tidak terbaca")
                    return None, ms, {}
            cat["status"].append(r.status_code)
            if r.status_code == 429:
                cat["n429"] += 1
                n429 += 1
                if n429 > MAKS_429:
                    cat["galat"].append(self._bersihkan("429 berulang: " + re.sub(r"\s+", " ", r.text)[:300]))
                    return None, ms, {}
                try:
                    tunggu = float(r.headers.get("retry-after", "20"))
                except ValueError:
                    tunggu = 20.0
                tunggu = min(max(tunggu, 5.0), 90.0)
                self.jeda = min(self.jeda * 1.5, 30.0)
                time.sleep(tunggu)
                continue
            if r.status_code == 400 and "json_validate_failed" in r.text and cat["gagal_json"] < 2:
                # Kegagalan acak penyedia saat menyusun JSON (bukan parameter yang ditolak): kirim ulang yang sama
                cat["gagal_json"] += 1
                continue
            if r.status_code == 400 and self._turun(r.text):
                cat["penyesuaian"] += 1
                continue
            cat["galat"].append(self._bersihkan(f"HTTP {r.status_code}: {r.text[:200]}"))
            return None, ms, {}

    # --- satu teks: panggil, validasi, ulang sekali kalau tidak valid ---
    def analisis(self, teks: str) -> dict:
        cat = {"status": [], "n429": 0, "galat": [], "penyesuaian": 0, "gagal_json": 0}
        percobaan = []
        for ke in (1, 2):
            konten, ms, usage = self._panggil(teks, cat)
            if konten is None:
                percobaan.append({"konten": None, "waktu_ms": ms})
                break
            data, id_luar, masalah = validasi(konten, self.id_boleh)
            percobaan.append({"konten": konten, "waktu_ms": ms, "id_luar": id_luar, "masalah": masalah,
                              "token": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}})
            if data is not None:
                break
        akhir = percobaan[-1]
        return {
            "valid": bool(akhir.get("konten") is not None and not akhir.get("masalah")),
            "data": validasi(akhir["konten"], self.id_boleh)[0] if akhir.get("konten") is not None else None,
            "percobaan": percobaan,
            "n429": cat["n429"],
            "status_non200": cat["status"],
            "galat": cat["galat"],
            "pengaturan": self.pengaturan(),
        }
