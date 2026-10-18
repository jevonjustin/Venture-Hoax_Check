"""Tahap LLM: merangkum klaim utama dan menandai kandidat ciri lewat API model bahasa. Hasilnya tidak pernah
menentukan tingkat dan tidak pernah menyatakan benar atau salah (prompt melarangnya; klaim yang memuat kata
penilaian di luar teks ditolak).

Urutan penyedia: Groq (openai/gpt-oss-120b) -> Google (gemini-3.5-flash-lite) -> None (ciri hanya dari regex).
Kegagalan jaringan, batas waktu, status bukan 200, dan JSON rusak berakhir di penyedia berikutnya atau None, tidak
pernah menjadi galat 500. Groq kadang membalas 400 `json_validate_failed`; itu dicoba ulang sekali.

Privasi: yang dikirim hanya teks bersih yang sudah disamarkan (pipeline/samarkan.py), tanpa gambar. Kunci API
dibaca dari variabel lingkungan atau server/.env dan tidak pernah dicetak. Log hanya memuat penyedia, status, dan
durasi; teks, prompt, dan balasan tidak pernah masuk log.

Anggaran waktu dijaga dengan asyncio.wait_for di luar thread (urllib hanya membatasi tiap operasi soket). Thread yang
tertinggal setelah batas waktu berakhir sendiri lewat batas soketnya dan tidak menahan permintaan berikutnya karena
berjalan di kolam thread khusus yang cukup besar.
"""

import asyncio
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ..konfigurasi import DATA_LOKAL, VERSI_SERVER, Pengaturan, pengaturan as pengaturan_global
from . import cocok, klaim as modul_klaim, samarkan, setia
from .ciri import ID_BISA_DITANDAI
from .tipe import KandidatLLM

log = logging.getLogger("uvicorn.error").getChild("cekhoaks")

BATAS_KUTIPAN_PER_CIRI = 3
MAKS_BADAN_GALAT = 2000  # byte balasan galat yang dibaca (hanya untuk mengenali json_validate_failed)
SISA_ANGGARAN_MINIMUM = 0.5  # detik; di bawah ini penyedia berikutnya tidak dicoba
CADANGAN_SOKET_DETIK = 1.0  # batas soket thread dibuat sedikit di atas batas wait_for
SISA_UNTUK_ULANG_429 = 2.5  # detik anggaran yang harus tersisa setelah menunggu agar Groq dicoba lagi
HEADER_DISIMPAN = ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests")

# --- Prompt: harus sama dengan server/alat/ukur_llm/prompt.py (tes paritas menjaganya) ---

PENJELASAN_CIRI = {
    "permintaan_data_rahasia": "meminta penerima mengirim OTP, PIN, kata sandi, data kartu, atau uang (bukan larangan atau edukasi)",
    "ajakan_menyebarkan": "ajakan menyebarkan atau meneruskan pesan (\"sebarkan\", \"teruskan ke grup\")",
    "desakan_waktu": "menekan penerima agar segera bertindak (\"sebelum dihapus\", \"segera\"); bukan pihak yang menunggu dalam obrolan",
    "kapital_tanda_seru": "kalimat kapital semua atau tanda seru berlebihan",
    "link_mencurigakan": "tautan pemendek atau domain tidak resmi (kutipan memuat tautannya)",
    "sumber_tidak_jelas": "rujukan sumber samar tanpa nama (\"katanya\", \"info dari grup\", \"forwarded\")",
    "judul_clickbait": "judul yang melebih-lebihkan atau menyembunyikan inti agar diklik; judul peringatan lembaga bukan clickbait",
    "bahasa_provokatif": "bahasa memancing marah, benci, atau takut terhadap pihak atau kelompok; bukan keluhan antarpribadi dalam obrolan",
}
KATA_PENILAIAN = (
    "benar", "salah", "hoaks", "hoax", "fakta", "bohong", "palsu", "dusta", "menyesatkan",
    "terbukti", "keliru", "penipuan", "disinformasi",
)


