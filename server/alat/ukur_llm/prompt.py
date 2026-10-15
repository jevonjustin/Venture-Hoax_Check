"""Prompt sistem dan skema keluaran untuk analisis teks. Daftar id ciri dibaca dari server/app/skema.py."""

import ast
from pathlib import Path

SKEMA_SERVER = Path(__file__).resolve().parents[2] / "app" / "skema.py"

# Penjelasan singkat sesuai RANCANGAN_PROYEK.md §8
PENJELASAN = {
    "permintaan_data_rahasia": "meminta penerima mengirim OTP, PIN, kata sandi, data kartu, atau uang (bukan larangan atau edukasi)",
    "ajakan_menyebarkan": "ajakan menyebarkan atau meneruskan pesan (\"sebarkan\", \"teruskan ke grup\")",
    "desakan_waktu": "menekan penerima agar segera bertindak (\"sebelum dihapus\", \"segera\"); bukan pihak yang menunggu dalam obrolan",
    "kapital_tanda_seru": "kalimat kapital semua atau tanda seru berlebihan",
    "link_mencurigakan": "tautan pemendek atau domain tidak resmi (kutipan memuat tautannya)",
    "sumber_tidak_jelas": "rujukan sumber samar tanpa nama (\"katanya\", \"info dari grup\", \"forwarded\")",
    "judul_clickbait": "judul yang melebih-lebihkan atau menyembunyikan inti agar diklik; judul peringatan lembaga bukan clickbait",
    "bahasa_provokatif": "bahasa memancing marah, benci, atau takut terhadap pihak atau kelompok; bukan keluhan antarpribadi dalam obrolan",
}
# pernah_dibantah ditentukan server lewat pencarian database cek fakta, bukan oleh LLM.
ID_DISERAHKAN_KE_SERVER = {"pernah_dibantah"}

KATA_PENILAIAN = (
    "benar", "salah", "hoaks", "hoax", "fakta", "bohong", "palsu", "dusta", "menyesatkan",
    "terbukti", "keliru", "penipuan", "disinformasi",
)


def id_terkunci() -> tuple[str, ...]:
    """Membaca ID_CIRI_TERKUNCI dari skema server tanpa mengimpor modul (pydantic tidak ada di venv alat)."""
    pohon = ast.parse(SKEMA_SERVER.read_text(encoding="utf-8"))
    for simpul in pohon.body:
        if isinstance(simpul, ast.Assign) and any(getattr(t, "id", "") == "ID_CIRI_TERKUNCI" for t in simpul.targets):
            return tuple(ast.literal_eval(simpul.value))
    raise RuntimeError("ID_CIRI_TERKUNCI tidak ditemukan di server/app/skema.py")


def id_untuk_llm() -> tuple[str, ...]:
    ids = tuple(i for i in id_terkunci() if i not in ID_DISERAHKAN_KE_SERVER)
    assert set(ids) == set(PENJELASAN), "PENJELASAN tidak sinkron dengan daftar id terkunci"
    return ids


def prompt_sistem() -> str:
    daftar = "\n".join(f"- {i}: {PENJELASAN[i]}" for i in id_untuk_llm())
    return f"""Kamu pengekstrak informasi untuk alat pemandu pemeriksaan hoaks: baca teks, tandai ciri yang tampak. Kamu bukan hakim.

Masukan: teks OCR tangkapan layar ponsel (bisa salah baca). Data pribadi diganti [NOMOR], [EMAIL], [AKUN]. Abaikan teks antarmuka aplikasi (nama akun, jam, suka, tombol, menu).

Keluarkan HANYA satu objek JSON:
{{"klaim_utama": "...", "ciri": [{{"id": "...", "kutipan": ["..."]}}]}}

klaim_utama: satu kalimat netral berisi klaim inti, kata-katanya sedekat mungkin dengan teks, lengkap dengan subjek, jumlah, dan angka (gabungkan dari baris judul yang berdekatan). Isi juga untuk judul berita, iklan atau lowongan, dan pertanyaan yang memuat klaim tersirat ("laut kering, pertanda apa ya" = klaim laut kering). Tulis sebagai orang ketiga, tanpa kamu atau Anda. Jangan memakai kata penilaian (benar, salah, hoaks, fakta, bohong, palsu, menyesatkan) kecuali ada di teks. Kosongkan hanya bila tak ada informasi yang diklaim.

ciri: id hanya dari daftar:
{daftar}
Sertakan hanya ciri yang jelas tampak (boleh kosong). kutipan: 1-3 potongan yang disalin PERSIS dari masukan (jangan memperbaiki ejaan atau menyingkat); tanpa potongan persis, jangan sertakan ciri itu. Satu id sekali saja."""


def pesan_pengguna(teks: str) -> str:
    return f"Teks hasil pembacaan layar:\n<<<\n{teks}\n>>>"


def skema_json() -> dict:
    """Skema untuk response_format json_schema. id sengaja berupa string bebas: kepatuhan id diperiksa sendiri."""
    return {
        "type": "object",
        "properties": {
            "klaim_utama": {"type": "string"},
            "ciri": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "kutipan": {"type": "array", "items": {"type": "string"}}},
                    "required": ["id", "kutipan"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["klaim_utama", "ciri"],
        "additionalProperties": False,
    }
