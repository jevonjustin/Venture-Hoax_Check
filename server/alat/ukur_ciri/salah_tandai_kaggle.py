"""Uji salah tandai detektor regex ciri pada dataset Kaggle "Indonesia False News" (Ghazi), Sesi 5.6.

Hanya aturan regex ciri (app/pipeline/ciri.py) dan aturan tingkat (tingkat.py); tanpa LLM, e5, OCR, atau
jaringan. Data hanya dibaca. Dijalankan dari folder server:

    .venv\\Scripts\\python alat\\ukur_ciri\\salah_tandai_kaggle.py [--pola-usulan alat\\ukur_ciri\\pola_usulan_kaggle.json]

Menulis data_lokal\\hasil_analisis\\salah_tandai_kaggle_ghazi.md. Laporan tidak memuat kalimat dataset: contoh
hanya berupa ID baris dan kata pemicu yang dinormalisasi.

Label di Data_latih.csv: 1 = hoaks (positif), 0 = bukan hoaks (negatif). Data_uji.csv tidak berlabel dan tidak
dipakai. Teks diuji dalam dua tampilan: "judul" saja dan "gabungan" (judul + narasi). Teks tidak melewati
bersih.py (itu untuk keluaran OCR; berita sudah berupa teks polos).

Berkas pola usulan (opsional) berisi {"id_ciri": ["regex pengecualian", ...]}. Kecocokan yang tumpang tindih dengan
kecocokan regex pengecualian (tanpa membedakan huruf besar kecil, pada teks yang sudah dirapikan) dibuang sebelum
bukti dikumpulkan. Dampaknya dilaporkan berdampingan dengan hasil bawaan.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER))

import dataclasses  # noqa: E402

from app.konfigurasi import pengaturan as pengaturan_bawaan  # noqa: E402
from app.pipeline import ciri, tingkat  # noqa: E402
from app.pipeline.tipe import CiriRegex  # noqa: E402
from app.skema import Tingkat  # noqa: E402

DATA = SERVER / "data_lokal" / "dataset_mentah" / "kaggle_ghazi" / "Data_latih.csv"
LAPORAN = SERVER / "data_lokal" / "hasil_analisis" / "salah_tandai_kaggle_ghazi.md"
TAMPILAN = ("gabungan", "judul")
pengaturan = pengaturan_bawaan  # diganti main() bila --rasio-kapital dipakai (hanya untuk simulasi usulan)

_DAFTAR_POLA = {
    "permintaan_data_rahasia": ciri._PERMINTAAN,
    "ajakan_menyebarkan": ciri._AJAKAN,
    "link_mencurigakan": ciri._LINK_KUAT,
    **{k: v for k, v in ciri._POLA.items() if k not in ("permintaan_data_rahasia", "ajakan_menyebarkan")},
}


def muat(jalur: Path = DATA) -> list[dict]:
    with open(jalur, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("label") in ("0", "1")]


def teks_tampilan(baris: dict, tampilan: str) -> str:
    judul, narasi = (baris.get("judul") or "").strip(), (baris.get("narasi") or "").strip()
    return judul if tampilan == "judul" else f"{judul}. {narasi}"


def cocok_ciri(id_ciri: str, datar: str) -> list[tuple[int, int, str]]:
    """Sama dengan cabang di ciri.deteksi_regex (fungsi pencocok privat yang sama)."""
    if id_ciri == "ajakan_menyebarkan":
        return ciri._cocok_ajakan(datar)
    if id_ciri == "link_mencurigakan":
        return ciri._cocok_tautan(datar)
    if id_ciri == "permintaan_data_rahasia":
        return ciri._cocok_permintaan(datar)
    if id_ciri == "kapital_tanda_seru":
        return ciri._cocok_kapital(datar, pengaturan)
    return ciri._cocok_pola(ciri._POLA[id_ciri], datar)


def _saring(cocok, datar: str, pola_pengecualian) -> list[tuple[int, int, str]]:
    for pola in pola_pengecualian:
        spans = [m.span() for m in pola.finditer(datar)]
        cocok = [c for c in cocok if not any(c[0] < b and a < c[1] for a, b in spans)]
    return cocok


def nama_pola(id_ciri: str, datar: str, s: int, e: int) -> str:
    if id_ciri == "kapital_tanda_seru":
        potongan = datar[s:e]
        if re.fullmatch(r"[!\s]+", potongan):
            return "seru_beruntun"
        return "kalimat_kapital_seru" if potongan.endswith("!") else "rasio_kapital"
    for i, (_, pola) in enumerate(_DAFTAR_POLA.get(id_ciri, [])):
        if any(m.span() == (s, e) for m in pola.finditer(datar)):
            return f"{id_ciri}#{i}"
    return f"{id_ciri}#url_umum" if id_ciri == "link_mencurigakan" else f"{id_ciri}#?"


def pemicu(id_ciri: str, datar: str, s: int, e: int) -> str:
    """Kata pemicu yang dinormalisasi: huruf kecil, angka jadi '#', dan hanya token pertama dan terakhir bila
    kecocokan lebih dari tiga token (celah pola bisa memuat nama atau kalimat)."""
    if id_ciri == "kapital_tanda_seru":
        return "(kapital/seru)"
    potongan = datar[s:e].lower()
    if id_ciri == "link_mencurigakan":
        host = re.sub(r"^(?:https?://)?(?:www\.)?", "", potongan).split("/")[0]
        return re.sub(r"\d", "#", host)[:40]
    token = re.sub(r"\d", "#", potongan).split()
    if len(token) > 3:
        token = [token[0], "...", token[-1]]
    return " ".join(token)[:40]


def deteksi(teks: str, pengecualian: dict[str, list[re.Pattern]] | None = None) -> list[CiriRegex]:
    """Tanpa pengecualian: persis ciri.deteksi_regex. Dengan pengecualian: logika yang sama, kecocokan yang
    tumpang tindih dengan pola pengecualian dibuang lebih dulu."""
    if not pengecualian and pengaturan is pengaturan_bawaan:
        return ciri.deteksi_regex(teks)
    datar = ciri._rapikan(teks)
    hasil = []
    for id_ciri in ciri.ID_BISA_DITANDAI:
        cocok = _saring(cocok_ciri(id_ciri, datar), datar, (pengecualian or {}).get(id_ciri, []))
        if not cocok:
            continue
        bukti, n_kuat = ciri._kumpulkan_bukti(datar, cocok, pengaturan)
        if bukti:
            kuat = any(c[2] == ciri.KUAT for c in cocok)
            hasil.append(CiriRegex(id_ciri, ciri.KUAT if kuat else ciri.LEMAH, bukti, n_kuat))
    return hasil


def varian_tanpa_artikel(hasil_regex: list[CiriRegex], teks: str, kuat_saja: bool) -> str:
    """Varian putusan dari tingkat.tentukan dengan daftar artikel kosong. kuat_saja meniru produksi saat LLM
    berhasil tetapi tidak menyetujui ciri lemah (ciri lemah dibuang); bila tidak, meniru LLM gagal (kuat jadi
    tinggi, lemah jadi sedang)."""
    masuk = [c for c in hasil_regex if c.kekuatan == ciri.KUAT] if kuat_saja else hasil_regex
    ciri_final = ciri.gabung_ciri(masuk, None, teks)
    p = tingkat.tentukan(ciri_final, [], teks)
    return p.varian if p.tingkat is Tingkat.HATI_HATI else ""


def ukur(baris: list[dict], tampilan: str, pengecualian=None) -> dict:
    n = Counter(int(b["label"]) for b in baris)
    per_ciri = {i: {0: Counter(), 1: Counter()} for i in ciri.ID_BISA_DITANDAI}
    tk = {m: {0: Counter(), 1: Counter()} for m in ("llm_gagal", "kuat_saja")}
    pola = defaultdict(lambda: {0: Counter(), 1: Counter()})  # (id, nama, kekuatan) -> label -> Counter
    kata = defaultdict(lambda: {0: Counter(), 1: Counter()})  # (id, kekuatan, pemicu) -> label -> Counter
    contoh = defaultdict(list)  # (id, label, kekuatan) -> [ID baris]
    for b in baris:
        teks, label = teks_tampilan(b, tampilan), int(b["label"])
        hasil = deteksi(teks, pengecualian)
        datar = ciri._rapikan(teks)
        for c in hasil:
            per_ciri[c.id][label]["ada"] += 1
            per_ciri[c.id][label][c.kekuatan] += 1
            if len(contoh[(c.id, label, c.kekuatan)]) < 3:
                contoh[(c.id, label, c.kekuatan)].append(b["ID"])
            cocok = _saring(cocok_ciri(c.id, datar), datar, (pengecualian or {}).get(c.id, []))
            dilihat = set()
            for s, e, k in cocok:
                kunci_p = ("p", c.id, nama_pola(c.id, datar, s, e), k)
                kunci_k = ("k", c.id, k, pemicu(c.id, datar, s, e))
                for kunci, sasaran in ((kunci_p, pola), (kunci_k, kata)):
                    if kunci not in dilihat:
                        dilihat.add(kunci)
                        sasaran[kunci[1:]][label]["n"] += 1
        for mode, kuat_saja in (("llm_gagal", False), ("kuat_saja", True)):
            v = varian_tanpa_artikel(hasil, teks, kuat_saja)
            tk[mode][label]["ciri_saja"] += v == tingkat.VARIAN_CIRI_SAJA
    return {"n": n, "ciri": per_ciri, "tingkat": tk, "pola": pola, "kata": kata, "contoh": contoh}


def persen(a: int, n: int) -> str:
    return f"{100 * a / n:.1f}%" if n else "-"


def tabel_ciri(h: dict, h2: dict | None = None) -> list[str]:
    n0, n1 = h["n"][0], h["n"][1]
    kepala = "| ciri | neg tinggi | neg sedang | neg total | pos tinggi | pos sedang | pos total |"
    if h2:
        kepala += " neg tinggi (usulan) | neg total (usulan) | pos total (usulan) |"
    baris = [kepala, "|" + "---|" * (kepala.count("|") - 1)]
    for i in ciri.ID_BISA_DITANDAI:
        a0, a1 = h["ciri"][i][0], h["ciri"][i][1]
        sel = (
            f"| {i} | {a0['kuat']} ({persen(a0['kuat'], n0)}) | {a0['lemah']} ({persen(a0['lemah'], n0)}) "
            f"| {a0['ada']} ({persen(a0['ada'], n0)}) | {a1['kuat']} ({persen(a1['kuat'], n1)}) "
            f"| {a1['lemah']} ({persen(a1['lemah'], n1)}) | {a1['ada']} ({persen(a1['ada'], n1)}) |"
        )
        if h2:
            b0, b1 = h2["ciri"][i][0], h2["ciri"][i][1]
            sel += (
                f" {b0['kuat']} ({persen(b0['kuat'], n0)}) | {b0['ada']} ({persen(b0['ada'], n0)}) "
                f"| {b1['ada']} ({persen(b1['ada'], n1)}) |"
            )
        baris.append(sel)
    return baris


def tabel_tingkat(h: dict, h2: dict | None = None) -> list[str]:
    n0, n1 = h["n"][0], h["n"][1]
    kepala = "| skenario | neg jadi hati_hati ciri_saja | pos jadi hati_hati ciri_saja |"
    if h2:
        kepala += " neg (usulan) | pos (usulan) |"
    baris = [kepala, "|" + "---|" * (kepala.count("|") - 1)]
    nama = {
        "llm_gagal": "LLM gagal (kuat=tinggi, lemah=sedang)",
        "kuat_saja": "hanya ciri regex kuat (ciri lemah dibuang, mirip LLM berhasil tanpa persetujuan ciri lemah)",
    }
    for m in ("llm_gagal", "kuat_saja"):
        t0, t1 = h["tingkat"][m][0]["ciri_saja"], h["tingkat"][m][1]["ciri_saja"]
        sel = f"| {nama[m]} | {t0} ({persen(t0, n0)}) | {t1} ({persen(t1, n1)}) |"
        if h2:
            u0, u1 = h2["tingkat"][m][0]["ciri_saja"], h2["tingkat"][m][1]["ciri_saja"]
            sel += f" {u0} ({persen(u0, n0)}) | {u1} ({persen(u1, n1)}) |"
        baris.append(sel)
    return baris


def bagian_pola(h: dict, id_ciri: str, atas: int = 6) -> list[str]:
    keluar = []
    for judul, sumber in (("Pola", h["pola"]), ("Kata pemicu", h["kata"])):
        baris = [(k, v[0]["n"], v[1]["n"]) for k, v in sumber.items() if k[0] == id_ciri and v[0]["n"]]
        baris.sort(key=lambda x: -x[1])
        if not baris:
            continue
        keluar.append(f"  - {judul} teratas pada negatif (jumlah teks neg / pos):")
        for k, n0, n1 in baris[:atas]:
            keluar.append(f"    - `{k[1]}` ({k[2]}): {n0} / {n1}" if judul == "Pola" else f"    - `{k[2]}` ({k[1]}): {n0} / {n1}")
    return keluar


def tulis_laporan(baris, hasil, hasil_usulan, nama_usulan) -> str:
    n0 = sum(1 for b in baris if b["label"] == "0")
    n1 = len(baris) - n0
    k = [
        "# Salah tandai regex ciri pada dataset Indonesia False News (Ghazi)",
        "",
        f"Data_latih.csv: {n1} teks hoaks (label 1, positif) dan {n0} teks bukan hoaks (label 0, negatif). "
        "Data_uji.csv tidak berlabel, tidak dipakai. Hanya aturan regex ciri dan aturan tingkat (daftar artikel kosong); "
        "tanpa LLM, e5, OCR.",
        "",
        "Catatan: dataset ini berupa teks polos (berita dan klaim), bukan screenshot. Angka di sini batas atas: di produksi "
        "ciri lemah tanpa persetujuan LLM dibuang dan satu ciri sedang tidak menaikkan tingkat (lihat skenario "
        "\"hanya ciri regex kuat\"). \"tinggi\" = pola regex kuat; \"sedang\" = hanya pola lemah. Contoh hanya "
        "berupa ID baris dan kata pemicu.",
        "",
    ]
    for t in TAMPILAN:
        h, h2 = hasil[t], (hasil_usulan or {}).get(t)
        k += [f"## Tampilan: {t}", "", "### Ciri ditandai (jumlah teks dan persen dari kelasnya)", ""]
        k += tabel_ciri(h, h2) + ["", "### Tingkat hati_hati varian ciri_saja tanpa artikel", ""] + tabel_tingkat(h, h2) + [""]
        k += ["### Pola penyebab per ciri (ciri dengan salah tandai total >= 1% pada negatif)", ""]
        for i in ciri.ID_BISA_DITANDAI:
            a0 = h["ciri"][i][0]
            if not a0["ada"] or a0["ada"] / h["n"][0] < 0.01:
                continue
            k.append(f"- **{i}**: neg tinggi {a0['kuat']}, sedang {a0['lemah']}")
            k += bagian_pola(h, i)
            for kek in (ciri.KUAT, ciri.LEMAH):
                ids = h["contoh"].get((i, 0, kek), [])
                if ids:
                    k.append(f"  - contoh ID negatif ({kek}): {', '.join(ids)}")
        k.append("")
    if nama_usulan:
        k += [f"Pola usulan dimuat dari `{nama_usulan}`; kolom \"usulan\" menunjukkan dampaknya.", ""]
    return "\n".join(k) + "\n"


def muat_usulan(jalur: Path) -> dict[str, list[re.Pattern]]:
    data = json.loads(jalur.read_text(encoding="utf-8"))
    return {
        i: [re.compile(p, re.IGNORECASE) for p in daftar]
        for i, daftar in data.items()
        if i in ciri.ID_BISA_DITANDAI
    }


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pola-usulan", type=Path, help="JSON {id_ciri: [regex pengecualian]} untuk menghitung dampak")
    ap.add_argument("--rasio-kapital", type=float, help="simulasi usulan: ambang rasio huruf kapital (bawaan 0,4)")
    ap.add_argument("--keluar", type=Path, default=LAPORAN)
    args = ap.parse_args(argv)
    global pengaturan
    baris = muat()
    hasil = {t: ukur(baris, t) for t in TAMPILAN}
    usulan = None
    if args.pola_usulan or args.rasio_kapital:
        peng = muat_usulan(args.pola_usulan) if args.pola_usulan else {}
        if args.rasio_kapital:
            pengaturan = dataclasses.replace(pengaturan_bawaan, ciri_kapital_rasio=args.rasio_kapital)
        usulan = {t: ukur(baris, t, peng) for t in TAMPILAN}
    args.keluar.parent.mkdir(parents=True, exist_ok=True)
    nama = " + ".join(
        x for x in (args.pola_usulan.name if args.pola_usulan else "", f"rasio_kapital={args.rasio_kapital}" if args.rasio_kapital else "") if x
    ) or None
    args.keluar.write_text(tulis_laporan(baris, hasil, usulan, nama), encoding="utf-8")
    print(f"Laporan: {args.keluar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
