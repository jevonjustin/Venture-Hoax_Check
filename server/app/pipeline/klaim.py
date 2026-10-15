"""Tahap 3: mengambil klaim utama dari teks.

`klaim_heuristik` adalah cadangan heuristik yang ekstraktif: kalimat diambil apa adanya dari teks (boleh dipotong
di batas kata dengan elipsis), tidak pernah dirangkai ulang, sehingga selalu setia pada teks. Dipakai sebagai
cadangan kalau LLM gagal atau mengosongkan klaim.
"""

import re

from ..konfigurasi import Pengaturan, pengaturan as pengaturan_global
from . import bersih, samarkan
from .tipe import CiriTerdeteksi

SINGKATAN = frozenset({
    "dr", "drs", "prof", "no", "hlm", "dll", "dsb", "dst", "tsb", "yth", "bpk", "sdr", "jl", "pt", "cv", "rp", "ir",
    "hj", "mr", "mrs", "vs", "st", "kec", "kab", "kel", "ka", "tgl", "tlp", "al", "sd", "an", "dkk", "dsj", "mis",
})
KATA_SAMBUNG = frozenset({
    "agar", "yang", "dan", "atau", "di", "ke", "untuk", "dengan", "karena", "bahwa", "dari", "pada", "serta",
    "sebagai", "dalam", "oleh", "akan", "jika", "kalau", "tetapi", "namun", "sehingga",
})
# Baris yang menjadi batas paragraf (tanggal, hari, sumber), bukan sambungan kalimat sebelumnya.
_BARIS_METADATA = re.compile(
    r"^(?:(?:senin|selasa|rabu|kamis|jumat|jum'at|sabtu|minggu)\b.*\d{4}|sumber\s*:|\d{1,2}\s+\w+\s+\d{4}\b.*(?:wib|wita|wit)?$)",
    re.IGNORECASE,
)
_AKHIR_KALIMAT = re.compile(r"[.!?]+[\"”’')\]]*$")
_KATA_KERJA = re.compile(
    r"\b(?:mengumumkan|menyatakan|mengatakan|menyebut|mengaku|akan|wajib|dilarang|diwajibkan|ditutup|dibuka|"
    r"mengandung|menyebabkan|dinyatakan|terbukti|resmi|berubah|disita|didenda|dikenakan|dirawat|ditangkap|diberlakukan|"
    r"usul|mengusulkan|tutup|menutup|melarang|mewajibkan|membatalkan|menghapus|menaikkan|menurunkan|gratis|terlibat|terungkap|ditemukan|meninggal|menewaskan|dikabarkan|beredar|mengajak|meminta|harus|dapat|bisa|"
    r"mendapat|menerima|memberikan|menghubungi|melanggar|dinonaktifkan|diblokir|dihapus|"
    r"masuk|mulai|bakar|membakar|terbakar|tertangkap|ketangkap|ditangkap|digelandang|gelandang|diduga|dituduh|diumumkan)\b",
    re.IGNORECASE,
)
_ANGKA = re.compile(r"\d")
# Ciri yang buktinya boleh menaikkan skor sebuah kalimat klaim. Ajakan menyebarkan, huruf kapital, sumber tidak
# jelas, dan judul clickbait sengaja tidak termasuk: kalimat bukti ciri itu biasanya ajakan atau komentar, bukan
# klaim (gambar 16: kalimat "VIRALKAN INI" mengalahkan klaim yang diviralkan).
CIRI_BONUS_KLAIM = frozenset({"desakan_waktu", "permintaan_data_rahasia", "bahasa_provokatif"})
MIN_KATA_BARIS_JUDUL = 2  # satu kata saja (nama akun, nama media) bukan potongan judul
MAKS_KATA_BARIS_JUDUL = 5  # baris judul terpecah tidak lebih dari ini kata
MIN_KATA_DAFTAR_NAMA = 7  # kalimat bertitle case sependek ini tidak dihukum sebagai daftar nama
MAKS_KATA_JUDUL_GABUNGAN = 10
RASIO_HURUF_JUDUL = 0.6  # bagian kata yang diawali huruf kapital atau angka pada baris judul
# Kata ganti orang kedua: kalimat yang memuatnya tidak dipakai sebagai klaim (teks UI tidak boleh memakainya).
KATA_GANTI_KEDUA = frozenset({"kamu", "anda", "engkau", "kau", "kalian", "dirimu"})
_PENGECUALIAN_MU = frozenset({"ilmu", "temu", "bertemu", "ketemu", "menemu", "jamu", "tamu", "bertamu", "semu", "ramu"})
# Orang pertama dan sapaan: kalimat obrolan, bukan pernyataan. "mas", "mbak", "pak", dan "bu" sengaja tidak
# termasuk karena juga muncul sebagai gelar di berita.
_PERCAKAPAN = re.compile(r"\b(?:saya|aku|gue|gw|gua|kak|kakak|bro|sis|gan|min)\b", re.IGNORECASE)
_URL =re.compile(r"https?://|www\.|\b\w+\.(?:com|id|net|org|co|xyz|top)\b", re.IGNORECASE)


