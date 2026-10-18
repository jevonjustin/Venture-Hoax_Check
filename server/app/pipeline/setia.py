"""Pemeriksaan kesetiaan klaim LLM pada teks layar (Sesi 5.6). Dipanggil dari `llm.klaim_dapat_dipakai` hanya
bila `Pengaturan.periksa_kesetiaan_klaim` menyala. Klaim yang gagal diganti klaim heuristik oleh orkestrator.

Empat pemeriksaan, berurutan; yang pertama gagal menentukan kode alasan:
1. `angka_baru`: angka/nominal/tanggal di klaim harus ada di teks (pemisah ribuan, "Rp", "%", "jt/juta" dinormalkan).
2. `entitas_baru`: token nama (berhuruf kapital bukan awal kalimat, singkatan huruf kapital semua, dan awal kalimat
   bila diikuti token kapital lain) harus ada di teks, toleran salah eja OCR.
3. `kata_berat_baru`: kata penilaian/tuduhan (penipu, hoaks, palsu, ...) yang tidak ada di teks.
4. `kata_pengganti`: kata isi baru yang mirip kata lain di teks tetapi berkata dasar berbeda ("digelapkan" untuk
   "digelandang"); lalu `kata_baru_banyak`: bagian kata isi baru melebihi ambang.

Privasi: hasil hanya (kode, jumlah token); tidak ada teks klaim atau teks layar yang dikembalikan atau dicatat."""

import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from ..konfigurasi import Pengaturan
from . import cocok

KODE_ANGKA = "angka_baru"
KODE_ENTITAS = "entitas_baru"
KODE_BERAT = "kata_berat_baru"
KODE_PENGGANTI = "kata_pengganti"
KODE_BANYAK = "kata_baru_banyak"
KODE_NEGASI = "negasi"

NEGASI = frozenset({"tidak", "tak", "bukan", "belum", "tanpa", "jangan", "enggak", "nggak", "gak", "ga", "ngga", "ndak"})
JANGKAUAN_NEGASI = 3  # token setelah penanda negasi yang dianggap terkena negasi
# Kata sambung/depan yang mengakhiri jangkauan negasi ("tanpa pengalaman, dengan biaya": biaya tidak dinegasikan).
PEMUTUS_NEGASI = frozenset({"dengan", "dan", "serta", "tetapi", "tapi", "namun", "atau", "karena", "sehingga", "untuk", "agar",
                            "melainkan", "sedangkan", "padahal"})

# Kata dasar penilaian/tuduhan yang tidak boleh ditambahkan LLM.
KATA_BERAT = frozenset({
    "tipu", "hoaks", "hoax", "palsu", "bohong", "dusta", "fitnah", "korup", "korupsi", "curi", "maling", "salah",
    "benar", "fakta", "keliru", "sesat", "terbukti", "disinformasi", "scam", "tersangka", "tangkap", "bunuh",
    "pidana", "teror",
})

_BUKAN_NAMA = frozenset({"rp", "wib", "wita", "wit"})  # satuan/zona waktu, bukan nama
_AWALAN = ("meng", "meny", "men", "mem", "me", "peng", "peny", "pen", "pem", "pe", "di", "ber", "ter")
_AKHIRAN = ("nya", "kan", "an")
_PENGGANTI_HURUF = {"meng": "k", "meny": "s", "men": "t", "mem": "p", "peng": "k", "peny": "s", "pen": "t", "pem": "p"}
_PENGALI = {
    "ribu": 10**3, "rb": 10**3, "juta": 10**6, "jt": 10**6, "miliar": 10**9, "milyar": 10**9, "m": 10**9,
    "triliun": 10**12, "t": 10**12,
}
_ANGKA = re.compile(r"(\d[\d.,]*)(?:\s*(ribu|rb|juta|jt|miliar|milyar|triliun)\b)?", re.IGNORECASE)