def prompt_sistem() -> str:
    daftar = "\n".join(f"- {i}: {PENJELASAN_CIRI[i]}" for i in ID_BISA_DITANDAI)
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


# --- Penyedia dan kunci ---


@dataclass(frozen=True)
class Penyedia:
    nama: str  # "groq" | "gemini"; hanya nama ini yang boleh muncul di log
    url: str
    model: str
    env: str  # nama variabel lingkungan kunci
    berpikir: str | None  # nilai reasoning_effort yang diterima API pada pengukuran Sesi 5.4a


GROQ = Penyedia("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", "GROQ_API_KEY", "low")
GEMINI = Penyedia(
    "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.5-flash-lite", "GEMINI_API_KEY", "minimal"
)
URUTAN_PENYEDIA = (GROQ, GEMINI)
# Wajib eksplisit: Groq (lewat Cloudflare) menolak User-Agent bawaan urllib dengan 403 cf_1010 (terbukti 2026-10-13).
USER_AGENT = f"CekHoaks/{VERSI_SERVER}"


def urutan_penyedia(cfg: Pengaturan) -> tuple[Penyedia, ...]:
    return URUTAN_PENYEDIA if cfg.llm_cadangan_aktif else (GROQ,)
FILE_ENV = DATA_LOKAL.parent / ".env"


def muat_kunci(nama_env: str, file_env=None) -> str:
    """Kunci dari variabel lingkungan, lalu server/.env. String kosong bila tidak diisi. Tidak pernah dicetak."""
    nilai = os.environ.get(nama_env, "").strip()
    if nilai:
        return nilai
    jalur = file_env or FILE_ENV
    try:
        for baris in jalur.read_text(encoding="utf-8").splitlines():
            baris = baris.strip()
            if baris and not baris.startswith("#") and "=" in baris:
                k, v = baris.split("=", 1)
                if k.strip() == nama_env:
                    return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def ringkasan_status(cfg: Pengaturan | None = None) -> str:
    """Satu baris untuk banner: penyedia mana yang siap. Tidak memuat kunci."""
    cfg = cfg or pengaturan_global
    if not cfg.llm_aktif:
        return "dimatikan (CEKHOAKS_LLM=mati); ciri hanya dari regex"
    urutan = urutan_penyedia(cfg)
    siap = [p.nama for p in urutan if muat_kunci(p.env)]
    if not siap:
        return "TIDAK TERSEDIA: tidak ada kunci API terisi; ciri hanya dari regex"
    if not cfg.llm_cadangan_aktif:
        return f"{siap[0]} saja (cadangan dimatikan)" if siap == [GROQ.nama] else "TIDAK TERSEDIA: kunci groq belum diisi (cadangan dimatikan); ciri hanya dari regex"
    return " -> ".join(siap) + (" (kunci cadangan belum diisi)" if len(siap) < len(urutan) else "")


# --- Transport ---


class GagalJaringan(Exception):
    """Koneksi gagal atau batas soket terlewati. Tidak membawa pesan asli (bisa memuat alamat)."""


# Mengembalikan (status, isi) atau (status, isi, header); header hanya memuat HEADER_DISIMPAN.
Transport = Callable[[Penyedia, dict, str, float], tuple]


def _header_terpilih(h) -> dict[str, str]:
    try:
        return {k: str(h[k])[:40] for k in HEADER_DISIMPAN if h.get(k) is not None}
    except Exception:
        return {}


