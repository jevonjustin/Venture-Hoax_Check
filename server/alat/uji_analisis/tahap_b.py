"""Menjalankan pipeline lengkap (Tahap B, dengan LLM bila kunci terisi dan tidak dimatikan) pada screenshot uji,
menulis tabel ringkasan, dan membandingkannya dengan tahap_a.md (tingkat, ciri, klaim, durasi).

Perintah (dari folder server, venv server; MEMANGGIL API LLM bila kunci terisi di server\\.env):
  .venv\\Scripts\\python.exe alat\\uji_analisis\\tahap_b.py

Opsi:
  --nama NAMA        nama berkas hasil (bawaan: tahap_b) di server\\data_lokal\\hasil_analisis\\
  --acuan BERKAS     berkas pembanding di folder yang sama (bawaan: tahap_a.md)
  --jeda DETIK       jeda antar gambar (bawaan 10; 0 bila --tanpa-llm). Paket gratis Groq: 8.000 token per menit, sekitar 1.100 token
                     per gambar, jadi 10 detik (ditambah waktu OCR) menjaga pemakaian di bawah batas.
  --cadangan         izinkan Gemini sebagai cadangan. Bawaan: dimatikan, supaya hasil seluruhnya Groq dan teks
                     tidak dikirim ke Google. Groq yang kena 429 ditunggu sesuai Retry-After lalu gambar diulang.
  --ulang-429 N      berapa kali satu gambar diulang setelah Groq kena 429 (bawaan 3)
  --tanpa-llm        tidak memanggil API LLM sama sekali (tanpa jaringan; ciri hanya dari regex)
Tanpa memanggil API: pakai --tanpa-llm (atau set CEKHOAKS_LLM=mati). Contoh perbandingan dua putaran:
  tahap_b.py --tanpa-llm --nama tanpa_llm   lalu   tahap_b.py --nama dengan_llm --acuan tanpa_llm.md

Teks gambar, klaim, dan judul artikel ikut tertulis di berkas hasil (lokal, di data_lokal yang diabaikan git).
Gambar hanya dibaca dari disk. Tidak ada kunci yang dicetak atau ditulis.
"""

import argparse
import asyncio
import re
import statistics
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tahap_a import (  # noqa: E402
    FOLDER_GAMBAR, FOLDER_HASIL, LABEL_SALAH, SERVER, kunci_slug, muat_sumber, ringkas_artikel, sebagai_png, sel,
    tidak_putus,
)

sys.path.insert(0, str(SERVER))
from app import konfigurasi  # noqa: E402
from app.galat import GalatApi  # noqa: E402
from app.pipeline import cocok, llm, orkestrator  # noqa: E402
from app.pipeline.tipe import Konteks  # noqa: E402


def baca_acuan(jalur: Path) -> dict[str, dict]:
    """Membaca tabel dan klaim dari berkas hasil Tahap A: {nomor: {tingkat, ciri, klaim, ms}}."""
    if not jalur.exists():
        return {}
    teks = jalur.read_text(encoding="utf-8")
    hasil: dict[str, dict] = {}
    for baris in teks.splitlines():
        m = re.match(r"\| (\d\d)\b", baris)
        if not m:
            continue
        kolom = [k.strip() for k in baris.strip().strip("|").split(" | ")]
        if len(kolom) >= 7:
            ciri = {c.split(" (")[0] for c in kolom[5].split(", ") if c and c != "-"}
            hasil[m.group(1)] = {"tingkat": kolom[1], "ciri": ciri, "ms": kolom[6]}
        else:
            hasil[m.group(1)] = {"tingkat": kolom[1], "ciri": set(), "ms": ""}
    for m in re.finditer(r"### (\d\d) .*?(?=\n### |\Z)", teks, re.S):
        k = [b for b in m.group(0).splitlines() if b.startswith("- Klaim")]
        if m.group(1) in hasil and k:
            hasil[m.group(1)]["klaim"] = k[0].split(": ", 1)[1]
    return hasil


def persentil(nilai: list[int], p: float) -> int:
    if not nilai:
        return 0
    urut = sorted(nilai)
    return urut[min(len(urut) - 1, max(0, round(p / 100 * (len(urut) - 1))))]


def groq_kena_429(info: dict) -> float | None:
    """Detik tunggu yang disarankan bila Groq kena 429 pada gambar ini dan hasilnya tidak berasal dari Groq."""
    jejak = info.get("jejak") or []
    if info.get("penyedia") == "groq" or not any(j["penyedia"] == "groq" and j["status"] == 429 for j in jejak):
        return None
    saran = [j["tunggu"] for j in jejak if j["penyedia"] == "groq" and j["status"] == 429 and j.get("tunggu") is not None]
    return min(90.0, max(saran + [10.0])) + 1.0


