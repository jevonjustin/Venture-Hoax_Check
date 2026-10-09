"""Prompt sistem dan skema keluaran untuk analisis teks. Daftar id ciri dibaca dari server/app/skema.py."""

import ast
from pathlib import Path

SKEMA_SERVER = Path(__file__).resolve().parents[2] / "app" / "skema.py"

# Penjelasan singkat sesuai RANCANGAN_PROYEK.md §8
PENJELASAN = {
    "ajakan_menyebarkan": "ajakan menyebarkan atau meneruskan pesan (\"sebarkan\", \"viralkan\", \"teruskan ke grup\")",
    "desakan_waktu": "desakan waktu atau tekanan agar segera bertindak (\"sebelum dihapus\", \"segera\", \"hari ini terakhir\")",
    "kapital_tanda_seru": "huruf kapital dan tanda seru berlebihan",
    "link_mencurigakan": "tautan pemendek atau tautan yang tidak jelas dan tidak resmi",
    "sumber_tidak_jelas": "tidak menyebut sumber yang bisa dicek (tanpa instansi, nama, tanggal, atau tautan resmi)",
    "judul_clickbait": "judul memancing klik dengan membesar-besarkan atau menyembunyikan informasi inti",
    "bahasa_provokatif": "bahasa yang memancing emosi seperti marah, takut, panik, atau kebencian",
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
    return f"""Kamu adalah pengekstrak informasi untuk alat pemandu pemeriksaan hoaks. Tugasmu hanya membaca teks dan menandai ciri yang tampak. Kamu bukan hakim: jangan pernah menyatakan sebuah informasi benar atau salah.

Masukan adalah teks hasil pembacaan (OCR) dari tangkapan layar ponsel. Teks bisa berantakan atau salah baca. Data pribadi sudah diganti dengan [NOMOR], [EMAIL], dan [AKUN].

Abaikan teks antarmuka aplikasi: nama akun, jam, jumlah suka dan komentar, tombol, menu situs, status baterai, dan sejenisnya.

Keluarkan HANYA satu objek JSON dengan bentuk:
{{"klaim_utama": "...", "ciri": [{{"id": "...", "kutipan": ["..."]}}]}}

Aturan klaim_utama:
- Satu kalimat netral yang merangkum klaim inti yang disampaikan teks, dengan kata-kata sedekat mungkin dengan teks.
- Jangan menilai. Jangan memakai kata penilaian seperti benar, salah, hoaks, fakta, bohong, palsu, atau menyesatkan, kecuali kata itu memang ada di teks.
- Kalau teks tidak memuat klaim (hanya antarmuka, obrolan pribadi, atau kosong), isi dengan string kosong.

Aturan ciri:
- id hanya boleh salah satu dari daftar ini:
{daftar}
- Sertakan ciri hanya kalau jelas tampak di teks. Tidak ada ciri yang tampak: isi dengan daftar kosong.
- kutipan berisi satu sampai tiga potongan teks yang disalin PERSIS dari masukan: jangan memperbaiki ejaan, jangan menyingkat, jangan menambah kata. Kalau tidak ada potongan persis yang menjadi bukti, jangan sertakan ciri itu.
- Satu id hanya muncul sekali."""


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