def _paragraf(teks: str, cfg: Pengaturan) -> list[str]:
    """Menggabungkan baris OCR berurutan, karena kalimat sering terbelah lintas baris.

    Baris tidak disambung bila sudah berakhir tanda akhir kalimat atau berupa metadata (tanggal, "Sumber:").
    Selain itu baris disambung ke baris berikutnya bila: berakhir kata sambung (agar, yang, dan, ...), baris
    berikutnya diawali huruf kecil, atau baris itu hampir sepanjang baris terpanjang (tanda terbelah oleh lebar
    layar). Judul pendek dan nama akun dengan begitu tetap berdiri sendiri."""
    # Baris UI dan baris nama akun yang lolos ke sini dianggap pemisah, bukan bagian kalimat.
    mentah = teks.splitlines()
    baris_akun = samarkan.tandai_baris_akun(mentah)
    baris_semua = ["" if bersih.apakah_ui(b, cfg) or akun else b.strip() for b, akun in zip(mentah, baris_akun)]
    terpanjang = max((len(b) for b in baris_semua), default=0)
    hasil: list[str] = []
    sambung = False
    for i, baris in enumerate(baris_semua):
        if not baris:
            sambung = False
            continue
        if sambung and not _BARIS_METADATA.match(baris):
            hasil[-1] += " " + baris
        else:
            hasil.append(baris)
        berakhir = _AKHIR_KALIMAT.search(baris) or _BARIS_METADATA.match(baris)
        kata_terakhir = re.sub(r"\W+$", "", baris.split()[-1]).lower() if baris.split() else ""
        sambung = not berakhir and (
            kata_terakhir in KATA_SAMBUNG
            or (
                len(baris) >= cfg.klaim_rasio_baris_panjang * terpanjang
                and _baris_berikutnya_lebih_dari_satu_kata(baris_semua, i)
            )
            or _berikutnya_huruf_kecil(baris_semua, i)
            or _judul_terpecah(baris_semua, i, hasil[-1])
        )
    return hasil


def _huruf_judul(kata: list[str]) -> bool:
    return bool(kata) and sum(1 for k in kata if k[:1].isupper() or k[:1].isdigit()) / len(kata) >= RASIO_HURUF_JUDUL


def _judul_terpecah(baris_semua: list[str], i: int, gabungan: str) -> bool:
    """Apakah baris ke-i dan berikutnya adalah dua bagian sebuah judul yang terpecah oleh lebar layar: keduanya
    pendek, baris pertama tanpa tanda akhir kalimat, dan keduanya berhuruf awal kapital (Title Case atau kapital
    semua), misalnya "MenKeu Suhasasil Terlibat" + "Korupsi 500 Triliun". Baris metadata menghentikan."""
    if i + 1 >= len(baris_semua):
        return False
    sekarang, berikut = baris_semua[i], baris_semua[i + 1]
    if not berikut or _BARIS_METADATA.match(berikut) or _AKHIR_KALIMAT.search(sekarang):
        return False
    kata_s, kata_b = sekarang.split(), berikut.split()
    if not (MIN_KATA_BARIS_JUDUL <= len(kata_s) <= MAKS_KATA_BARIS_JUDUL):
        return False
    if not (MIN_KATA_BARIS_JUDUL <= len(kata_b) <= MAKS_KATA_BARIS_JUDUL):
        return False
    if len(gabungan.split()) + len(kata_b) > MAKS_KATA_JUDUL_GABUNGAN:
        return False
    return _huruf_judul(kata_s) and _huruf_judul(kata_b)


def _baris_berikutnya_lebih_dari_satu_kata(baris_semua: list[str], i: int) -> bool:
    """Satu kata sendirian di bawah baris panjang (nama media, nama akun) bukan lanjutan kalimat."""
    return i + 1 < len(baris_semua) and len(baris_semua[i + 1].split()) >= 2


def _berikutnya_huruf_kecil(baris_semua: list[str], i: int) -> bool:
    """Apakah baris tepat sesudah baris ke-i diawali huruf kecil (sambungan kalimat). Baris kosong adalah pemisah."""
    return i + 1 < len(baris_semua) and bool(baris_semua[i + 1]) and baris_semua[i + 1][0].islower()