def transport_urllib(penyedia: Penyedia, badan: dict, kunci: str, timeout: float) -> tuple[int, str, dict]:
    """Satu panggilan POST ke /chat/completions. Mengembalikan (status HTTP, isi balasan, header terpilih)."""
    permintaan = urllib.request.Request(
        f"{penyedia.url}/chat/completions",
        data=json.dumps(badan).encode("utf-8"),
        headers={"Authorization": f"Bearer {kunci}", "Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(permintaan, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace"), {}
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(MAKS_BADAN_GALAT).decode("utf-8", errors="replace"), _header_terpilih(e.headers)
        except Exception:
            return e.code, "", _header_terpilih(e.headers)
    except Exception:  # URLError, TimeoutError, OSError, ValueError
        raise GagalJaringan from None


# Kolam khusus: thread yang tertinggal setelah batas waktu tidak menghabiskan kolam bawaan event loop.
_KOLAM = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm")


# --- Hasil ---


@dataclass(frozen=True)
class HasilLLM:
    klaim_utama: str  # bisa kosong
    kandidat: list[KandidatLLM]  # kutipan belum dipetakan ke teks asli
    penyedia: str
    durasi_ms: int
    percobaan: int = 1
    catatan: list[str] = field(default_factory=list)  # hanya kode pendek, tanpa teks


def _urai_json(konten: str):
    t = (konten or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return None


def urai_balasan(konten: str) -> tuple[str, list[KandidatLLM]] | None:
    """Mengurai isi balasan model. None bila bukan objek JSON dengan klaim_utama (string) dan ciri (daftar).

    Butir ciri yang rusak atau berid di luar daftar yang ditawarkan dibuang satu per satu; kutipan dibatasi tiga per
    ciri dan hanya yang berupa string tidak kosong."""
    data = _urai_json(konten)
    if not isinstance(data, dict) or not isinstance(data.get("klaim_utama"), str) or not isinstance(data.get("ciri"), list):
        return None
    kandidat: list[KandidatLLM] = []
    terlihat: set[str] = set()
    for butir in data["ciri"]:
        if not isinstance(butir, dict) or not isinstance(butir.get("id"), str) or not isinstance(butir.get("kutipan"), list):
            continue
        id_ciri = butir["id"].strip()
        if id_ciri not in ID_BISA_DITANDAI or id_ciri in terlihat:
            continue
        kutipan = [k.strip() for k in butir["kutipan"] if isinstance(k, str) and k.strip()][:BATAS_KUTIPAN_PER_CIRI]
        if kutipan:
            terlihat.add(id_ciri)
            kandidat.append(KandidatLLM(id_ciri, kutipan))
    return data["klaim_utama"].strip(), kandidat


def _badan(penyedia: Penyedia, teks_samar: str, cfg: Pengaturan) -> dict:
    badan = {
        "model": penyedia.model,
        "temperature": 0,
        "max_tokens": cfg.llm_maks_token,
        "messages": [
            {"role": "system", "content": prompt_sistem()},
            {"role": "user", "content": pesan_pengguna(teks_samar)},
        ],
        "response_format": {"type": "json_schema", "json_schema": {"name": "analisis", "strict": True, "schema": skema_json()}},
    }
    if penyedia.berpikir:
        badan["reasoning_effort"] = penyedia.berpikir
    return badan


_POLA_KODE = re.compile(r"[A-Za-z0-9_.\-]{1,60}")


def kode_galat(body: str) -> str | None:
    """Kode atau tipe galat dari isi balasan non-200, untuk diagnostik. Hanya field error.code / error.type
    (bila cocok pola pendek) atau nomor galat Cloudflare ("error code: 1010" menjadi "cf_1010"). Pesan galat,
    yang bisa memuat potongan masukan, tidak pernah diambil."""
    try:
        galat = json.loads(body).get("error")
    except (ValueError, AttributeError, TypeError):
        galat = None
    if isinstance(galat, dict):
        bagian = [str(galat[k]) for k in ("code", "type") if isinstance(galat.get(k), (str, int))]
        sah = [b for b in bagian if _POLA_KODE.fullmatch(b)]
        return "/".join(sah) or None
    m = re.search(r"error code:\s*(\d{3,5})", body or "", re.I)
    return f"cf_{m.group(1)}" if m else None


_SATUAN_DETIK = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def _durasi_detik(teks: str) -> float | None:
    """"6", "7.66s", "2m59.56s", "50ms" -> detik. None bila tidak dikenali."""
    t = (teks or "").strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return float(t)
    bagian = re.findall(r"(\d+(?:\.\d+)?)(ms|h|m|s)", t)
    if not bagian or re.sub(r"(\d+(?:\.\d+)?)(ms|h|m|s)", "", t):
        return None
    return sum(float(n) * _SATUAN_DETIK[u] for n, u in bagian)


def waktu_tunggu(header: dict, body: str) -> float | None:
    """Waktu tunggu (detik) yang disarankan balasan 429: header retry-after, lalu kalimat "try again in ..." di
    isi, lalu header reset kuota. Hanya angkanya yang diambil."""
    nilai = _durasi_detik(header.get("retry-after", ""))
    if nilai is None:
        m = re.search(r"try again in ([0-9a-z.]+)", body or "", re.I)
        nilai = _durasi_detik(m.group(1).rstrip(".")) if m else None
    if nilai is None:
        for k in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
            nilai = _durasi_detik(header.get(k, ""))
            if nilai is not None:
                break
    return nilai


def kuota_dari_galat(body: str) -> dict | None:
    """Angka "Limit 8000, Used 7000, Requested 1500" dari galat 429 (hanya tiga bilangan bulat)."""
    m = re.search(r"Limit (\d+), Used (\d+), Requested (\d+)", body or "")
    return {"batas": int(m.group(1)), "terpakai": int(m.group(2)), "diminta": int(m.group(3))} if m else None


def penggunaan_token(body: str) -> dict | None:
    """Jumlah token dari field usage balasan 200: prompt, completion (sudah termasuk penalaran), penalaran."""
    try:
        u = json.loads(body).get("usage")
        rinci = u.get("completion_tokens_details") or {}
        angka = {
            "prompt": u.get("prompt_tokens"), "completion": u.get("completion_tokens"),
            "penalaran": rinci.get("reasoning_tokens"),
        }
    except (ValueError, AttributeError, TypeError):
        return None
    angka = {k: v for k, v in angka.items() if isinstance(v, int) and not isinstance(v, bool)}
    return angka or None


def _catat(
    jejak: list | None, penyedia: Penyedia, status, ms: int, kode: str | None = None, token: dict | None = None,
    tunggu: float | None = None, kuota: dict | None = None,
) -> None:
    """Satu baris diagnostik per percobaan: penyedia, status (angka HTTP atau kata pendek), durasi, kode galat,
    jumlah token, waktu tunggu 429 yang disarankan, dan angka kuota. Hanya kode dan angka; tidak ada teks."""
    if jejak is not None:
        jejak.append({
            "penyedia": penyedia.nama, "status": status, "ms": ms, "kode": kode, "token": token, "tunggu": tunggu,
            "kuota": kuota,
        })


def _terpotong(body: str) -> bool:
    """finish_reason "length": balasan berhenti karena batas token, jadi JSON-nya tidak utuh."""
    try:
        return json.loads(body)["choices"][0].get("finish_reason") == "length"
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return False


def _isi_balasan(body: str) -> str | None:
    try:
        return json.loads(body)["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None


async def _panggil(transport: Transport, penyedia: Penyedia, badan: dict, kunci: str, batas: float) -> tuple[int, str]:
    """Satu panggilan di kolam thread dengan batas waktu mutlak `batas` detik (wait_for di luar thread)."""
    loop = asyncio.get_running_loop()
    masa = loop.run_in_executor(_KOLAM, transport, penyedia, badan, kunci, batas + CADANGAN_SOKET_DETIK)
    return await asyncio.wait_for(masa, timeout=batas)


async def _coba_penyedia(
    penyedia: Penyedia, kunci: str, teks_samar: str, cfg: Pengaturan, transport: Transport,
    mulai: float, batas_penyedia: float, jejak: list | None = None,
) -> HasilLLM | None:
    badan = _badan(penyedia, teks_samar, cfg)
    ulang_json = ulang_429 = False
    percobaan = 0
    while True:
        sisa = cfg.llm_anggaran_total - (time.monotonic() - mulai)
        batas = min(batas_penyedia, sisa)
        if sisa < SISA_ANGGARAN_MINIMUM or batas <= 0:
            log.info("LLM %s: anggaran waktu habis", penyedia.nama)
            _catat(jejak, penyedia, "anggaran_habis", 0)
            return None
        percobaan += 1
        t0 = time.monotonic()
        try:
            hasil_transport = await _panggil(transport, penyedia, badan, kunci, batas)
            status, body = hasil_transport[0], hasil_transport[1]
            header = hasil_transport[2] if len(hasil_transport) > 2 else {}
        except asyncio.TimeoutError:
            ms = int((time.monotonic() - t0) * 1000)
            log.info("LLM %s: status=timeout %d ms", penyedia.nama, ms)
            _catat(jejak, penyedia, "timeout", ms)
            return None
        except GagalJaringan:
            ms = int((time.monotonic() - t0) * 1000)
            log.info("LLM %s: status=jaringan_gagal %d ms", penyedia.nama, ms)
            _catat(jejak, penyedia, "jaringan_gagal", ms)
            return None
        except Exception as e:  # transport rusak: jangan menjatuhkan /analisis
            log.warning("LLM %s: galat tak terduga (%s)", penyedia.nama, type(e).__name__)
            _catat(jejak, penyedia, "galat_tak_terduga", int((time.monotonic() - t0) * 1000))
            return None
        ms = int((time.monotonic() - t0) * 1000)
        kode = kode_galat(body) if status != 200 else None
        token = penggunaan_token(body) if status == 200 else None
        tunggu = waktu_tunggu(header, body) if status == 429 else None
        kuota = kuota_dari_galat(body) if status == 429 else None
        terpotong = status == 200 and _terpotong(body)
        log.info(
            "LLM %s: status=%s %d ms%s%s%s", penyedia.nama, "terpotong" if terpotong else status, ms,
            f" kode={kode}" if kode else "",
            f" token={token['prompt']}/{token.get('completion', '-')}" if token and "prompt" in token else "",
            f" tunggu={tunggu:.1f}s" if tunggu is not None else "",
        )
        _catat(jejak, penyedia, "terpotong" if terpotong else status, ms, kode, token, tunggu, kuota)
        if status == 429 and not ulang_429 and tunggu is not None:
            sisa_setelah = cfg.llm_anggaran_total - (time.monotonic() - mulai) - tunggu
            if tunggu <= cfg.llm_tunggu_429_maks and sisa_setelah >= SISA_UNTUK_ULANG_429:
                ulang_429 = True
                await asyncio.sleep(tunggu + 0.1)
                continue
        if status == 400 and "json_validate_failed" in body and not ulang_json:
            ulang_json = True
            continue
        if status != 200 or terpotong:
            return None  # terpotong: JSON tidak utuh, dan mengulang dengan batas yang sama hasilnya sama
        konten = _isi_balasan(body)
        urai = urai_balasan(konten) if konten is not None else None
        if urai is None:
            log.info("LLM %s: balasan tidak sah (JSON rusak)", penyedia.nama)
            _catat(jejak, penyedia, "json_rusak", ms, token=token)
            return None
        klaim, kandidat = urai
        return HasilLLM(klaim, kandidat, penyedia.nama, int((time.monotonic() - mulai) * 1000), percobaan)


async def analisis(
    teks_samar: str, cfg: Pengaturan | None = None, transport: Transport | None = None, jejak: list | None = None,
) -> HasilLLM | None:
    """Masukan: teks bersih yang sudah disamarkan. Keluaran: hasil penyedia pertama yang berhasil, atau None.

    Klaim kosong tidak dicoba ulang (boros kuota per menit); orkestrator memakai klaim cadangan.
    `jejak`, bila berupa list, diisi satu dict per percobaan (penyedia, status, ms, kode, token, tunggu, kuota)
    untuk diagnostik: hanya kode dan angka, tidak ada teks."""
    cfg = cfg or pengaturan_global
    if not cfg.llm_aktif:
        return None
    transport = transport or transport_urllib
    mulai = time.monotonic()
    batas = {GROQ.nama: cfg.llm_timeout_groq, GEMINI.nama: cfg.llm_timeout_gemini}
    for penyedia in urutan_penyedia(cfg):
        kunci = muat_kunci(penyedia.env)
        if not kunci:
            log.info("LLM %s: dilewati (kunci tidak diisi)", penyedia.nama)
            _catat(jejak, penyedia, "tanpa_kunci", 0)
            continue
        if cfg.llm_anggaran_total - (time.monotonic() - mulai) < SISA_ANGGARAN_MINIMUM:
            break
        hasil = await _coba_penyedia(penyedia, kunci, teks_samar, cfg, transport, mulai, batas[penyedia.nama], jejak)
        if hasil is not None:
            return hasil
    return None


# --- Pemeriksaan hasil: kutipan dan klaim ---


def petakan_kandidat(kandidat: list[KandidatLLM], teks_samar: str, teks_asli: str) -> tuple[list[KandidatLLM], int]:
    """Memeriksa kutipan LLM terhadap teks yang dikirim ke LLM, lalu memetakannya ke potongan teks asli (supaya
    `bukti` tidak memuat token penyamaran). Mengembalikan (kandidat sah, jumlah kutipan yang ditolak)."""
    sah, ditolak = [], 0
    for k in kandidat:
        asli = []
        for kutipan in k.kutipan:
            potongan = samarkan.kutipan_ke_asli(kutipan, teks_samar, teks_asli)
            if potongan:
                asli.append(potongan)
            else:
                ditolak += 1
        if asli:
            sah.append(KandidatLLM(k.id, asli))
    return sah, ditolak


def kesetiaan_klaim(klaim: str, teks: str) -> float:
    """Bagian kata isi klaim yang ada di teks (0-1). Kata dianggap ada bila menjadi potongan teks, sehingga kata
    yang ditempel OCR ("pemerintahagar") tetap dihitung. Klaim tanpa kata isi bernilai 0."""
    kata = cocok.kata_isi(klaim)
    if not kata:
        return 0.0
    acuan = re.sub(r"\s+", " ", teks).lower()
    return sum(1 for k in kata if k in acuan) / len(kata)


def kata_penilaian_baru(klaim: str, teks: str) -> list[str]:
    """Kata penilaian (benar, salah, hoaks, ...) yang ada di klaim tetapi tidak ada di teks."""
    k, t = klaim.lower(), teks.lower()
    return [w for w in KATA_PENILAIAN if re.search(rf"\b{w}\b", k) and w not in t]


def alasan_klaim_ditolak(klaim: str, teks_samar: str, cfg: Pengaturan | None = None) -> tuple[str, int] | None:
    """None bila klaim dapat dipakai; selain itu (kode alasan, jumlah token). Hanya kode dan angka, tanpa teks."""
    cfg = cfg or pengaturan_global
    if not klaim.strip():
        return "kosong", 0
    if any(t in klaim for t in (samarkan.TOKEN_NOMOR, samarkan.TOKEN_EMAIL, samarkan.TOKEN_AKUN)):
        return "token_penyamaran", 1
    if modul_klaim.memuat_kata_ganti_kedua(klaim):
        return "kata_ganti_kedua", 1
    baru = kata_penilaian_baru(klaim, teks_samar)
    if baru:
        return "kata_penilaian_baru", len(baru)
    if kesetiaan_klaim(klaim, teks_samar) < cfg.klaim_kesetiaan_minimum:
        return "kesetiaan_rendah", 1
    if cfg.periksa_kesetiaan_klaim:
        return setia.periksa_kesetiaan(klaim, teks_samar, cfg)
    return None


def klaim_dapat_dipakai(klaim: str, teks_samar: str, cfg: Pengaturan | None = None) -> bool:
    """Klaim LLM dipakai bila tidak kosong, setia pada teks (rasio kata isi >= klaim_kesetiaan_minimum), tidak
    memuat kata penilaian di luar teks, tidak memuat token penyamaran, dan tidak memuat kata ganti orang kedua.
    Bila `periksa_kesetiaan_klaim` menyala, angka, nama, dan kata isi juga harus setia (pipeline/setia.py)."""
    return alasan_klaim_ditolak(klaim, teks_samar, cfg) is None
