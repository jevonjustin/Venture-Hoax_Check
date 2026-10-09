"""Tahap 2: membuang teks antarmuka (UI) media sosial dari hasil baca.

Prinsip utama: konservatif. Sebuah baris dibuang hanya kalau SELURUH isinya cocok pola UI (bukan
sekadar memuat satu kata tombol), dan baris yang panjang tidak pernah dibuang oleh aturan UI. Lebih baik
ada sisa teks UI daripada kalimat isi yang hilang. Aturan posisi (pita atas) tidak mengandalkan bilah status
selalu ada, karena pengguna bisa memilih potongan layar mana pun.

Fungsi di sini murni: tanpa jaringan, tanpa log. Nama akun dan @akun sengaja tidak disentuh
(penyamaran dikerjakan Sesi 5.5). Ambang ada di konfigurasi.py.
"""

import re
import unicodedata

from ..konfigurasi import Pengaturan, pengaturan as pengaturan_global
from .tipe import BarisDibuang, BarisTeks, HasilBersih

# Aturan tambahan yang belum menjadi bawaan; diukur terpisah dari aturan utama (Sesi 5.4).
# "Baca juga" belum pernah muncul di data nyata, jadi baru diukur dan belum dipakai.
VARIAN_BACA_JUGA = "baca_juga"
VARIAN_DIKENAL = frozenset({VARIAN_BACA_JUGA})

ALASAN_TANPA_HURUF = "tanpa huruf atau angka"
ALASAN_BILAH_STATUS = "bilah status (pita atas)"
ALASAN_INTERAKSI = "angka interaksi"
ALASAN_TOMBOL = "tombol atau aksi"
ALASAN_MENU = "menu situs"
ALASAN_DERET_MENU = "deret menu"
ALASAN_WAKTU = "penanda waktu"
ALASAN_JAM_OBROLAN = "jam obrolan"
ALASAN_TERJEMAHAN = "terjemahan atau sponsor"
ALASAN_BANNER = "banner sistem"
ALASAN_BACA_JUGA = "baca juga"
ALASAN_UI_PESAN = "UI aplikasi pesan"

_TOKEN_WAKTU = re.compile(r"^\d{1,2}[.:]\d{2}$")
_TOKEN_JARINGAN = re.compile(r"^(?:[345]g\+?|lte|volte|vowifi|wi-?fi|h\+?|e)$")
_TOKEN_KECEPATAN = re.compile(r"^[\d.,]+(?:kb|mb)/[ds]$")
# Angka polos 1-3 digit (tanpa %) ikut dianggap token status karena sinyal dan baterai sering terbaca "4" atau "97".
# Itu aman hanya karena aturan ini berlaku di pita atas dan hanya untuk baris yang SELURUH tokennya token status.
# Akibat yang diketahui: "3" dan "13" di gambar 08 (potongan nomor telepon di header) ikut terbuang.
_TOKEN_ANGKA = re.compile(r"^\d{1,3}%?$")
_TOKEN_SINYAL = re.compile(r"^[li|]{1,3}$")  # ikon sinyal sering terbaca "ll" atau "il"

_SATUAN_INTERAKSI = r"(?:suka|likes?|komentar|comments?|tayangan|views?|dilihat|kali dilihat|bagikan|shares?|retweets?|reposts?|pengikut|followers?|mengikuti|following)"
_INTERAKSI = re.compile(
    rf"^\d+(?:[.,]\d+)?\s*(?:rb|ribu|k|jt|juta)(?:\s*{_SATUAN_INTERAKSI})?$"
    rf"|^\d+(?:[.,]\d+)?\s*{_SATUAN_INTERAKSI}$"
)

_KATA_TOMBOL = frozenset({
    "suka", "balas", "bagikan", "like", "reply", "share", "ikuti", "follow", "kirim", "komentar",
    "comment", "comments", "send", "repost", "retweet", "simpan", "save",
})
_KATA_MENU = frozenset({
    "beranda", "home", "masuk", "login", "cari", "menu", "berlangganan", "daftar", "search", "subscribe",
})

# Angka waktu dimulai dari 1 (bukan 0), supaya ikon yang terbaca "0J" tidak dianggap "0 jam".
_WAKTU_RELATIF = re.compile(
    r"^(?:[1-9]\d*\s*(?:d|det|detik|mnt|menit|m|j|jam|h|hari|mgg|minggu|bln|bulan|thn|tahun|w|s|sec|min|hr|hrs)\.?"
    r"(?:\s+(?:yang\s+)?lalu)?"
    r"|[1-9]\d*\s*(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+ago"
    r"|kemarin|baru saja|just now|yesterday)$"
)

