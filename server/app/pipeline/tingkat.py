"""Tahap 6: menentukan tingkat indikasi dengan logika sendiri (tanpa LLM; RANCANGAN §9).

Aturan:
- kuat: ada artikel berlabel salah atau penipuan dengan skor >= ambang_cocok, dan artikel itu unggul lebih dari
  `selisih_konflik` dari SEMUA artikel berlabel benar, klarifikasi, atau satir di antara kandidat.
- hati_hati, varian "konflik": kecocokan salah/penipuan ada, tetapi ada artikel benar/klarifikasi/satir yang
  lebih tinggi atau selisihnya tidak lebih dari `selisih_konflik`.
- hati_hati, varian "satir": ada artikel satir dengan skor >= ambang_cocok (kalau `satir_hati_hati` aktif).
- hati_hati, varian "mirip": artikel salah/penipuan hanya di rentang mirip (ambang_mirip sampai ambang_cocok).
- hati_hati, varian "ciri_saja": tidak ada kecocokan, tetapi sedikitnya satu ciri hasil penggabungan.
- tidak_ditemukan: selain itu. Varian "rujukan" bila ada artikel (label lain) yang tetap ditampilkan.

Artikel yang tidak berkaitan disaring lebih dulu: artikel hanya dihitung dan ditampilkan bila relevansinya
(bobot kata isi judul yang ada di teks) mencapai `relevansi_minimum`, kecuali artikel peringkat 1 dengan skor
>= ambang_cocok (atau `relevansi_lolos_skor` bila diisi) yang selalu lolos. Artikel yang tersaring dikembalikan
di `Putusan.tersaring` hanya untuk debug.

Kombinasi skor dan relevansi (Sesi 5.6, `kuat_kombinasi_aktif`, bawaan mati): artikel salah/penipuan yang relevan
dengan skor sedikitnya `kuat_kombinasi_skor` (di bawah ambang_cocok), relevansi sedikitnya `kuat_kombinasi_relevansi`,
dan sedikitnya `kuat_kombinasi_min_kata` kata isi judul yang ada di teks diperlakukan sama dengan skor >= ambang_cocok
(kuat bila tanpa konflik). Syarat jumlah kata mencegah judul pendek (relevansi tinggi dari satu-dua kata) menjadi kuat.

Ciri tanpa kecocokan database tidak pernah menaikkan tingkat ke kuat. Label klarifikasi, benar, satir, lainnya,
dan belum_terbukti tidak pernah menaikkan tingkat ke kuat; artikelnya tetap ditampilkan sebagai rujukan.
"""

from dataclasses import dataclass, field

from ..konfigurasi import Pengaturan, pengaturan as pengaturan_global
from ..skema import Tingkat
from . import cocok
from .tipe import CiriTerdeteksi, Kandidat

ID_PERNAH_DIBANTAH = "pernah_dibantah"
LABEL_DIBANTAH = frozenset({"salah", "penipuan"})
LABEL_KONFLIK = frozenset({"benar", "klarifikasi", "satir"})
LABEL_SATIR = "satir"

VARIAN_MIRIP = "mirip"
VARIAN_SATIR = "satir"
VARIAN_KONFLIK = "konflik"
VARIAN_CIRI_SAJA = "ciri_saja"
VARIAN_RUJUKAN = "rujukan"

_EPSILON = 1e-9  # selisih 0,88 - 0,86 bukan persis 0,02 di aritmetika float


@dataclass(frozen=True)
class Putusan:
    tingkat: Tingkat
    varian: str  # "" bila tanpa varian; dipakai template.keterangan_tingkat
    ciri_dibantah: CiriTerdeteksi | None  # ciri pernah_dibantah, atau None
    cek_fakta: list[Kandidat]  # artikel yang masuk respons, skor tertinggi lebih dulu
    tersaring: list[Kandidat] = field(default_factory=list)  # skor >= ambang_mirip tetapi tidak relevan (debug)
    # Ciri yang tidak ditampilkan karena tidak cukup untuk menaikkan tingkat (satu ciri sedang tanpa indikasi lain).
    ciri_dibuang: list[CiriTerdeteksi] = field(default_factory=list)


def _label(k: Kandidat) -> str:
    return (k.label or "").strip().lower()


def _cukup_untuk_hati_hati(ciri: list[CiriTerdeteksi]) -> bool:
    """Sedikitnya satu ciri berkeyakinan tinggi, atau dua ciri sedang. Satu ciri sedang saja (satu sumber, tanpa
    penguat) tidak menaikkan tingkat."""
    return any(c.keyakinan == "tinggi" for c in ciri) or len(ciri) >= 2


