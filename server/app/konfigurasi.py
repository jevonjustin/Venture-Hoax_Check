"""Satu tempat untuk semua pengaturan server.

Nilai bawaan bisa ditimpa variabel lingkungan. Pengaturan dibaca sekali saat server mulai, dan
nilai yang tidak sah membuat server menolak jalan (lihat __main__.py).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .skema import Tingkat

# server/data_lokal/ (masuk .gitignore): database cek fakta dan model e5 ada di dalamnya.
DATA_LOKAL = Path(__file__).resolve().parents[1] / "data_lokal"

# Versi server: dipakai /status, banner, dan User-Agent permintaan ke penyedia LLM.
VERSI_SERVER = "0.6.0"

PAKSA_TEKS_TIDAK_TERBACA = "teks_tidak_terbaca"
# Satu-satunya sumber daftar nilai sah PAKSA_TINGKAT dan query ?paksa= (selaras dengan docs/API.md).
NILAI_PAKSA = tuple(t.value for t in Tingkat) + (PAKSA_TEKS_TIDAK_TERBACA,)


class KonfigurasiTidakValid(ValueError):
    """Pengaturan dari variabel lingkungan tidak sah. Pesannya siap dicetak ke pengguna."""


@dataclass
class Pengaturan:
    host: str = "0.0.0.0"  # semua antarmuka jaringan, supaya HP di jaringan yang sama bisa masuk
    port: int = 8000
    batas_gambar_byte: int = 8 * 1024 * 1024
    # Jeda buatan hanya untuk menguji pembatalan; waktu proses sungguhan sudah ada sejak Sesi 5.2b.
    jeda_min_detik: float = 0.0
    jeda_maks_detik: float = 0.0
    # Jumlah minimum karakter huruf-angka hasil baca; di bawahnya galat teks_tidak_terbaca.
    ambang_teks_karakter: int = 20
    paksa_tingkat: str | None = None
    # Pembersihan teks UI (pipeline/bersih.py). Semua dibuat konservatif: lebih baik ada sisa teks UI
    # daripada membuang kalimat isi.
    # Bilah status hanya dicari di pita ini (fraksi tinggi gambar, dihitung dari tengah baris).
    bersih_pita_atas: float = 0.06
    # Baris tombol, menu, dan penanda waktu hanya dibuang kalau tidak lebih dari ini kata.
    bersih_maks_kata_ui: int = 3
    # Deret menu: minimal jumlah baris pendek sejajar (satu menu situs) agar semuanya dibuang.
    bersih_menu_min_baris: int = 3
    # Dua baris dianggap sejajar kalau selisih tengah vertikalnya tidak lebih dari fraksi tinggi gambar ini.
    bersih_toleransi_sejajar: float = 0.02
    # Baris menu: tiap baris tidak lebih dari ini kata.
    bersih_menu_maks_kata: int = 3
    # Detektor ciri (pipeline/ciri.py).
    ciri_bukti_maks: int = 3  # bukti per ciri
    ciri_bukti_maks_karakter: int = 140  # panjang tiap bukti
    ciri_bukti_konteks: int = 30  # karakter di kiri dan kanan kecocokan yang ikut dikutip
    ciri_kapital_rasio: float = 0.4  # rasio huruf kapital yang dianggap berlebihan (pola lemah)
    ciri_kapital_min_huruf: int = 30  # rasio hanya dinilai kalau teks punya sedikitnya sekian huruf
    ciri_kalimat_kapital_kuat: int = 2  # jumlah kalimat kapital penuh bertanda seru untuk pola kuat
    ciri_seru_beruntun_kuat: int = 3  # jumlah tanda seru beruntun untuk pola kuat
    # Klaim utama heuristik (pipeline/klaim.py).
    klaim_min_kata: int = 5
    klaim_maks_karakter: int = 200
    klaim_skor_minimum: float = 3.0  # Sesi 5.5: naik dari 2,0 supaya infografis dan obrolan tanpa pernyataan kosong
    # Baris OCR yang tidak berakhir tanda baca disambung ke baris berikutnya kalau panjangnya sedikitnya
    # sekian kali baris terpanjang (kalimat yang terbelah karena lebar layar).
    klaim_rasio_baris_panjang: float = 0.8
    # Pencarian cek fakta (pipeline/cocok.py). Dimatikan lewat CEKHOAKS_CEKFAKTA=mati.
    cek_fakta_aktif: bool = True
    cek_fakta_folder: Path = DATA_LOKAL / "cek_fakta"
    model_folder: Path = DATA_LOKAL / "model"
    cek_fakta_ukuran: str = "base"  # vektor dan model harus berukuran sama (small | base)
    cek_fakta_varian: str = "fp32"
    # Panjang token KUERI e5 (passage dibatasi saat vektor dibangun, tercatat di meta vektor). Bawaan 256 sama
    # dengan sebelumnya; e5-base mendukung sampai 512. Hanya mengubah pemotongan kueri, bukan vektor artikel.
    e5_maks_token_kueri: int = 256
    # Hanya untuk alat evaluasi: model ONNX dan vektor (.npy, dengan .json di sebelahnya) hasil kuantisasi lokal.
    # None = berkas bawaan di model_folder dan cek_fakta_folder. Server tidak membacanya dari lingkungan.
    e5_model_berkas: Path | None = None
    e5_vektor_berkas: Path | None = None
    cocok_top_k: int = 5  # kandidat yang diambil dari pencarian
    cek_fakta_maks: int = 3  # artikel paling banyak di respons
    # Ambang skor e5-base fp32 (titik awal Sesi 5.3; ditetapkan final di Sesi 5.6).
    ambang_cocok: float = 0.88  # "cocok": boleh menaikkan tingkat ke kuat
    ambang_mirip: float = 0.85  # "mirip": hanya hati_hati, dan batas bawah artikel yang ditampilkan
    # Artikel benar, klarifikasi, atau satir yang skornya tidak lebih rendah dari artikel salah/penipuan terbaik
    # dikurangi selisih ini dianggap berkonflik, sehingga tingkat kuat turun menjadi hati_hati.
    selisih_konflik: float = 0.02
    # Artikel yang tampil dan dihitung hanya bila bobot kata isi judulnya yang ada di teks sedikitnya sekian
    # (0-1). Artikel peringkat 1 dengan skor >= ambang_cocok lolos tanpa syarat ini. Aturan sementara: ambang
    # final ditetapkan di Sesi 5.6.
    relevansi_minimum: float = 0.40
    # Batas skor peringkat 1 yang lolos tanpa syarat relevansi; None = ambang_cocok (perilaku lama).
    relevansi_lolos_skor: float | None = None
    # Sesi 5.6, semua MATI di bawaan dataclass (profil "lama"); profil "akhir" (PROFIL_AMBANG) menyalakannya.
    # Toleransi salah eja OCR pada relevansi: kata isi judul (>= 5 huruf, tanpa angka) dianggap ada di teks bila
    # berbeda paling banyak sekian huruf dari kata teks ("Fiktlwam" untuk "Fiktiwan").
    relevansi_toleransi_ocr: bool = False
    relevansi_edit_pendek: int = 1  # kata judul 5-6 huruf
    relevansi_edit_panjang: int = 2  # kata judul >= 7 huruf
    # Kuat lewat kombinasi skor dan relevansi: artikel salah/penipuan dengan skor di bawah ambang_cocok tetapi
    # sedikitnya kuat_kombinasi_skor, relevansi sedikitnya kuat_kombinasi_relevansi, dan sedikitnya
    # kuat_kombinasi_min_kata kata isi judul yang ada di teks (judul pendek tidak cukup) diperlakukan cocok.
    kuat_kombinasi_aktif: bool = False
    kuat_kombinasi_skor: float = 0.86
    kuat_kombinasi_relevansi: float = 0.70
    kuat_kombinasi_min_kata: int = 4
    # Satir dengan skor >= ambang_cocok memberi hati_hati (tidak pernah kuat).
    satir_hati_hati: bool = True
    # Model bahasa (pipeline/llm.py). Dimatikan lewat CEKHOAKS_LLM=mati (uji tanpa internet, cadangan demo).
    llm_aktif: bool = True
    # False (CEKHOAKS_LLM_CADANGAN=mati): rantai hanya Groq lalu None, supaya teks pasti tidak dikirim ke Google.
    llm_cadangan_aktif: bool = True
    llm_timeout_groq: float = 4.0  # detik; p95 terukur gpt-oss-120b 1,4 detik (Sesi 5.4a); lihat LLM_TIMEOUT_GROQ_SENDIRI
    llm_timeout_gemini: float = 6.0  # detik; p95 terukur gemini-3.5-flash-lite 4,7 detik
    llm_anggaran_total: float = 9.0  # detik untuk semua penyedia dan percobaan ulang; aplikasi menunggu 60 detik
    # Completion terukur paling banyak 438 token (Sesi 5.4a, 5.5); 1.000 memberi ruang dan menjaga kuota per menit.
    llm_maks_token: int = 1000
    # Balasan 429 dengan waktu tunggu sampai sekian detik (dan sisa anggaran cukup untuk satu panggilan lagi)
    # ditunggu lalu penyedia yang sama dicoba sekali lagi; selain itu langsung pindah penyedia.
    llm_tunggu_429_maks: float = 3.0
    # Klaim LLM dipakai hanya bila bagian kata isinya yang ada di teks sedikitnya ini; selain itu klaim heuristik.
    # Dari 98 klaim hasil_llm (5 model): 0,5 meloloskan 91; 0,7 hanya 69 karena parafrase sah ("mengusulkan" vs
    # "usul") dan salah baca OCR menurunkan nilai. Klaim yang mengarang ("Wakil Menteri", gambar 14) bernilai 0,40.
    klaim_kesetiaan_minimum: float = 0.5
    # Pemeriksaan kesetiaan ketat (pipeline/setia.py): angka, nama, dan kata isi klaim LLM harus ada di teks.
    # Mati di profil "lama", menyala di profil "akhir"; klaim yang gagal diganti klaim heuristik.
    periksa_kesetiaan_klaim: bool = False
    klaim_setia_edit_pendek: int = 1  # jarak edit OCR yang ditoleransi untuk kata dasar 5-6 huruf (<=4 huruf: persis)
    klaim_setia_edit_panjang: int = 2  # idem untuk kata dasar >= 7 huruf
    klaim_setia_rasio_nama: float = 0.8  # kemiripan minimum nama/singkatan klaim terhadap token teks
    klaim_setia_kemiripan_pengganti: float = 0.7  # kata baru semirip ini dengan kata teks (dasar beda) = pengganti
    klaim_setia_kata_baru_maks: float = 0.34  # bagian kata isi baru (bukan berat) yang masih diterima
    # Bila klaim LLM tidak kosong tetapi ditolak (tidak setia atau memuat kata ganti kedua), heuristik hanya
    # dipakai pada skor sedikitnya ini: LLM menilai ada klaim, jadi kalimat yang kebetulan lolos tidak cukup.
    klaim_skor_setelah_tolak: float = 4.0
    # Bukti pernah_dibantah dipakai sebagai klaim bila sedikitnya sekian kata (potongan pendek seperti
    # "700 Kepala Desa" bukan klaim).
    klaim_bukti_min_kata: int = 4
    # Pengaman struktural untuk kutipan ciri dari LLM (pipeline/ciri.py).
    ciri_llm_min_kata: int = 3  # bukti ciri yang hanya ditemukan LLM; tidak berlaku untuk link_mencurigakan
    ciri_llm_kapital_rasio: float = 0.5  # bagian huruf kapital pada bukti kapital_tanda_seru
    ciri_llm_seru_min: int = 2  # atau sekian tanda seru
    # Nama profil ambang yang diterapkan (lihat PROFIL_AMBANG); hanya untuk banner dan log alat.
    profil_ambang: str = "lama"


# Profil ambang Sesi 5.6. "lama" = nilai bawaan dataclass di atas (perilaku commit 7742a73); "akhir" = hasil
# penyetelan set dev (D45) ditambah pemeriksaan kesetiaan klaim (T8c, tidak mengubah tingkat). Server memakai
# "akhir" kecuali CEKHOAKS_PROFIL_AMBANG=lama (cadangan demo). Alat evaluasi memakai tabel yang sama (--profil),
# jadi hasil evaluasi dan jalur server berasal dari konfigurasi yang sama.
PROFIL_AMBANG: dict[str, dict] = {
    "lama": {},
    "akhir": {
        "e5_maks_token_kueri": 512,
        "relevansi_toleransi_ocr": True,
        "kuat_kombinasi_aktif": True,
        "kuat_kombinasi_skor": 0.855,
        "kuat_kombinasi_relevansi": 0.70,
        "kuat_kombinasi_min_kata": 4,
        "relevansi_lolos_skor": 0.90,
        # 25 di penyetelan dev hanya menyaring obrolan pendek tanpa ciri; dikembalikan ke 20 supaya pesan penipuan
        # pendek (24 karakter, ditemukan di set uji) tetap dianalisis. Keputusan produk, lihat RANCANGAN §11.
        "ambang_teks_karakter": 20,
        "periksa_kesetiaan_klaim": True,
    },
}
PROFIL_AMBANG_BAWAAN = "akhir"

# Batas waktu Groq bila cadangan Gemini dimatikan: sisa anggaran yang biasanya untuk Gemini dipakai Groq (uji HP
# 2026-10-19: satu panggilan 3,5 detik, dekat batas 4). Tetap dibatasi llm_anggaran_total.
LLM_TIMEOUT_GROQ_SENDIRI = 7.0


def nilai_profil(nama: str) -> dict:
    """Semua bidang yang diatur profil mana pun, dengan nilai profil `nama` (bidang yang tidak disebut = bawaan)."""
    dasar = Pengaturan()
    bidang = {k for p in PROFIL_AMBANG.values() for k in p}
    return {k: PROFIL_AMBANG[nama].get(k, getattr(dasar, k)) for k in sorted(bidang)} | {"profil_ambang": nama}


def terapkan_profil_ambang(cfg: Pengaturan, nama: str) -> None:
    for k, v in nilai_profil(nama).items():
        setattr(cfg, k, v)


def _angka(env: Mapping[str, str], nama: str, tipe: type, bawaan):
    mentah = env.get(nama, "").strip()
    if not mentah:
        return bawaan
    try:
        nilai = tipe(mentah)
    except ValueError:
        raise KonfigurasiTidakValid(f"{nama} harus berupa angka, diterima: {mentah!r}") from None
    if nilai < 0:
        raise KonfigurasiTidakValid(f"{nama} tidak boleh negatif, diterima: {mentah!r}")
    return nilai


def muat(env: Mapping[str, str] = os.environ) -> Pengaturan:
    bawaan = Pengaturan()
    paksa = env.get("PAKSA_TINGKAT", "").strip()
    if paksa and paksa not in NILAI_PAKSA:
        raise KonfigurasiTidakValid(
            f"PAKSA_TINGKAT berisi nilai yang tidak dikenal: {paksa!r}. "
            f"Nilai yang sah: {', '.join(NILAI_PAKSA)} (atau kosong agar hasil bergiliran)."
        )
    sakelar = env.get("CEKHOAKS_CEKFAKTA", "").strip().lower()
    if sakelar not in ("", "aktif", "mati"):
        raise KonfigurasiTidakValid(f"CEKHOAKS_CEKFAKTA harus 'aktif' atau 'mati', diterima: {sakelar!r}")
    sakelar_llm = env.get("CEKHOAKS_LLM", "").strip().lower()
    if sakelar_llm not in ("", "aktif", "mati"):
        raise KonfigurasiTidakValid(f"CEKHOAKS_LLM harus 'aktif' atau 'mati', diterima: {sakelar_llm!r}")
    sakelar_cadangan = env.get("CEKHOAKS_LLM_CADANGAN", "").strip().lower()
    if sakelar_cadangan not in ("", "aktif", "mati"):
        raise KonfigurasiTidakValid(f"CEKHOAKS_LLM_CADANGAN harus 'aktif' atau 'mati', diterima: {sakelar_cadangan!r}")
    nama_profil = env.get("CEKHOAKS_PROFIL_AMBANG", "").strip().lower() or PROFIL_AMBANG_BAWAAN
    if nama_profil not in PROFIL_AMBANG:
        raise KonfigurasiTidakValid(
            f"CEKHOAKS_PROFIL_AMBANG harus {' atau '.join(repr(p) for p in PROFIL_AMBANG)}, diterima: {nama_profil!r}"
        )
    profil = nilai_profil(nama_profil)
    folder_cek = env.get("CEKHOAKS_CEKFAKTA_FOLDER", "").strip()
    folder_model = env.get("CEKHOAKS_MODEL_FOLDER", "").strip()
    pengaturan = Pengaturan(
        **{k: v for k, v in profil.items() if k != "ambang_teks_karakter"},
        cek_fakta_aktif=sakelar != "mati",
        llm_aktif=sakelar_llm != "mati",
        llm_cadangan_aktif=sakelar_cadangan != "mati",
        llm_timeout_groq=LLM_TIMEOUT_GROQ_SENDIRI if sakelar_cadangan == "mati" else bawaan.llm_timeout_groq,
        cek_fakta_folder=Path(folder_cek) if folder_cek else bawaan.cek_fakta_folder,
        model_folder=Path(folder_model) if folder_model else bawaan.model_folder,
        host=env.get("CEKHOAKS_HOST", "").strip() or bawaan.host,
        port=_angka(env, "CEKHOAKS_PORT", int, bawaan.port),
        batas_gambar_byte=_angka(env, "CEKHOAKS_BATAS_GAMBAR_BYTE", int, bawaan.batas_gambar_byte),
        jeda_min_detik=_angka(env, "CEKHOAKS_JEDA_MIN", float, bawaan.jeda_min_detik),
        jeda_maks_detik=_angka(env, "CEKHOAKS_JEDA_MAKS", float, bawaan.jeda_maks_detik),
        ambang_teks_karakter=_angka(env, "CEKHOAKS_AMBANG_TEKS", int, profil["ambang_teks_karakter"]),
        paksa_tingkat=paksa or None,
    )
    if pengaturan.jeda_min_detik > pengaturan.jeda_maks_detik:
        raise KonfigurasiTidakValid("CEKHOAKS_JEDA_MIN tidak boleh lebih besar dari CEKHOAKS_JEDA_MAKS")
    return pengaturan


# Dimuat saat modul pertama kali diimpor. Test mengubah field objek ini langsung.
# Pengaturan tidak sah tidak melempar saat impor: galatnya disimpan di `kesalahan`, dan pemanggil
# (python -m app, app.cek, lifespan server) wajib memeriksanya lebih dulu lalu menolak jalan.
kesalahan: KonfigurasiTidakValid | None = None
try:
    pengaturan = muat()
except KonfigurasiTidakValid as _e:
    kesalahan = _e
    pengaturan = Pengaturan()