# Jam di gelembung obrolan: SELURUH baris hanya jam, boleh dengan penanda baca/dibaca/diedit (tanda centang
# di ujung baris sudah dibuang oleh _inti). Baris yang masih punya kata isi lain tidak cocok.
_PENANDA_JAM = r"(?:diedit|edited|dibaca|terbaca|read|terkirim|sent|delivered)"
_JAM = re.compile(
    rf"^(?:{_PENANDA_JAM}\s+)?(?:[01]?\d|2[0-3])[.:][0-5]\d\s?(?:am|pm|wib|wita|wit)?(?:\s+{_PENANDA_JAM})?$"
)

# Baris tunggal tombol terjemahan dan label iklan (bawaan).
_TERJEMAHAN_SPONSOR = re.compile(
    r"^(?:lihat terjemahan|tampilkan terjemahan|show translation|see translation|bersponsor|sponsored|iklan)$"
)
# Varian ukur: "Baca juga" biasanya baris panjang, jadi dicocokkan dari awal baris.
_AWALAN_BACA_JUGA = re.compile(r"^baca juga\b")
_BACA_JUGA_PENDEK = re.compile(r"^(?:lihat selengkapnya|see more)$")

# Banner sistem WhatsApp: teks tetap yang sering terpecah beberapa baris, jadi dicocokkan pada gabungan baris.
_BANNER = re.compile(
    r"pesan dan panggilan (?:terenkripsi|dienkripsi).{0,200}?ketuk untuk info selengkapnya\.?"
    r"|messages and calls are end-to-end encrypted.{0,200}?tap to learn more\.?"
    r"|chat ini dengan akun bisnis\.? ketuk untuk info selengkapnya\.?"
    r"|this chat is with a business account\.? tap to learn more\.?"
)

# UI aplikasi pesan: teks tetap pada banner kontak tak dikenal dan placeholder kolom ketik. Hanya cocok kalau
# SELURUH baris adalah teks itu (tanda baca di ujung sudah dibuang oleh _inti, termasuk "..." pada placeholder).
_UI_APLIKASI_PESAN = re.compile(
    r"^(?:bukan kontak(?:\s*[·•|.\-]?\s*tidak ada grup yang sama)?|tidak ada grup yang sama|fitur keamanan"
    r"|ketik (?:sebuah )?pesan|tulis (?:pesan|komentar|balasan)|tambahkan komentar|kirim pesan"
    r"|type a message|write a (?:message|comment)|add a comment|message)$"
)
_MAKS_KARAKTER_BARIS_MENU = 25