def _angka_ke_nilai(mentah: str) -> Decimal | None:
    mentah = mentah.rstrip(".,")
    if not mentah:
        return None
    pemisah = [m.start() for m in re.finditer(r"[.,]", mentah)]
    if pemisah:
        ekor = mentah[pemisah[-1] + 1:]
        # Pemisah ribuan: kelompok akhir tepat 3 digit (1.500.000, 1,500). Selain itu desimal (1,5).
        if len(ekor) == 3 or len(pemisah) > 1:
            mentah = re.sub(r"[.,]", "", mentah)
        else:
            mentah = mentah.replace(",", ".")
    try:
        return Decimal(mentah)
    except InvalidOperation:
        return None


def angka_di(teks: str, longgar: bool) -> set[Decimal]:
    """Nilai angka di teks. `longgar=True` (teks layar) juga menyertakan nilai tanpa pengali."""
    hasil: set[Decimal] = set()
    for m in _ANGKA.finditer(teks):
        nilai = _angka_ke_nilai(m.group(1))
        if nilai is None:
            continue
        pengali = _PENGALI.get((m.group(2) or "").lower())
        if pengali:
            hasil.add((nilai * pengali).normalize())
            if longgar:
                hasil.add(nilai.normalize())
        else:
            hasil.add(nilai.normalize())
    return hasil


def _jarak(a: str, b: str) -> int:
    if a == b:
        return 0
    sebelum = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        baris = [i]
        for j, cb in enumerate(b, 1):
            baris.append(min(sebelum[j] + 1, baris[j - 1] + 1, sebelum[j - 1] + (ca != cb)))
        sebelum = baris
    return sebelum[-1]


def kandidat_dasar(kata: str) -> set[str]:
    """Kemungkinan kata dasar (konservatif): kata itu sendiri, tanpa awalan, tanpa akhiran, dan gabungannya.
    Hasil yang kurang dari 4 huruf dibuang."""
    hasil = {kata}
    tanpa_awalan = {kata}
    for a in _AWALAN:
        if kata.startswith(a) and len(kata) - len(a) >= 3:
            sisa = kata[len(a):]
            if len(sisa) >= 4:
                tanpa_awalan.add(sisa)
            if a in _PENGGANTI_HURUF:  # menipu -> tipu (huruf awal luluh)
                tanpa_awalan.add(_PENGGANTI_HURUF[a] + sisa)
    for k in tanpa_awalan:
        hasil.add(k)
        for akhir in _AKHIRAN:
            if k.endswith(akhir) and len(k) - len(akhir) >= 4:
                hasil.add(k[: -len(akhir)])
    return hasil


def _toleransi(panjang: int, cfg: Pengaturan) -> int:
    if panjang <= 4:
        return 0
    return cfg.klaim_setia_edit_pendek if panjang <= 6 else cfg.klaim_setia_edit_panjang


def _kata_teks(teks: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", teks.lower()))


def _nama_ada(token: str, kata_teks: set[str], cfg: Pengaturan) -> bool:
    t = token.lower()
    if t in kata_teks:
        return True
    if len(t) < 4:
        return False
    if len(t) >= 5 and any(len(w) >= 5 and t in w for w in kata_teks):  # menempel akibat OCR
        return True
    toleransi = _toleransi(len(t), cfg)
    for w in kata_teks:
        if abs(len(w) - len(t)) > 2:
            continue
        if _jarak(t, w) <= toleransi or SequenceMatcher(None, t, w).ratio() >= cfg.klaim_setia_rasio_nama:
            return True
    return False


_BULAN = ("januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november",
          "desember")
_BULAN_SINGKAT = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "agu": 8, "ags": 8, "agt": 8, "sep": 9,
                  "okt": 10, "nov": 11, "des": 12, "pebruari": 2, "nopember": 11}


