"""Kandidat model, endpoint, dan pengaturan per model. Nama model diperiksa lewat API pada 2026-10-09."""

from dataclasses import dataclass, field
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
DATA_LOKAL = SERVER / "data_lokal"
FOLDER_ENV = SERVER / ".env"
FOLDER_HASIL = DATA_LOKAL / "hasil_llm"
FOLDER_OCR = DATA_LOKAL / "hasil_ukur" / "rapidocr"
SUMBER_GAMBAR = DATA_LOKAL / "sumber_gambar.csv"

# 6 teks yang diulang untuk uji stabilitas: ragam (obrolan, unggahan, infografis, teks panjang, portal, artikel)
TEKS_ULANGAN = ("01", "04", "09", "11", "14", "17")
GAMBAR_PENCARIAN = ("09", "10", "11", "12", "13", "14")
BATAS_WAKTU_DETIK = 60
MAKS_TOKEN_KELUARAN = 2000
MAKS_429 = 2


@dataclass(frozen=True)
class Model:
    kunci: str            # nama pendek untuk folder hasil
    penyedia: str         # gemini | groq | mistral
    nama: str             # nama model di API
    url: str              # basis endpoint kompatibel OpenAI
    env: str              # nama variabel kunci di .env
    jeda_detik: float     # jeda awal antarpermintaan (naik otomatis kalau kena 429)
    # Urutan pilihan: dicoba dari kiri, turun ke berikutnya kalau API menolak (400). None = parameter dibuang.
    berpikir: tuple = (None,)
    format_keluaran: tuple = ("json_schema", "json_object", None)
    batas: dict = field(default_factory=dict)  # kuota resmi yang diketahui (untuk perhitungan anggaran)


GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai"
GROQ = "https://api.groq.com/openai/v1"

# Batas Gemini tidak dipublikasikan di dokumen (hanya di AI Studio): jeda awal konservatif 7 detik,
# lalu menyesuaikan sendiri dari header retry-after saat kena 429.
KANDIDAT = {
    m.kunci: m
    for m in (
        Model("gemini-3.5-flash", "gemini", "gemini-3.5-flash", GEMINI, "GEMINI_API_KEY", 7,
              berpikir=("none", "minimal", "low", None)),
        Model("gemini-3.5-flash-lite", "gemini", "gemini-3.5-flash-lite", GEMINI, "GEMINI_API_KEY", 7,
              berpikir=("none", "minimal", "low", None)),
        Model("gemini-3.1-flash-lite", "gemini", "gemini-3.1-flash-lite", GEMINI, "GEMINI_API_KEY", 7,
              berpikir=("none", "minimal", "low", None)),
        # Groq gratis: 30 RPM, 1K RPD, 8K TPM, 200K TPD per model (console.groq.com/docs/rate-limits, 2026-10-09)
        Model("gpt-oss-120b", "groq", "openai/gpt-oss-120b", GROQ, "GROQ_API_KEY", 15,
              berpikir=("low", None), batas=dict(rpm=30, rpd=1000, tpm=8000, tpd=200000)),
        Model("qwen3.8-27b", "groq", "qwen/qwen3.8-27b", GROQ, "GROQ_API_KEY", 15,
              berpikir=("none", "low", None), batas=dict(rpm=30, rpd=1000, tpm=8000, tpd=200000)),
    )
}
