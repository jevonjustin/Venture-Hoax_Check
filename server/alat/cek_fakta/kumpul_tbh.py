"""Pengumpul artikel cek fakta dari turnbackhoax.id (Sesi 5.3).

Hanya menyimpan: judul, URL, tanggal terbit, label, kategori, dan cuplikan narasi (maks 500 karakter).
Isi penjelasan, gambar, dan komentar tidak disimpan. Hasilnya hanya untuk pencarian di laptop.

Aturan: satu permintaan dalam satu waktu, jeda minimal 1 detik, user-agent jelas tanpa data pribadi,
berhenti otomatis setelah 429/403 berulang, dan bisa dilanjutkan dari checkpoint.

Situs tidak punya sitemap. Alur: halaman daftar /articles?page=N (terbaru dulu, 10 artikel per halaman)
memberi URL dan tanggal, lalu tiap halaman artikel yang belum pernah diambil dibaca satu kali.
"""

import argparse
import atexit
import collections
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

import psutil
import requests
from bs4 import BeautifulSoup

from skema import FOLDER_DB, MAKS_NARASI, label_asli_dari_judul, rapikan, tanggal_iso

SITUS = "https://turnbackhoax.id"
USER_AGENT = "CekHoaksResearchBot/0.1 (proyek kuliah Venture Creation)"
JEDA_DETIK = 1.1                      # jeda setelah setiap respons (batas minimal 1 detik)
TIMEOUT = (10, 40)                    # (menyambung, membaca)
JEDA_ULANG = [30, 60, 120, 240, 480]  # menunggu saat jaringan putus atau server 5xx, lalu mencoba lagi
MAKS_DITOLAK_BERUNTUN = 3             # 429/403 berturut-turut sebelum berhenti
BATAS_TAHAP = {"1": "2024-11-01", "2": "2023-01-01", "3": "0001-01-01"}

KODE_KELUAR_SUKSES, KODE_KELUAR_BERHENTI, KODE_KELUAR_DITOLAK = 0, 3, 4
NAMA_SKRIP = "kumpul_tbh.py"
PERCOBAAN_TULIS = 5                   # coba lagi menulis berkas sementara saat PermissionError/OSError


class Berhenti(Exception):
    """Pengumpulan berhenti dengan rapi; checkpoint sudah tersimpan."""


class Pengambil:
    def __init__(self, folder: Path):
        self.sesi = requests.Session()
        self.sesi.headers["User-Agent"] = USER_AGENT
        self.folder = folder
        self.stop_file = folder / "BERHENTI"
        self.terakhir = 0.0
        self.ditolak = 0
        self.byte_total = 0
        self.permintaan = 0

    def ambil(self, url: str, params=None) -> requests.Response | None:
        """GET dengan jeda, coba ulang saat jaringan bermasalah. None untuk 404. Melempar Berhenti jika harus berhenti."""
        percobaan = 0
        while True:
            if self.stop_file.exists():
                raise Berhenti("berkas BERHENTI ditemukan")
            tunggu = JEDA_DETIK - (time.monotonic() - self.terakhir)
            if tunggu > 0:
                time.sleep(tunggu)
            try:
                r = self.sesi.get(url, params=params, timeout=TIMEOUT)
            except (requests.ConnectionError, requests.Timeout) as e:
                self.terakhir = time.monotonic()
                r = None
                alasan = f"jaringan: {type(e).__name__}"
            else:
                self.terakhir = time.monotonic()
                self.permintaan += 1
                # ukuran setelah dekompresi; yang lewat jaringan (gzip) kira-kira seperlimanya
                self.byte_total += len(r.content)
                alasan = f"HTTP {r.status_code}"
                if r.status_code == 200:
                    self.ditolak = 0
                    return r
                if r.status_code == 404:
                    self.ditolak = 0
                    return None
                if r.status_code in (429, 403):
                    self.ditolak += 1
                    if self.ditolak >= MAKS_DITOLAK_BERUNTUN:
                        raise Berhenti(f"{r.status_code} berulang {self.ditolak} kali; situs meminta berhenti")
                    jeda = min(int(r.headers.get("Retry-After", 60) or 60), 300)
                    cetak(f"{alasan}; menunggu {jeda} detik ({self.ditolak}/{MAKS_DITOLAK_BERUNTUN})")
                    time.sleep(jeda)
                    continue
            if percobaan >= len(JEDA_ULANG):
                raise Berhenti(f"gagal {percobaan + 1} kali berturut-turut ({alasan}) pada {url}")
            jeda = JEDA_ULANG[percobaan]
            percobaan += 1
            cetak(f"{alasan}; menunggu {jeda} detik lalu mencoba lagi ({percobaan}/{len(JEDA_ULANG)})")
            self._tidur(jeda)

    def _tidur(self, detik: int):
        for _ in range(detik):
            if self.stop_file.exists():
                raise Berhenti("berkas BERHENTI ditemukan")
            time.sleep(1)