def bulan_di(teks: str) -> set[int]:
    """Nomor bulan (1-12) yang disebut di teks: nama bulan, singkatan setelah tanggal ("1 Nov"), dan tanggal angka
    (26/1/2026, 3-4-2025)."""
    t = teks.lower()
    hasil = {i + 1 for i, b in enumerate(_BULAN) if re.search(rf"\b{b}\b", t)}
    for m in re.finditer(r"\b\d{1,2}\s*([a-z]{3,8})\b", t):
        if m.group(1) in _BULAN_SINGKAT:
            hasil.add(_BULAN_SINGKAT[m.group(1)])
    for m in re.finditer(r"\b\d{1,2}[/.\-](\d{1,2})[/.\-]\d{2,4}\b", t):
        if 1 <= int(m.group(1)) <= 12:
            hasil.add(int(m.group(1)))
    return hasil


def _entitas_ada(n: str, teks: str, kata_teks: set[str], cfg: Pengaturan) -> bool:
    """Token nama ada di teks. Nama bertanda hubung (Wi-Fi, Undang-Undang) diperiksa per bagian karena teks
    dipecah di tanda hubung; nama bulan juga cocok dengan singkatan atau tanggal angka."""
    if _nama_ada(n, kata_teks, cfg):
        return True
    if n.lower() in _BULAN:
        return _BULAN.index(n.lower()) + 1 in bulan_di(teks)
    bagian = [b for b in n.lower().split("-") if b]
    return len(bagian) > 1 and all(b in kata_teks or _nama_ada(b, kata_teks, cfg) for b in bagian)


def entitas_klaim(klaim: str) -> list[str]:
    """Token nama yang harus ada di teks: kapital bukan awal kalimat, singkatan, dan awal kalimat bila token
    berikutnya juga kapital (frasa nama/jabatan seperti "Wakil Menteri")."""
    token = list(re.finditer(r"[A-Za-z][A-Za-z'\-]*", klaim))
    hasil = []
    for i, m in enumerate(token):
        t = m.group().strip("'-")
        if len(t) < 2 or t.lower() in _BUKAN_NAMA:
            continue
        awal_kalimat = i == 0 or re.search(r"[.!?:\n]\s*$", klaim[: m.start()]) is not None
        singkatan = t.isupper() and len(t) >= 2
        kapital = t[0].isupper()
        if singkatan:
            # kalimat berhuruf kapital semua bukan singkatan: tidak diperiksa sebagai nama
            if klaim.isupper():
                continue
            hasil.append(t)
        elif kapital and not awal_kalimat:
            hasil.append(t)
        elif kapital and awal_kalimat and i + 1 < len(token) and token[i + 1].group()[0].isupper():
            hasil.append(t)
    return hasil


def _ada_kata(kata: str, kata_teks: set[str], cfg: Pengaturan, longgar: bool = True) -> bool:
    """Kata klaim ada di teks: sama, sekata dasar, menempel, atau salah eja OCR (hanya bila longgar)."""
    kc = kandidat_dasar(kata)
    if kata in kata_teks:
        return True
    for w in kata_teks:
        wc = kandidat_dasar(w)
        if kc & wc:
            return True
        if any(len(c) >= 5 and len(w) >= 5 and c in w for c in kc):
            return True
    if not longgar:
        return False
    for w in kata_teks:
        for c in kc:
            for d in kandidat_dasar(w):
                if min(len(c), len(d)) >= 5 and abs(len(c) - len(d)) <= 2 and _jarak(c, d) <= _toleransi(max(len(c), len(d)), cfg):
                    return True
    return False


def _berat(kata: str) -> bool:
    return bool(kandidat_dasar(kata) & KATA_BERAT) or kata in KATA_BERAT


def _sekata(a: str, b: str) -> bool:
    return a == b or bool(kandidat_dasar(a) & kandidat_dasar(b))


def _token_negasi(teks: str) -> list[str]:
    """Token huruf-angka huruf kecil; tanda baca akhir klausa (titik, koma, dst. yang diikuti spasi atau akhir teks)
    dipertahankan sebagai penanda batas "|". Titik di dalam angka (8.000.000) bukan batas; ganti baris bukan batas
    karena teks OCR sering terpotong di tengah kalimat."""
    return [t if t[0].isalnum() else "|" for t in re.findall(r"[a-z0-9]+|[.,;:!?](?=\s|$)", teks.lower())]