def _batas_kalimat(paragraf: str, posisi: int) -> bool:
    """Apakah tanda baca pada `paragraf[posisi]` (sudah diikuti spasi) benar-benar akhir kalimat."""
    tanda = paragraf[posisi]
    sebelum = paragraf[:posisi]
    kata = re.search(r"(\S+)$", sebelum)
    kata = kata.group(1) if kata else ""
    if tanda == ".":
        if re.search(r"\d$", sebelum) and re.match(r"\s*\d", paragraf[posisi + 1:]):
            return False  # angka diapit titik: 12. 16 atau 1.000. 000
        if "/" in kata or "www" in kata.lower() or _URL.search(kata):
            return False  # titik di dalam tautan
        bersih_kata = kata.strip("([\"'").rstrip(".").lower()
        if bersih_kata in SINGKATAN or re.fullmatch(r"(?:[a-z]\.)+[a-z]", kata.strip("([\"'").lower()):
            return False  # singkatan umum, termasuk a.n dan s.d
        if len(bersih_kata) == 1 and bersih_kata.isalpha():
            return False  # inisial
    lanjut = paragraf[posisi + 1:].lstrip(" \"“‘'([")
    return not lanjut or not lanjut[0].islower()


def pisah_kalimat(teks: str, cfg: Pengaturan | None = None) -> list[str]:
    """Memecah teks menjadi kalimat. Titik tidak dianggap batas bila diapit angka, ada di dalam tautan, atau
    mengikuti singkatan umum; tanda baca yang diikuti huruf kecil juga bukan batas."""
    cfg = cfg or pengaturan_global
    kalimat: list[str] = []
    for p in _paragraf(teks, cfg):
        awal = 0
        for m in re.finditer(r"[.!?]+(?=\s|$)", p):
            akhir = m.end()
            if _batas_kalimat(p, akhir - 1):
                potongan = p[awal:akhir].strip()
                if potongan:
                    kalimat.append(potongan)
                awal = akhir
        sisa = p[awal:].strip()
        if sisa:
            kalimat.append(sisa)
    return kalimat


def _kata(kalimat: str) -> list[str]:
    return kalimat.split()


def _rasio_huruf(kalimat: str) -> float:
    tanpa_spasi = re.sub(r"\s", "", kalimat)
    return sum(c.isalpha() for c in tanpa_spasi) / len(tanpa_spasi) if tanpa_spasi else 0.0


def memuat_kata_ganti_kedua(teks: str) -> bool:
    """Apakah teks memuat kamu, Anda, engkau, kalian, atau akhiran -mu (kecuali kata seperti "ilmu", "tamu")."""
    for t in re.findall(r"[a-z]+(?:-[a-z]+)*", teks.lower()):
        if t in KATA_GANTI_KEDUA:
            return True
        if len(t) > 3 and t.endswith("mu") and t not in _PENGECUALIAN_MU:
            return True
    return False


def skor_kalimat(
    kalimat: str, bukti_norm: list[str], cfg: Pengaturan, saring_percakapan: bool = True
) -> float | None:
    """Skor pemilihan kalimat, atau None bila kalimat tidak layak jadi klaim (pertanyaan, UI, terlalu pendek,
    terlalu banyak non-huruf, tautan, atau, bila `saring_percakapan`, memuat kata ganti kedua, orang pertama,
    atau sapaan)."""
    kata = _kata(kalimat)
    if len(kata) < cfg.klaim_min_kata or kalimat.rstrip("\"”’') ").endswith("?"):
        return None
    if bersih.apakah_ui(kalimat, cfg) or _rasio_huruf(kalimat) < 0.6 or _URL.search(kalimat):
        return None
    if saring_percakapan and (memuat_kata_ganti_kedua(kalimat) or _PERCAKAPAN.search(kalimat)):
        return None
    skor = 0.0
    n = len(kata)
    skor += 2 if 8 <= n <= 35 else (1 if n <= 60 else 0)
    if kalimat.rstrip("\"”’') ").endswith("."):
        skor += 1
    if re.search(r"!\s*$", kalimat):
        skor -= 1
    if _KATA_KERJA.search(kalimat):
        skor += 1
    nama = [k for k in kata[1:] if k[:1].isupper() and not k.isupper()]
    if _ANGKA.search(kalimat) or len(nama) >= 2:
        skor += 1
    kapital = sum(1 for k in kata if k[:1].isupper())
    if n >= MIN_KATA_DAFTAR_NAMA and kapital / n >= 0.7 and not _KATA_KERJA.search(kalimat) and not _ANGKA.search(kalimat):
        skor -= 2  # deretan nama lembaga atau judul tanpa pernyataan, bukan klaim
    norm = kalimat.lower()
    if any(b and (b in norm or norm in b) for b in bukti_norm):
        skor += 1
    return skor


