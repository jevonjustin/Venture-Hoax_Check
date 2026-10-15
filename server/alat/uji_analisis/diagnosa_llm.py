"""Diagnosis kenapa Groq tidak terpakai di server (MEMANGGIL API; dijalankan developer, bukan Claude).

Perintah (dari folder server):
  .venv\\Scripts\\python.exe alat\\uji_analisis\\diagnosa_llm.py

Mengirim teks contoh yang dibuat sendiri (tanpa data pribadi) ke tiap penyedia dengan badan permintaan yang sama
seperti produksi, lalu variasinya: User-Agent lain, tanpa response_format, tanpa reasoning_effort. Yang dicetak
hanya: penyedia, varian, status HTTP, kode galat (field error.code / error.type atau nomor galat Cloudflare),
durasi, dan apakah balasan 200 bisa diurai. Kunci, isi pesan galat, dan isi balasan tidak dicetak.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import konfigurasi  # noqa: E402
from app.pipeline import llm  # noqa: E402

TEKS = (
    "Info penting! Akun Facebook akan segera dinonaktifkan. Sebarkan pesan ini ke semua grup sebelum hari ini "
    "berakhir. Klik tautan https://bit.ly/contoh-uji untuk verifikasi."
)
UA_LAIN = "CekHoaks-diagnosa"
BATAS_SOKET = 15.0


def kirim(penyedia, badan: dict, kunci: str, ua: str | None) -> tuple[int | str, str, int]:
    """Mengembalikan (status, isi, ms). Meniru llm.transport_urllib; hanya User-Agent yang bisa diubah.
    ua None = tidak diatur, urllib memakai "Python-urllib/3.x" seperti server sekarang."""
    header = {"Authorization": f"Bearer {kunci}", "Content-Type": "application/json"}
    if ua:
        header["User-Agent"] = ua
    permintaan = urllib.request.Request(
        f"{penyedia.url}/chat/completions", data=json.dumps(badan).encode("utf-8"), headers=header, method="POST"
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(permintaan, timeout=BATAS_SOKET) as r:
            return r.status, r.read().decode("utf-8", errors="replace"), int((time.monotonic() - t0) * 1000)
    except urllib.error.HTTPError as e:
        try:
            isi = e.read(llm.MAKS_BADAN_GALAT).decode("utf-8", errors="replace")
        except Exception:
            isi = ""
        return e.code, isi, int((time.monotonic() - t0) * 1000)
    except Exception as e:
        return f"jaringan:{type(e).__name__}", "", int((time.monotonic() - t0) * 1000)


def sumber_kunci(nama: str) -> str:
    if os.environ.get(nama, "").strip():
        return "variabel lingkungan"
    return ".env" if llm.muat_kunci(nama) else "kosong"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if konfigurasi.kesalahan:
        print(f"Pengaturan tidak sah: {konfigurasi.kesalahan}")
        return 1
    cfg = konfigurasi.pengaturan
    print(f"Berkas .env ada: {'ya' if llm.FILE_ENV.exists() else 'TIDAK'}; LLM aktif: {cfg.llm_aktif}")
    print(f"Batas produksi: groq {cfg.llm_timeout_groq} dtk, gemini {cfg.llm_timeout_gemini} dtk\n")
    baris = []
    for p in llm.URUTAN_PENYEDIA:
        kunci = llm.muat_kunci(p.env)
        awalan = {"groq": "gsk_", "gemini": "AIza"}[p.nama]
        # Awalan hanya informasi (kunci yang berjalan normal tidak perlu berawalan umum).
        print(
            f"{p.nama}: kunci terisi={'ya' if kunci else 'TIDAK'} (sumber: {sumber_kunci(p.env)}), "
            f"awalan umum {awalan}: {'ya' if kunci.startswith(awalan) else 'tidak (informasi saja)'}, model {p.model}"
        )
        if not kunci:
            continue
        dasar = llm._badan(p, TEKS, cfg)
        tanpa_format = {k: v for k, v in dasar.items() if k != "response_format"}
        tanpa_pikir = {k: v for k, v in dasar.items() if k != "reasoning_effort"}
        tanpa_dua = {k: v for k, v in tanpa_format.items() if k != "reasoning_effort"}
        varian = [
            ("UA bawaan urllib (perilaku sebelum perbaikan)", dasar, None),
            (f"produksi (UA {llm.USER_AGENT})", dasar, llm.USER_AGENT),
            (f"UA {UA_LAIN}", dasar, UA_LAIN),
            (f"UA {UA_LAIN}, tanpa response_format", tanpa_format, UA_LAIN),
            (f"UA {UA_LAIN}, tanpa reasoning_effort", tanpa_pikir, UA_LAIN),
            (f"UA {UA_LAIN}, tanpa keduanya", tanpa_dua, UA_LAIN),
        ]
        batas_ms = (cfg.llm_timeout_groq if p.nama == "groq" else cfg.llm_timeout_gemini) * 1000
        for nama_varian, badan, ua in varian:
            status, isi, ms = kirim(p, badan, kunci, ua)
            if status == 200:
                konten = llm._isi_balasan(isi)
                ok = konten is not None and llm.urai_balasan(konten) is not None
                ket, kode = ("balasan terurai" if ok else "balasan TIDAK terurai"), "-"
            else:
                ket, kode = "-", llm.kode_galat(isi) or "-"
            lewat = " (melewati batas produksi)" if ms > batas_ms else ""
            baris.append(f"| {p.nama} | {nama_varian} | {status} | {kode} | {ms}{lewat} | {ket} |")
            time.sleep(2.0)
    print("\n| Penyedia | Varian | Status | Kode galat | ms | Balasan |\n|---|---|---|---|---|---|")
    print("\n".join(baris))
    return 0


if __name__ == "__main__":
    sys.exit(main())
