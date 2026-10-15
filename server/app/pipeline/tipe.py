"""Tipe yang dipakai bersama oleh modul pipeline."""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class BarisTeks:
    """Satu baris hasil baca: teks, kotak pembatas (4 titik x,y dalam piksel gambar), dan keyakinan 0-1."""

    teks: str
    kotak: tuple[tuple[float, float], ...]
    skor: float


@dataclass(frozen=True)
class HasilBaca:
    """Keluaran tahap baca. `teks` adalah semua baris yang digabung dengan baris baru."""

    teks: str
    baris: list[BarisTeks]

    @property
    def karakter_bermakna(self) -> int:
        return sum(c.isalnum() for c in self.teks)


@dataclass(frozen=True)
class BarisDibuang:
    """Baris yang dibuang pembersih beserta alasannya. Hanya untuk debug, tidak dikirim ke HP."""

    teks: str
    alasan: str


@dataclass(frozen=True)
class HasilBersih:
    """Keluaran tahap bersih: baris yang dipertahankan digabung dengan baris baru, urutan asli."""

    teks: str
    dibuang: list[BarisDibuang]


@dataclass(frozen=True)
class CiriRegex:
    """Hasil satu detektor regex. `kekuatan` adalah "kuat" (pola yang hampir pasti) atau "lemah"."""

    id: str
    kekuatan: str
    bukti: list[str]
    # Jumlah bukti pertama yang berasal dari pola kuat (bukti disusun kuat lebih dulu, lalu lemah).
    n_kuat: int = 0


@dataclass(frozen=True)
class KandidatLLM:
    """Ciri yang ditandai LLM beserta kutipannya (belum diverifikasi)."""

    id: str
    kutipan: list[str]


@dataclass(frozen=True)
class CiriTerdeteksi:
    """Hasil deteksi sebelum diberi nama dan penjelasan oleh tahap template."""

    id: str
    bukti: list[str]
    keyakinan: str  # "tinggi" | "sedang"


@dataclass(frozen=True)
class Kandidat:
    """Satu artikel cek fakta hasil pencarian kemiripan (internal; belum disaring untuk respons).

    `narasi` hanya dipakai server untuk memilih kalimat bukti dan tidak dikirim ke HP."""

    judul: str
    sumber: str
    url: str
    skor: float
    label: str
    tanggal: date | None
    url_format_lama: bool
    narasi: str = ""
    # Bagian bobot kata isi judul artikel yang ada di teks (0-1), diisi pencarian. 1,0 bila tidak dihitung.
    relevansi: float = 1.0


@dataclass
class Konteks:
    """Keadaan satu permintaan. Dibuat oleh pemanggil (endpoint atau app.cek)."""

    id_permintaan: str
    # Rentang jeda buatan (detik). (0, 0) berarti tanpa jeda.
    jeda_detik: tuple[float, float]
    # Mengembalikan True jika klien memutus koneksi. Dipakai selama tahap yang lama.
    klien_putus: Callable[[], Awaitable[bool]]
    # Nilai paksa dari query ?paksa= atau PAKSA_TINGKAT; sudah divalidasi pemanggil.
    paksa: str | None = None
    # Waktu permintaan mulai diterima (time.perf_counter), untuk durasi_ms.
    mulai: float = field(default_factory=time.perf_counter)
    # Diisi orkestrator hanya kalau pemanggil memberi dict (app.cek) agar hasil antara bisa dicetak.
    diagnostik: dict | None = None