def _cocok_kuat(k: Kandidat, kata_teks: set[str], cfg: Pengaturan) -> bool:
    """Kecocokan yang boleh menaikkan tingkat ke kuat (bila tanpa konflik): skor >= ambang_cocok, atau kombinasi
    skor dan relevansi bila `kuat_kombinasi_aktif`."""
    if k.skor >= cfg.ambang_cocok:
        return True
    return (
        cfg.kuat_kombinasi_aktif
        and k.skor >= cfg.kuat_kombinasi_skor
        and k.relevansi >= cfg.kuat_kombinasi_relevansi
        and cocok.kata_judul_di_teks(kata_teks, k.judul, cfg) >= cfg.kuat_kombinasi_min_kata
    )


def tentukan(
    ciri: list[CiriTerdeteksi], kandidat: list[Kandidat], teks_bersih: str, cfg: Pengaturan | None = None
) -> Putusan:
    """Masukan: ciri hasil penggabungan (tanpa pernah_dibantah), kandidat pencarian, dan teks bersih (untuk
    kalimat bukti pernah_dibantah). Keluaran: putusan lengkap."""
    cfg = cfg or pengaturan_global
    urut = sorted(kandidat, key=lambda k: k.skor, reverse=True)
    di_atas_mirip = [k for k in urut if k.skor >= cfg.ambang_mirip]
    lolos = cfg.ambang_cocok if cfg.relevansi_lolos_skor is None else cfg.relevansi_lolos_skor
    peringkat_satu = urut[0] if urut and urut[0].skor >= lolos else None
    mirip = [k for k in di_atas_mirip if k is peringkat_satu or k.relevansi >= cfg.relevansi_minimum]
    tersaring = [k for k in di_atas_mirip if k not in mirip]

    kata_teks = cocok.kata_isi(teks_bersih) if cfg.kuat_kombinasi_aktif else set()
    dibantah_semua = [k for k in mirip if _label(k) in LABEL_DIBANTAH]
    # Penentu: artikel salah/penipuan relevan pertama yang cocok untuk kuat; tanpa itu, yang skornya tertinggi.
    # Bila kombinasi mati, hanya skor >= ambang_cocok yang cocok, jadi penentunya selalu yang pertama (perilaku lama).
    dibantah = next((k for k in dibantah_semua if _cocok_kuat(k, kata_teks, cfg)), None) or next(
        iter(dibantah_semua), None
    )
    dibantah_cocok = dibantah is not None and _cocok_kuat(dibantah, kata_teks, cfg)
    konflik = (
        [k for k in mirip if _label(k) in LABEL_KONFLIK and dibantah.skor - k.skor <= cfg.selisih_konflik + _EPSILON]
        if dibantah
        else []
    )
    satir_cocok = any(_label(k) == LABEL_SATIR and k.skor >= cfg.ambang_cocok for k in mirip)

    ciri_dibantah = None
    if dibantah:
        yakin = dibantah_cocok and not konflik
        ciri_dibantah = CiriTerdeteksi(
            ID_PERNAH_DIBANTAH, [cocok.kalimat_serupa(teks_bersih, dibantah, cfg)], "tinggi" if yakin else "sedang"
        )

    if dibantah_cocok and not konflik:
        tingkat, varian = Tingkat.KUAT, ""
    elif dibantah_cocok:
        tingkat, varian = Tingkat.HATI_HATI, VARIAN_KONFLIK
    elif satir_cocok and cfg.satir_hati_hati:
        tingkat, varian = Tingkat.HATI_HATI, VARIAN_SATIR
    elif dibantah:
        tingkat, varian = Tingkat.HATI_HATI, VARIAN_MIRIP
    elif _cukup_untuk_hati_hati(ciri):
        tingkat, varian = Tingkat.HATI_HATI, VARIAN_CIRI_SAJA
    else:
        tingkat, varian = Tingkat.TIDAK_DITEMUKAN, ""

    # Artikel yang menentukan tingkat (penentu, lalu yang berkonflik) tidak boleh terpotong batas jumlah tampilan.
    prioritas = ([dibantah] if dibantah else []) + konflik
    tampil = prioritas[: cfg.cek_fakta_maks]
    tampil += [k for k in mirip if k not in tampil][: max(0, cfg.cek_fakta_maks - len(tampil))]
    tampil.sort(key=lambda k: k.skor, reverse=True)

    if tingkat is Tingkat.TIDAK_DITEMUKAN and tampil:
        varian = VARIAN_RUJUKAN
    # Tingkat tidak_ditemukan dengan ciri tersisa berarti ciri itu hanya satu ciri sedang: tidak ditampilkan supaya
    # kartu tidak menyatakan "tidak ditemukan indikasi" bersama sebuah ciri.
    dibuang = list(ciri) if tingkat is Tingkat.TIDAK_DITEMUKAN else []
    return Putusan(tingkat, varian, ciri_dibantah, tampil, tersaring, dibuang)