_BERKAS_LOG: Path | None = None


def cetak(pesan: str):
    """Cetak ke layar dan tambahkan ke tbh_log.txt (UTF-8) supaya bisa dipantau dari jendela PowerShell lain."""
    baris = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {pesan}"
    print(baris, flush=True)
    if _BERKAS_LOG is not None:
        try:
            with open(_BERKAS_LOG, "a", encoding="utf-8") as f:
                f.write(baris + "\n")
        except OSError:
            pass  # gagal menulis log tidak boleh menghentikan pengumpulan


def tulis_aman(jalur: Path, teks: str) -> bool:
    """Menulis lewat berkas sementara bernama unik (memuat PID) lalu os.replace. Mencoba lagi beberapa kali kalau
    PermissionError atau OSError lain (misalnya berkas sedang dibaca pihak lain). Tidak pernah melempar galat:
    kalau tetap gagal, mencatat peringatan dan mengembalikan False."""
    sementara = jalur.with_name(f"{jalur.name}.{os.getpid()}.tmp")
    galat: OSError | None = None
    for percobaan in range(PERCOBAAN_TULIS):
        try:
            sementara.write_text(teks, encoding="utf-8")
            os.replace(sementara, jalur)
            return True
        except OSError as e:
            galat = e
            time.sleep(0.2 * (percobaan + 1))
    try:
        sementara.unlink(missing_ok=True)
    except OSError:
        pass
    cetak(f"PERINGATAN: gagal menulis {jalur.name} setelah {PERCOBAAN_TULIS} percobaan "
          f"({type(galat).__name__}: {galat}); dilewati, pengumpulan tetap berjalan")
    return False


def _perintah_pengumpul(proses: psutil.Process) -> bool:
    try:
        return any(os.path.basename(a) == NAMA_SKRIP for a in proses.cmdline())
    except (psutil.Error, OSError):
        return False


def proses_pengumpul_lain() -> list[int]:
    """PID proses lain yang menjalankan kumpul_tbh.py, di folder mana pun. Proses ini sendiri dan induknya (launcher venv
    Windows) tidak dihitung. Dengan begitu pengumpul versi lama (tanpa berkas kunci) pun terdeteksi."""
    saya = psutil.Process()
    sendiri = {saya.pid}
    sendiri |= {p.pid for p in saya.parents()}
    return sorted(p.pid for p in psutil.process_iter() if p.pid not in sendiri and _perintah_pengumpul(p))


def pengumpul_aktif(pid: int) -> bool:
    try:
        return psutil.pid_exists(pid) and _perintah_pengumpul(psutil.Process(pid))
    except psutil.Error:
        return False


class Ditolak(Exception):
    """Pengumpul lain sedang berjalan."""