def _kena_negasi(token: list[str], j: int) -> bool:
    """Token ke-j berada dalam jangkauan negasi: penanda negasi dalam JANGKAUAN_NEGASI token sebelumnya tanpa
    melewati batas klausa atau kata sambung."""
    for t in reversed(token[max(0, j - JANGKAUAN_NEGASI):j]):
        if t in NEGASI:
            return True
        if t == "|" or t in PEMUTUS_NEGASI:
            return False
    return False


def periksa_negasi(klaim: str, teks: str) -> int:
    """Jumlah ketidakcocokan negasi antara klaim dan teks (0 = cocok). Konservatif: kata isi klaim yang ada di teks
    dianggap cocok bila SEDIKITNYA SATU kemunculannya di teks berpolaritas sama (bernegasi atau tidak) dengan kata itu
    di klaim; bagian teks lain yang bernegasi atau kata turunan berbeda arti tidak membuat klaim gagal."""
    tk, tt = _token_negasi(klaim), _token_negasi(teks)
    neg_klaim = [i for i, t in enumerate(tk) if t in NEGASI]
    if neg_klaim and not any(t in NEGASI for t in tt):
        return len(neg_klaim)
    salah = 0
    dicek: set[str] = set()
    for j, kata in enumerate(tk):
        if kata in dicek or not cocok.kata_isi(kata):
            continue
        dicek.add(kata)
        ada = [m for m, w in enumerate(tt) if _sekata(kata, w)]
        if not ada:
            continue
        kutub = [_kena_negasi(tt, m) for m in ada]
        kutub_klaim = {_kena_negasi(tk, i) for i, w in enumerate(tk) if w == kata}
        # tiap kemunculan di klaim harus punya padanan berpolaritas sama di teks
        if any(k not in kutub for k in kutub_klaim):
            salah += 1
    return salah


def periksa_kesetiaan(klaim: str, teks: str, cfg: Pengaturan) -> tuple[str, int] | None:
    """None bila klaim setia pada teks; selain itu (kode alasan, jumlah token bermasalah)."""
    # 1. angka
    angka_teks = angka_di(teks, longgar=True)
    baru = [n for n in angka_di(klaim, longgar=False) if n not in angka_teks]
    if baru:
        return KODE_ANGKA, len(baru)

    kata_teks = _kata_teks(teks)

    # 2. nama dan singkatan
    nama = entitas_klaim(klaim)
    hilang = [n for n in nama if not _entitas_ada(n, teks, kata_teks, cfg)]
    if hilang:
        return KODE_ENTITAS, len(hilang)

    # 3-4. kata isi
    dilewati = {n.lower() for n in nama}
    kata = [k for k in cocok.kata_isi(klaim) if not any(c.isdigit() for c in k) and k not in dilewati]
    if not kata:
        return _hasil_negasi(klaim, teks)
    baru_berat, pengganti, baru_biasa = 0, 0, 0
    for k in kata:
        if _ada_kata(k, kata_teks, cfg, longgar=not _berat(k)):
            continue
        if _berat(k):
            baru_berat += 1
            continue
        terdekat = max((SequenceMatcher(None, k, w).ratio() for w in kata_teks if len(w) >= 4), default=0.0)
        if terdekat >= cfg.klaim_setia_kemiripan_pengganti:
            pengganti += 1
        else:
            baru_biasa += 1
    if baru_berat:
        return KODE_BERAT, baru_berat
    if pengganti:
        return KODE_PENGGANTI, pengganti
    if baru_biasa / len(kata) > cfg.klaim_setia_kata_baru_maks:
        return KODE_BANYAK, baru_biasa
    return _hasil_negasi(klaim, teks)


def _hasil_negasi(klaim: str, teks: str) -> tuple[str, int] | None:
    n = periksa_negasi(klaim, teks)
    return (KODE_NEGASI, n) if n else None