def _norm(teks: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", teks)).strip().lower()


def _inti(teks: str) -> str:
    """Huruf kecil, spasi dirapikan, dan tanda non-huruf/angka di ujung baris (·, •, ✓, titik) dibuang."""
    return re.sub(r"^[^\w]+|[^\w%+]+$", "", _norm(teks))


def _tengah_y(baris: BarisTeks) -> float:
    ys = [y for _, y in baris.kotak]
    return sum(ys) / len(ys) if ys else 0.0


def _token_kata(inti: str) -> list[str]:
    return [t for t in (re.sub(r"^[^\w+]+|[^\w+]+$", "", k) for k in inti.split()) if t]


def _bilah_status(norm: str) -> bool:
    tokens = [t for t in re.split(r"[\s|]+", norm) if t]
    if not tokens:
        return False
    for t in tokens:
        if not re.search(r"\w", t):
            continue  # simbol saja (©, ·, ikon)
        if not (_TOKEN_WAKTU.match(t) or _TOKEN_JARINGAN.match(t) or _TOKEN_KECEPATAN.match(t)
                or _TOKEN_ANGKA.match(t) or _TOKEN_SINYAL.match(t)):
            return False
    return True


def _hanya_dari(inti: str, kata_sah: frozenset[str], maks_kata: int) -> bool:
    tokens = _token_kata(inti.replace("log in", "login"))
    return 1 <= len(tokens) <= maks_kata and all(t in kata_sah for t in tokens)


def _alasan_baris(baris: BarisTeks, tinggi: int, varian: frozenset[str], cfg: Pengaturan) -> str | None:
    norm = _norm(baris.teks)
    if not re.search(r"\w", norm):
        return ALASAN_TANPA_HURUF
    inti = _inti(baris.teks)
    if tinggi > 0 and _tengah_y(baris) < cfg.bersih_pita_atas * tinggi and _bilah_status(norm):
        return ALASAN_BILAH_STATUS
    if _INTERAKSI.match(inti):
        return ALASAN_INTERAKSI
    if _hanya_dari(inti, _KATA_TOMBOL, cfg.bersih_maks_kata_ui):
        return ALASAN_TOMBOL
    if _UI_APLIKASI_PESAN.match(inti):
        return ALASAN_UI_PESAN
    if _hanya_dari(inti, _KATA_MENU, cfg.bersih_maks_kata_ui):
        return ALASAN_MENU
    if _WAKTU_RELATIF.match(inti):
        return ALASAN_WAKTU
    if _JAM.match(inti):
        return ALASAN_JAM_OBROLAN
    if _TERJEMAHAN_SPONSOR.match(inti):
        return ALASAN_TERJEMAHAN
    if VARIAN_BACA_JUGA in varian and (_AWALAN_BACA_JUGA.match(inti) or _BACA_JUGA_PENDEK.match(inti)):
        return ALASAN_BACA_JUGA
    return None


def _calon_menu(baris: BarisTeks, cfg: Pengaturan) -> bool:
    teks = baris.teks.strip()
    return (
        len(teks) <= _MAKS_KARAKTER_BARIS_MENU
        and len(teks.split()) <= cfg.bersih_menu_maks_kata
        and not re.search(r"[.!?]$", teks)
    )


def _tandai_deret_menu(baris: list[BarisTeks], alasan: list[str | None], tinggi: int, cfg: Pengaturan) -> None:
    """Baris menu situs ("Home") biasanya satu deret sejajar dengan kategori ("Ekonomi", "Finansial").
    Kategori itu dibuang hanya kalau sejajar dengan kata menu yang terbukti dan deretnya cukup banyak."""
    if tinggi <= 0:
        return
    toleransi = cfg.bersih_toleransi_sejajar * tinggi
    for i, a in enumerate(alasan):
        if a != ALASAN_MENU:
            continue
        y = _tengah_y(baris[i])
        deret = [j for j, b in enumerate(baris) if abs(_tengah_y(b) - y) <= toleransi
                 and (alasan[j] == ALASAN_MENU or (alasan[j] is None and _calon_menu(b, cfg)))]
        if len(deret) >= cfg.bersih_menu_min_baris:
            for j in deret:
                if alasan[j] is None:
                    alasan[j] = ALASAN_DERET_MENU


def _tandai_banner(baris: list[BarisTeks], alasan: list[str | None]) -> None:
    """Membuang banner sistem yang terpecah beberapa baris. Hanya baris yang SELURUHNYA berada di dalam
    kecocokan yang dibuang; baris yang menggabungkan banner dengan teks lain dipertahankan."""
    gabungan, rentang = "", []
    for i, b in enumerate(baris):
        if alasan[i] is not None:
            continue
        teks = _norm(b.teks)
        gabungan += (" " if gabungan else "") + teks
        rentang.append((i, len(gabungan) - len(teks), len(gabungan)))
    for m in _BANNER.finditer(gabungan):
        for i, awal, akhir in rentang:
            if awal >= m.start() and akhir <= m.end():
                alasan[i] = ALASAN_BANNER


def bersihkan(
    baris: list[BarisTeks],
    lebar: int,
    tinggi: int,
    varian: frozenset[str] = frozenset(),
    cfg: Pengaturan | None = None,
) -> HasilBersih:
    """Masukan: baris hasil baca (teks, kotak, skor) dan ukuran gambar. Keluaran: teks bersih dan baris yang dibuang.

    `lebar` belum dipakai aturan mana pun tetapi disediakan agar aturan posisi berikutnya tidak mengubah
    tanda tangan. `varian` memilih aturan tambahan (VARIAN_DIKENAL); kosong berarti aturan bawaan saja.
    """
    cfg = cfg or pengaturan_global
    tidak_dikenal = set(varian) - VARIAN_DIKENAL
    if tidak_dikenal:
        raise ValueError(f"Varian pembersihan tidak dikenal: {sorted(tidak_dikenal)}")
    alasan = [_alasan_baris(b, tinggi, frozenset(varian), cfg) for b in baris]
    _tandai_deret_menu(baris, alasan, tinggi, cfg)
    _tandai_banner(baris, alasan)
    dipertahankan = [b.teks for b, a in zip(baris, alasan) if a is None]
    dibuang = [BarisDibuang(b.teks, a) for b, a in zip(baris, alasan) if a is not None]
    return HasilBersih("\n".join(dipertahankan), dibuang)


def apakah_ui(teks: str, cfg: Pengaturan | None = None) -> bool:
    """Apakah satu baris teks, tanpa informasi posisi, cocok pola UI. Dipakai klaim heuristik."""
    return _alasan_baris(BarisTeks(teks, (), 0.0), 0, frozenset(), cfg or pengaturan_global) is not None
