"""Tipe yang dipakai bersama oleh modul pipeline."""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from ..skema import Tingkat


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
class CiriTerdeteksi:
    """Hasil deteksi sebelum diberi nama dan penjelasan oleh tahap template."""

    id: str
    bukti: list[str]
    keyakinan: str  # "tinggi" | "sedang"


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
    # Khusus dummy: tingkat skenario yang dipilih di tahap baca. Hilang di Sesi 5.5.
    skenario: Tingkat | None = None
