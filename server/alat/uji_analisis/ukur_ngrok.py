"""Mengukur /analisis lewat alamat ngrok (Sesi 8.2). Server dan ngrok dijalankan developer di jendela terpisah.

Gambar demo dibaca dari server\\data_lokal\\demo (hanya dibaca). Yang dicetak hanya: nama berkas, status HTTP, kode
galat atau tingkat, durasi dari kirim sampai respons, dan durasi_ms server. Teks hasil bacaan tidak dicetak.
Setiap permintaan membawa header ngrok-skip-browser-warning seperti aplikasi.

Mode:
  bersamaan  N permintaan dikirim sekaligus (gambar demo 1-4 bergiliran). Pakai dengan CEKHOAKS_LLM=mati.
  berurutan  N permintaan satu per satu dengan jeda (minimal 8 detik bila LLM menyala).

Contoh (dari folder server):
  .venv\\Scripts\\python.exe alat\\uji_analisis\\ukur_ngrok.py bersamaan --n 4
  .venv\\Scripts\\python.exe alat\\uji_analisis\\ukur_ngrok.py berurutan --n 4 --jeda 8
"""

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

import httpx

URL_BAWAAN = "https://skewer-bundle-viral.ngrok-free.dev"
DEMO = Path(__file__).resolve().parents[2] / "data_lokal" / "demo"
HEADER = {"ngrok-skip-browser-warning": "1"}
JEDA_LLM_MIN = 8.0


def gambar_demo() -> list[Path]:
    berkas = sorted(p for p in DEMO.glob("[1-4]_*.png"))
    if len(berkas) != 4:
        raise SystemExit(f"Gambar demo 1-4 tidak lengkap di {DEMO}")
    return berkas


def ringkas_respons(r: httpx.Response) -> str:
    try:
        isi = r.json()
    except ValueError:
        return f"bukan JSON ({r.headers.get('content-type', '-')})"
    if r.status_code == 200:
        terbatas = ",".join(isi.get("pemeriksaan_terbatas") or []) or "-"
        return f"tingkat={isi.get('tingkat')} terbatas={terbatas} server_ms={isi.get('durasi_ms')}"
    return f"kode={(isi.get('galat') or {}).get('kode')}"


async def kirim(klien: httpx.AsyncClient, url: str, berkas: Path) -> tuple[str, int, float, str]:
    t0 = time.perf_counter()
    try:
        r = await klien.post(f"{url}/analisis", files={"gambar": (berkas.name, berkas.read_bytes(), "image/png")})
        return berkas.name, r.status_code, time.perf_counter() - t0, ringkas_respons(r)
    except httpx.HTTPError as e:
        return berkas.name, 0, time.perf_counter() - t0, type(e).__name__


def cetak(hasil: list[tuple[str, int, float, str]], total: float) -> None:
    for nama, status, detik, ket in hasil:
        print(f"  {nama:<34} {status:>3}  {detik:6.2f} s  {ket}")
    ok = [d for _, s, d, _ in hasil if s == 200]
    sibuk = sum(1 for *_, k in hasil if "server_sibuk" in k)
    print(f"  200: {len(ok)}/{len(hasil)}, server_sibuk: {sibuk}, total {total:.2f} s"
          + (f", median 200 {statistics.median(ok):.2f} s, maks {max(ok):.2f} s" if ok else ""))


async def utama(a) -> int:
    demo = gambar_demo()
    async with httpx.AsyncClient(headers=HEADER, timeout=90.0) as klien:
        r = await klien.get(f"{a.url}/health")
        print(f"/health: {r.status_code} {r.text.strip()[:80]}")
        if r.status_code != 200:
            return 1
        daftar = [demo[i % 4] for i in range(a.n)]
        t0 = time.perf_counter()
        if a.mode == "bersamaan":
            hasil = await asyncio.gather(*(kirim(klien, a.url, b) for b in daftar))
        else:
            hasil = []
            for i, b in enumerate(daftar):
                if i:
                    await asyncio.sleep(a.jeda)
                hasil.append(await kirim(klien, a.url, b))
                print(f"  terkirim {i + 1}/{a.n}")
        cetak(list(hasil), time.perf_counter() - t0)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=("bersamaan", "berurutan"))
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--jeda", type=float, default=JEDA_LLM_MIN)
    p.add_argument("--url", default=URL_BAWAAN)
    a = p.parse_args(argv)
    if a.mode == "berurutan" and a.jeda < JEDA_LLM_MIN:
        raise SystemExit(f"--jeda minimal {JEDA_LLM_MIN} detik")
    return asyncio.run(utama(a))


if __name__ == "__main__":
    sys.exit(main())