def konfirmasi(ringkasan: dict[str, tuple[str, dict[str, str]]]) -> list[str]:
    """Pemeriksaan hasil yang harus tetap: 03, 06, 08 hati_hati dengan permintaan_data_rahasia tinggi; 07 tanpa
    ciri dan tidak_ditemukan."""
    baris = ["## Konfirmasi"]
    for nomor in ("03", "06", "08"):
        if nomor not in ringkasan:
            baris.append(f"- {nomor}: tidak ada hasil")
            continue
        tingkat_, ciri_ = ringkasan[nomor]
        ok = tingkat_ == "hati_hati" and ciri_.get("permintaan_data_rahasia") == "tinggi"
        baris.append(f"- {nomor}: {'OK' if ok else 'TIDAK SESUAI'} (tingkat {tingkat_}, permintaan_data_rahasia "
                     f"{ciri_.get('permintaan_data_rahasia', 'tidak ada')})")
    if "07" in ringkasan:
        tingkat_, ciri_ = ringkasan["07"]
        ok = tingkat_ == "tidak_ditemukan" and not ciri_
        baris.append(f"- 07: {'OK' if ok else 'TIDAK SESUAI'} (tingkat {tingkat_}, ciri {', '.join(ciri_) or 'tidak ada'})")
    return baris


def token_gambar(info: dict) -> tuple[int, int]:
    """Jumlah token prompt dan completion semua percobaan sukses pada satu gambar."""
    p = c = 0
    for j in info.get("jejak") or []:
        t = j.get("token") or {}
        p += t.get("prompt", 0)
        c += t.get("completion", 0)
    return p, c