def _potong(kalimat: str, maks: int) -> str:
    if len(kalimat) <= maks:
        return kalimat
    potong = kalimat[:maks]
    if kalimat[maks] != " " and " " in potong:
        potong = potong.rsplit(" ", 1)[0]
    return potong.rstrip(" ,;:-") + "…"


def klaim_heuristik(
    teks_bersih: str, bukti: list[str] | None = None, cfg: Pengaturan | None = None,
    skor_minimum: float | None = None, catatan: dict | None = None,
) -> str:
    """Masukan: teks bersih dan (opsional) bukti ciri regex. Keluaran: satu kalimat klaim yang diambil apa adanya
    dari teks, atau string kosong bila tidak ada pernyataan yang layak.

    Skor: panjang wajar (+2 untuk 8-35 kata, +1 sampai 60), berakhir titik (+1), kata kerja pernyataan (+1),
    angka atau dua nama berhuruf kapital (+1), tumpang tindih dengan bukti ciri (+1), seruan murni (-1). Kalimat
    pertanyaan, baris UI, tautan, dan kalimat yang kebanyakan non-huruf tidak dipertimbangkan. Skor terbaik harus
    mencapai `klaim_skor_minimum` (atau `skor_minimum`); kalau seri, kalimat yang lebih awal menang. Kalimat yang
    memuat kata ganti kedua, orang pertama, atau sapaan tidak dipertimbangkan.

    `catatan` (dict, opsional) diisi "gugur_percakapan": jumlah kalimat yang akan lolos skor minimum seandainya
    tidak disaring karena kata ganti kedua, orang pertama, atau sapaan.
    """
    cfg = cfg or pengaturan_global
    minimum = cfg.klaim_skor_minimum if skor_minimum is None else skor_minimum
    bukti_norm = [re.sub(r"\s+", " ", b).strip().lower().rstrip("…") for b in (bukti or []) if b]
    terbaik, skor_terbaik, gugur = "", None, 0
    for kalimat in pisah_kalimat(teks_bersih, cfg):
        skor = skor_kalimat(kalimat, bukti_norm, cfg)
        if skor is None:
            tanpa_saring = skor_kalimat(kalimat, bukti_norm, cfg, saring_percakapan=False)
            if tanpa_saring is not None and tanpa_saring >= minimum:
                gugur += 1
            continue
        if skor_terbaik is None or skor > skor_terbaik:
            terbaik, skor_terbaik = kalimat, skor
    if catatan is not None:
        catatan["gugur_percakapan"] = gugur
    if skor_terbaik is None or skor_terbaik < minimum:
        return ""
    return _potong(terbaik, cfg.klaim_maks_karakter)


def klaim_dari_bukti(bukti: str, cfg: Pengaturan | None = None) -> str:
    """Klaim dari bukti pernah_dibantah (potongan teks layar yang terbukti mirip artikel cek fakta). Kata sambung di
    ujung potongan dibuang. Kosong bila terlalu pendek, memuat kata ganti kedua, orang pertama atau sapaan, tautan,
    atau tampak sebagai teks UI."""
    cfg = cfg or pengaturan_global
    kata = re.sub(r"\s+", " ", bukti or "").strip().rstrip(" :;,-").split()
    while kata and kata[-1].lower().strip(",.;:") in KATA_SAMBUNG:  # potongan yang berakhir "... dan" / "... di"
        kata.pop()
    teks = " ".join(kata).rstrip(" :;,-")
    if len(kata) < cfg.klaim_bukti_min_kata or memuat_kata_ganti_kedua(teks) or _PERCAKAPAN.search(teks):
        return ""
    if _URL.search(teks) or bersih.apakah_ui(teks, cfg):
        return ""
    return _potong(teks, cfg.klaim_maks_karakter)



def bukti_untuk_klaim(ciri: list[CiriTerdeteksi]) -> list[str]:
    """Bukti dari ciri hasil penggabungan yang boleh menaikkan skor kalimat klaim (`CIRI_BONUS_KLAIM`). Hanya ciri
    berkeyakinan tinggi: bukti ciri sedang (satu sumber) pernah menaikkan kalimat obrolan yang keliru."""
    return [b for c in ciri if c.id in CIRI_BONUS_KLAIM and c.keyakinan == "tinggi" for b in c.bukti]
