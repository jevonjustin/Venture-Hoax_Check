"""Model data sesuai kontrak API (docs/API.md)."""

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Tingkat(str, Enum):
    KUAT = "kuat"
    HATI_HATI = "hati_hati"
    TIDAK_DITEMUKAN = "tidak_ditemukan"


# Id ciri bagian dari kontrak API (docs/API.md, RANCANGAN_PROYEK.md §8). Jangan diubah tanpa mengubah kontrak.
ID_CIRI_TERKUNCI = (
    "ajakan_menyebarkan",
    "desakan_waktu",
    "kapital_tanda_seru",
    "link_mencurigakan",
    "sumber_tidak_jelas",
    "judul_clickbait",
    "bahasa_provokatif",
    "pernah_dibantah",
)


class Ciri(BaseModel):
    id: str = Field(description="Id tetap dari daftar ciri (RANCANGAN_PROYEK.md §8)")
    nama: str
    bukti: list[str] = Field(description="Potongan teks dari gambar yang menunjukkan ciri ini")
    penjelasan: str = Field(description="Teks template, bukan buatan LLM")
    keyakinan: Literal["tinggi", "sedang"]


class ArtikelCekFakta(BaseModel):
    judul: str
    sumber: str
    url: str
    skor_kemiripan: float = Field(ge=0, le=1)
    label: str = Field(description="Kesimpulan artikel, misalnya salah, menyesatkan, hoaks")
    tanggal: date | None = Field(description="Tanggal terbit artikel (ISO 8601)")


class HasilAnalisis(BaseModel):
    id_permintaan: str
    tingkat: Tingkat
    klaim_utama: str | None
    ciri: list[Ciri]
    cek_fakta: list[ArtikelCekFakta]
    teks_terbaca: str
    durasi_ms: int


class StatusServer(BaseModel):
    status: Literal["ok"]
    versi: str


class IsiGalat(BaseModel):
    kode: str
    pesan: str = Field(description="Untuk log developer; teks untuk pengguna ada di aplikasi")


class ResponsGalat(BaseModel):
    galat: IsiGalat