async def jalankan_semua(
    nama: str, acuan_nama: str, jeda: float, cadangan: bool, maks_ulang: int, tanpa_llm: bool = False
) -> str:
    if konfigurasi.kesalahan:
        raise SystemExit(f"Pengaturan tidak sah: {konfigurasi.kesalahan}")
    cfg = konfigurasi.pengaturan
    cfg.llm_cadangan_aktif = cadangan
    if tanpa_llm:
        cfg.llm_aktif = False
    await cocok.pencarian.siapkan()
    if cocok.pencarian.status != cocok.STATUS_SIAP:
        raise SystemExit(f"Pencarian tidak siap: {cocok.pencarian.ringkasan()}")
    sumber = muat_sumber()
    indeks = {}
    for a in cocok.pencarian._artikel:
        indeks.setdefault(kunci_slug(a.get("url", "")), a)
    acuan = baca_acuan(FOLDER_HASIL / acuan_nama)

    baris_tabel, detail, perbandingan = [], [], []
    durasi, durasi_llm, penyedia_hitung = [], [], {}
    tingkat_hitung = {"kuat": 0, "hati_hati": 0, "tidak_ditemukan": 0, "galat": 0}
    klaim_llm_dipakai = klaim_total = peringkat1 = ada_sumber = 0
    token_per_gambar: list[int] = []
    token_per_permintaan: list[int] = []
    ringkasan_gambar: dict[str, tuple[str, dict[str, str]]] = {}  # nomor -> (tingkat, {id ciri: keyakinan})
    daftar_dibuang: list[str] = []
    kutipan_ditolak_total = gugur_total = 0
    sumber_klaim_hitung: dict[str, int] = {}

    gambar = sorted(FOLDER_GAMBAR.iterdir())
    for urutan, jalur in enumerate(gambar):
        nomor = jalur.stem
        if urutan and jeda > 0:
            time.sleep(jeda)
        url_sumber = sumber.get(jalur.name, "")
        a_sumber = indeks.get(kunci_slug(url_sumber)) if url_sumber else None
        try:
            for ke in range(maks_ulang + 1):
                diag: dict = {}
                ctx = Konteks(
                    id_permintaan=uuid.uuid4().hex, jeda_detik=(0.0, 0.0), klien_putus=tidak_putus, diagnostik=diag
                )
                hasil = await orkestrator.jalankan(sebagai_png(jalur), ctx)
                tunggu = groq_kena_429(diag.get("llm") or {})
                if tunggu is None or ke == maks_ulang:
                    break
                print(f"{nomor}: Groq kena 429, menunggu {tunggu:.0f} dtk lalu mengulang gambar ({ke + 1}/{maks_ulang})", flush=True)
                time.sleep(tunggu)
        except GalatApi as e:
            tingkat_hitung["galat"] += 1
            baris_tabel.append(f"| {nomor} | galat `{e.kode}` | | | | | | | | | | |")
            perbandingan.append(f"| {nomor} | {acuan.get(nomor, {}).get('tingkat', '-')} | galat `{e.kode}` | | |")
            continue
        putusan = diag["putusan"]
        info = diag.get("llm") or {}
        durasi.append(hasil.durasi_ms)
        tingkat_hitung[hasil.tingkat.value] += 1
        penyedia = info.get("penyedia") or "-"
        jejak = " -> ".join(
            f"{j['penyedia']}:{j['status']}" + (f"({j['kode']})" if j.get("kode") else "") for j in info.get("jejak") or []
        ) or "-"
        penyedia_hitung[penyedia] = penyedia_hitung.get(penyedia, 0) + 1
        if info.get("durasi_ms") is not None:
            durasi_llm.append(info["durasi_ms"])
        tok_p, tok_c = token_gambar(info)
        if tok_p or tok_c:
            token_per_gambar.append(tok_p + tok_c)
        token_per_permintaan += [
            (j["token"].get("prompt", 0) + j["token"].get("completion", 0)) for j in info.get("jejak") or [] if j.get("token")
        ]
        ket_token = f"{tok_p}/{tok_c}" if tok_p or tok_c else "-"
        print(f"{nomor}: {hasil.tingkat.value}, penyedia {penyedia}, token {ket_token}", flush=True)
        klaim_total += 1 if hasil.klaim_utama else 0
        klaim_llm_dipakai += 1 if info.get("klaim_dipakai") else 0
        if a_sumber:
            ada_sumber += 1
            peringkat1 += bool(diag["kandidat"]) and diag["kandidat"][0].url == a_sumber.get("url")

        ciri_baru = {c.id for c in hasil.ciri}
        sumber_klaim = diag.get("klaim_sumber", "-")
        gugur = diag.get("klaim_gugur_percakapan", 0)
        ditolak = info.get("kutipan_ditolak")
        sumber_klaim_hitung[sumber_klaim] = sumber_klaim_hitung.get(sumber_klaim, 0) + 1
        gugur_total += gugur
        kutipan_ditolak_total += ditolak or 0
        ringkasan_gambar[nomor] = (hasil.tingkat.value, {c.id: c.keyakinan for c in hasil.ciri})
        for d_ in diag.get("ciri_dibuang") or []:
            daftar_dibuang.append(f"- {nomor}: `{d_['id']}` [{d_['alasan']}] {sel(d_['bukti'])[:110]}")
        tingkat_ket = hasil.tingkat.value + (f" / {putusan.varian}" if putusan.varian else "")
        ciri_ket = ", ".join(f"{c.id} ({c.keyakinan})" for c in hasil.ciri) or "-"
        terbatas = ", ".join(hasil.pemeriksaan_terbatas) or "-"
        baris_tabel.append(
            f"| {nomor} | {tingkat_ket} | {sel(hasil.klaim_utama or '(kosong)')[:90]} | {penyedia} [{jejak}] | "
            f"{len(putusan.cek_fakta)} | {sel(ciri_ket)} | {terbatas} | {hasil.durasi_ms} | {ket_token} | "
            f"{sumber_klaim} | {'-' if ditolak is None else ditolak} | {gugur} |"
        )

        a = acuan.get(nomor, {})
        ubah_ciri = []
        if a:
            ubah_ciri = [f"+{c}" for c in sorted(ciri_baru - a["ciri"])] + [f"-{c}" for c in sorted(a["ciri"] - ciri_baru)]
        perbandingan.append(
            f"| {nomor} | {a.get('tingkat', '-')} | {tingkat_ket} | {' '.join(ubah_ciri) or 'sama'} | "
            f"{sel(a.get('klaim', '-'))[:60]} -> {sel(hasil.klaim_utama or '(kosong)')[:60]} |"
        )

        d = [f"### {nomor} — {tingkat_ket} (penyedia: {penyedia}; percobaan: {jejak})", ""]
        d.append(f"- Klaim: {sel(hasil.klaim_utama or '(kosong)')[:200]}")
        if info.get("klaim") is not None:
            d.append(
                f"- Klaim LLM: {sel(info['klaim'] or '(kosong)')[:160]} | kesetiaan {info['kesetiaan']:.2f} | "
                f"dipakai: {'ya' if info['klaim_dipakai'] else 'tidak'} | kutipan ditolak: {info['kutipan_ditolak']} | "
                f"percobaan: {info['percobaan']} | {info['durasi_ms']} ms"
            )
        for c in hasil.ciri:
            d.append(f"- Ciri `{c.id}` ({c.keyakinan}): " + "; ".join(sel(b)[:100] for b in c.bukti))
        for k in diag["kandidat"][:3]:
            tanda = " ★sumber" if a_sumber and k.url == a_sumber.get("url") else ""
            d.append(f"- Artikel: {ringkas_artikel(k)}{tanda}")
        salah_tampil = [k for k in putusan.cek_fakta if k.label in LABEL_SALAH]
        if not a_sumber and salah_tampil:
            d.append("- ⚠ tanpa artikel sumber di DB, tetapi ada artikel salah/penipuan yang tampil (nilai manual)")
        detail.append("\n".join(d))

    ringkas = [
        "# Hasil Tahap B (pipeline lengkap)", "",
        f"Pencarian: {cocok.pencarian.ringkasan()}. LLM: {llm.ringkasan_status(cfg)}.",
        f"Anggaran LLM: groq {cfg.llm_timeout_groq} dtk, gemini {cfg.llm_timeout_gemini} dtk, total {cfg.llm_anggaran_total} dtk. "
        f"Ambang: cocok {cfg.ambang_cocok}, mirip {cfg.ambang_mirip}, relevansi {cfg.relevansi_minimum}, "
        f"kesetiaan klaim {cfg.klaim_kesetiaan_minimum}, skor klaim minimum {cfg.klaim_skor_minimum}.", "",
        f"Tingkat: kuat {tingkat_hitung['kuat']}, hati_hati {tingkat_hitung['hati_hati']}, "
        f"tidak_ditemukan {tingkat_hitung['tidak_ditemukan']}, galat {tingkat_hitung['galat']}. "
        f"Artikel sumber peringkat 1: {peringkat1}/{ada_sumber}.",
        f"Penyedia LLM: " + ", ".join(f"{k} {v}" for k, v in sorted(penyedia_hitung.items())) + ".",
        f"Klaim dari LLM dipakai pada {klaim_llm_dipakai} dari {klaim_total} gambar yang punya klaim.",
        f"Durasi total (ms, termasuk OCR): median {int(statistics.median(durasi)) if durasi else 0}, "
        f"p95 {persentil(durasi, 95)}, maks {max(durasi) if durasi else 0}.",
        f"Durasi tahap LLM (ms): median {int(statistics.median(durasi_llm)) if durasi_llm else 0}, "
        f"p95 {persentil(durasi_llm, 95)} (n={len(durasi_llm)}).",
        f"Token per permintaan sukses (prompt+completion): rata-rata "
        f"{int(statistics.mean(token_per_permintaan)) if token_per_permintaan else 0}, "
        f"maks {max(token_per_permintaan) if token_per_permintaan else 0} (n={len(token_per_permintaan)}). "
        f"Per gambar: rata-rata "
        f"{int(statistics.mean(token_per_gambar)) if token_per_gambar else 0}, maks {max(token_per_gambar) if token_per_gambar else 0}.",
        f"Jeda antar gambar {jeda:.0f} dtk; cadangan Gemini {'aktif' if cadangan else 'dimatikan'}.",
        "Sumber klaim: " + ", ".join(f"{k} {v}" for k, v in sorted(sumber_klaim_hitung.items())) + ".",
        f"Kutipan LLM ditolak (tidak ada di teks): {kutipan_ditolak_total} pada seluruh gambar. "
        f"Kandidat klaim heuristik gugur karena kata ganti kedua, orang pertama, atau sapaan: {gugur_total}.",
        "", *konfirmasi(ringkasan_gambar), "",
        "| Gambar | Tingkat / varian | Klaim | Penyedia | cek_fakta | Ciri (keyakinan) | Terbatas | ms | "
        "Token (prompt/completion) | Klaim dari | Kutipan ditolak | Gugur obrolan |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
        *baris_tabel, "",
        "## Bukti dan ciri yang dibuang (pengaman struktural, aturan sumber_tidak_jelas, ciri sedang tunggal)", "",
        *(daftar_dibuang or ["(tidak ada)"]), "",
        f"## Perbandingan dengan {acuan_nama}", "",
        "| Gambar | Tingkat Tahap A | Tingkat sekarang | Perubahan ciri | Klaim: sebelum -> sesudah |",
        "|---|---|---|---|---|",
        *perbandingan, "", "## Rincian", "", *detail, "",
    ]
    FOLDER_HASIL.mkdir(parents=True, exist_ok=True)
    keluaran = FOLDER_HASIL / f"{nama}.md"
    keluaran.write_text("\n".join(ringkas), encoding="utf-8")
    return str(keluaran)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nama", default="tahap_b")
    p.add_argument("--acuan", default="tahap_a.md")
    p.add_argument("--jeda", type=float, default=None)
    p.add_argument("--cadangan", action="store_true")
    p.add_argument("--tanpa-llm", action="store_true", dest="tanpa_llm")
    p.add_argument("--ulang-429", type=int, default=3, dest="ulang_429")
    a = p.parse_args()
    if a.jeda is None:  # tanpa LLM tidak ada kuota yang perlu dijaga
        a.jeda = 0.0 if a.tanpa_llm else 10.0
    print(f"Tabel ditulis ke {asyncio.run(jalankan_semua(a.nama, a.acuan, a.jeda, a.cadangan, a.ulang_429, a.tanpa_llm))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