class Kunci:
    """Berkas kunci berisi PID di folder data. Dibuat dengan O_EXCL sehingga dua proses tidak bisa memilikinya bersamaan.
    Kunci basi (PID sudah tidak ada atau bukan pengumpul) diambil alih dengan peringatan."""

    def __init__(self, folder: Path):
        self.jalur = folder / "tbh.lock"
        self.dimiliki = False

    def ambil(self):
        lain = proses_pengumpul_lain()
        if lain:
            raise Ditolak(f"Pengumpul lain sedang berjalan (PID {', '.join(map(str, lain))}). "
                          "Hanya satu pengumpul boleh berjalan dalam satu waktu. Tunggu sampai selesai, atau hentikan yang "
                          "berjalan dengan Ctrl+C di jendelanya, atau dengan membuat berkas BERHENTI di folder datanya.")
        for _ in range(3):
            try:
                fd = os.open(self.jalur, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    pid = int(self.jalur.read_text(encoding="utf-8").strip())
                except (OSError, ValueError):
                    pid = 0
                if pid and pid != os.getpid() and pengumpul_aktif(pid):
                    raise Ditolak(f"Berkas kunci {self.jalur} dipegang pengumpul yang masih berjalan (PID {pid}).")
                cetak(f"PERINGATAN: kunci basi (PID {pid or 'tidak terbaca'} sudah tidak berjalan); kunci diambil alih")
                try:
                    self.jalur.unlink()
                except OSError:
                    time.sleep(0.3)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            self.dimiliki = True
            atexit.register(self.lepas)
            return
        raise Ditolak(f"Tidak bisa mengambil berkas kunci {self.jalur}.")

    def lepas(self):
        if not self.dimiliki:
            return
        self.dimiliki = False
        try:
            if int(self.jalur.read_text(encoding="utf-8").strip()) == os.getpid():
                self.jalur.unlink()
        except (OSError, ValueError):
            pass


def baca_daftar(html: str) -> list[dict]:
    """Daftar artikel di halaman /articles: url, tanggal ISO, judul."""
    sup = BeautifulSoup(html, "html.parser")
    hasil, terlihat = [], set()
    for kartu in sup.select("div.news-card-h-alt"):
        a = kartu.find("a", href=re.compile(r"/articles/\d+-"))
        if not a or a["href"] in terlihat:
            continue
        terlihat.add(a["href"])
        waktu = kartu.find("span", string=re.compile(r"^\d{2}/\d{2}/\d{4}$"))
        img = kartu.find("img")
        hasil.append({
            "url": a["href"] if a["href"].startswith("http") else SITUS + a["href"],
            "tanggal": tanggal_iso(waktu.get_text(strip=True)) if waktu else None,
            "judul": (img.get("alt") if img else "") or "",
        })
    return hasil


_BLOK = ["p", "blockquote", "li"]


def teks_blok(isi) -> str:
    """Teks per blok (p, blockquote, li) tanpa blok bersarang; sisipan inline (span, a) tidak dipecah.
    Penanda '[ arsip ]' dibuang karena hanya tautan arsip."""
    blok = [e.get_text("") for e in isi.find_all(_BLOK) if not e.find(_BLOK)]
    teks = "\n".join(b.strip() for b in blok if b.strip()) or isi.get_text(" ")
    return re.sub(r"\[\s*arsip[^\]]*\]", "", teks, flags=re.I)


def baca_artikel(html: str, url: str) -> dict | None:
    """Mengambil judul, tanggal, kategori, hasil periksa fakta, dan cuplikan narasi. Isi penjelasan dibuang."""
    sup = BeautifulSoup(html, "html.parser")
    h1 = sup.find("h1")
    if not h1:
        return None
    judul = h1.get_text(" ", strip=True)
    artikel = sup.find("article")
    if artikel is None:
        return None
    waktu = artikel.find("time")
    tanggal = tanggal_iso(waktu.get("datetime") or waktu.get_text(strip=True)) if waktu else None
    kat = artikel.find("a", href=re.compile(r"category="))
    narasi, hasil = "", ""
    for bagian in artikel.find_all("section"):
        judul_bagian = bagian.find("strong")
        if not judul_bagian or bagian.find("section"):
            continue
        nama = judul_bagian.get_text(strip=True).lower()
        if nama == "narasi" and not narasi:
            isi = bagian.find("div")
            narasi = rapikan(teks_blok(isi)) if isi else ""
        elif nama.startswith("hasil periksa fakta") and not hasil:
            kuat = bagian.find("div").find("strong") if bagian.find("div") else None
            hasil = kuat.get_text(strip=True) if kuat else ""
    m = re.search(r"/articles/(\d+)-", url)
    return {
        "id_situs": int(m.group(1)) if m else None,
        "judul": judul,
        "url": url,
        "tanggal": tanggal,
        "label_asli": label_asli_dari_judul(judul),
        "hasil_periksa": hasil,
        "kategori": kat.get_text(strip=True) if kat else "",
        "narasi": narasi[: MAKS_NARASI + 1],
        "diambil": datetime.datetime.now().isoformat(timespec="seconds"),
    }


class Penyimpan:
    """Satu baris JSON per artikel (ditulis dan di-flush seketika) ditambah checkpoint halaman."""

    def __init__(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        self.jalur = folder / "tbh_artikel.jsonl"
        self.ckpt = folder / "tbh_checkpoint.json"
        self.status = folder / "tbh_status.json"
        self.sudah: set[str] = set()
        self.per_tahun: collections.Counter = collections.Counter()
        if self.jalur.exists():
            for baris in self.jalur.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(baris)
                except json.JSONDecodeError:
                    continue  # baris terakhir bisa terpotong kalau proses dimatikan paksa
                if d.get("galat"):
                    continue  # halaman yang gagal dibaca dicoba lagi pada jalan berikutnya
                self.sudah.add(d["url"])
                self.per_tahun[(d.get("tanggal") or "????")[:4]] += 1
        self.f = open(self.jalur, "a", encoding="utf-8", newline="\n")

    def tambah(self, d: dict):
        try:
            self.f.write(json.dumps(d, ensure_ascii=False) + "\n")
            self.f.flush()
        except OSError as e:
            raise Berhenti(f"gagal menulis tbh_artikel.jsonl ({type(e).__name__}: {e})") from e
        self.sudah.add(d["url"])
        self.per_tahun[(d.get("tanggal") or "????")[:4]] += 1

    def muat_ckpt(self) -> dict:
        try:
            return json.loads(self.ckpt.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def simpan_ckpt(self, data: dict):
        tulis_aman(self.ckpt, json.dumps(data, ensure_ascii=False, indent=1))

    def tulis_status(self, ekstra: dict):
        data = {"jumlah": len(self.sudah), "per_tahun": dict(sorted(self.per_tahun.items())),
                "diperbarui": datetime.datetime.now().isoformat(timespec="seconds"), **ekstra}
        tulis_aman(self.status, json.dumps(data, ensure_ascii=False, indent=1))

    def tutup(self):
        self.f.close()


def jalankan(mode: str, sampai: str, folder: Path, maks_artikel: int | None, mulai_halaman: int | None) -> int:
    global _BERKAS_LOG
    folder.mkdir(parents=True, exist_ok=True)
    _BERKAS_LOG = folder / "tbh_log.txt"
    kunci = Kunci(folder)
    try:
        kunci.ambil()
    except Ditolak as e:
        print(f"DITOLAK: {e}", file=sys.stderr, flush=True)
        return KODE_KELUAR_DITOLAK
    try:
        return _jalankan_terkunci(mode, sampai, folder, maks_artikel, mulai_halaman)
    finally:
        kunci.lepas()


def _jalankan_terkunci(mode: str, sampai: str, folder: Path, maks_artikel: int | None, mulai_halaman: int | None) -> int:
    pengambil = Pengambil(folder)
    simpan = Penyimpan(folder)
    ckpt = simpan.muat_ckpt()
    # mode lengkap melanjutkan dari halaman di checkpoint; mode pembaruan selalu mulai dari halaman 1
    halaman = mulai_halaman or (ckpt.get("halaman_berikut", 1) if mode == "lengkap" else 1)
    baru = 0
    awal = time.monotonic()
    cetak(f"Mulai mode={mode}, sampai={sampai}, halaman={halaman}, sudah ada {len(simpan.sudah)} artikel")
    try:
        while True:
            r = pengambil.ambil(f"{SITUS}/articles", params={"page": halaman})
            daftar = baca_daftar(r.text) if r is not None else []
            if not daftar:
                cetak(f"Halaman {halaman} kosong; daftar artikel habis.")
                simpan.simpan_ckpt({"halaman_berikut": halaman, "selesai": True})
                break
            baru_di_halaman = 0
            terlalu_lama = [i for i in daftar if i["tanggal"] and i["tanggal"] < sampai]
            if len(terlalu_lama) == len(daftar):
                cetak(f"Seluruh halaman {halaman} lebih lama dari {sampai}; selesai.")
                simpan.simpan_ckpt({"halaman_berikut": halaman, "selesai": False})
                return KODE_KELUAR_SUKSES
            for item in daftar:
                if item["tanggal"] and item["tanggal"] < sampai:
                    continue
                if item["url"] in simpan.sudah:
                    continue
                if maks_artikel is not None and baru >= maks_artikel:
                    cetak(f"Batas {maks_artikel} artikel tercapai.")
                    return KODE_KELUAR_SUKSES
                ra = pengambil.ambil(item["url"])
                data = baca_artikel(ra.text, item["url"]) if ra is not None else None
                if data is None and ra is not None:  # respons 200 tetapi tidak bisa dibaca: coba sekali lagi
                    ra = pengambil.ambil(item["url"])
                    data = baca_artikel(ra.text, item["url"]) if ra is not None else None
                if data is None:
                    cetak(f"Dilewati (404 atau tak terbaca): {item['url']}")
                    data = {"id_situs": None, "judul": item["judul"], "url": item["url"], "tanggal": item["tanggal"],
                            "label_asli": label_asli_dari_judul(item["judul"]), "hasil_periksa": "", "kategori": "",
                            "narasi": "", "diambil": datetime.datetime.now().isoformat(timespec="seconds"),
                            "galat": "tak_terbaca"}
                elif not data["tanggal"]:
                    data["tanggal"] = item["tanggal"]
                simpan.tambah(data)
                baru += 1
                baru_di_halaman += 1
            halaman += 1
            simpan.simpan_ckpt({"halaman_berikut": halaman, "selesai": False})
            if mode == "pembaruan" and baru_di_halaman == 0:
                cetak("Satu halaman penuh tidak berisi artikel baru; pembaruan selesai.")
                break
            lama = time.monotonic() - awal
            simpan.tulis_status({"mode": mode, "sampai": sampai, "halaman_berikut": halaman, "baru_sesi_ini": baru,
                                 "permintaan": pengambil.permintaan, "megabyte_setelah_dekompresi": round(pengambil.byte_total / 1e6, 1),
                                 "detik_berjalan": int(lama)})
            if halaman % 5 == 0 or baru_di_halaman:
                cetak(f"halaman berikut {halaman} | baru {baru} | total {len(simpan.sudah)} | "
                      f"{pengambil.byte_total / 1e6:.1f} MB | {lama / 60:.1f} menit | tahun terbaru: {tahun_ringkas(simpan.per_tahun)}")
        return KODE_KELUAR_SUKSES
    except Berhenti as e:
        cetak(f"BERHENTI: {e}")
        simpan.simpan_ckpt({"halaman_berikut": halaman, "selesai": False, "berhenti_karena": str(e)})
        cetak("Checkpoint tersimpan. Untuk melanjutkan, jalankan ulang perintah yang sama "
              "(setelah menghapus berkas BERHENTI jika ada).")
        return KODE_KELUAR_BERHENTI
    except KeyboardInterrupt:
        cetak("Dihentikan dengan Ctrl+C. Checkpoint tersimpan; jalankan ulang perintah yang sama untuk melanjutkan.")
        simpan.simpan_ckpt({"halaman_berikut": halaman, "selesai": False, "berhenti_karena": "Ctrl+C"})
        return KODE_KELUAR_BERHENTI
    finally:
        simpan.tulis_status({"mode": mode, "sampai": sampai, "halaman_berikut": halaman, "baru_sesi_ini": baru,
                             "permintaan": pengambil.permintaan, "megabyte_setelah_dekompresi": round(pengambil.byte_total / 1e6, 1)})
        simpan.tutup()
        cetak("Per tahun: " + ", ".join(f"{t}={n}" for t, n in sorted(simpan.per_tahun.items())))


def tahun_ringkas(c: collections.Counter) -> str:
    return " ".join(f"{t}:{n}" for t, n in sorted(c.items())[-3:])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Pengumpul artikel turnbackhoax.id")
    p.add_argument("mode", choices=["lengkap", "pembaruan"],
                   help="lengkap: terbaru dulu lalu mundur, lanjut dari checkpoint. pembaruan: hanya artikel baru.")
    p.add_argument("--tahap", choices=list(BATAS_TAHAP), help="1: sejak 2024-11-01, 2: sejak 2023-01-01, 3: semua")
    p.add_argument("--sampai", help="berhenti saat artikel lebih lama dari tanggal ini (YYYY-MM-DD)")
    p.add_argument("--folder", type=Path, default=FOLDER_DB, help="folder keluaran (bawaan: data_lokal/cek_fakta)")
    p.add_argument("--maks-artikel", type=int, help="batasi jumlah artikel baru (untuk uji kecil)")
    p.add_argument("--halaman", type=int, help="mulai dari halaman ini (mengabaikan checkpoint)")
    a = p.parse_args()
    sampai = a.sampai or (BATAS_TAHAP[a.tahap] if a.tahap else "0001-01-01")
    sys.exit(jalankan(a.mode, sampai, a.folder, a.maks_artikel, a.halaman))


if __name__ == "__main__":
    main()
