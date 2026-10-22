# Server Veritas (pipeline analisis, Sesi 5.5)

Server FastAPI yang menerima potongan layar dari aplikasi dan mengembalikan hasil analisis sungguhan. Kontrak lengkapnya ada di [`docs/API.md`](../docs/API.md); rancangan dan keputusannya ada di [`docs/RANCANGAN_PROYEK.md`](../docs/RANCANGAN_PROYEK.md).

## Cara kerja

Urutan di `app/pipeline/orkestrator.py`, dipakai bersama oleh endpoint `/analisis` dan `python -m app.cek`:

1. **Baca** teks dari gambar dengan RapidOCR.
2. **Bersih**: teks antarmuka media sosial dibuang, tautan yang terpecah antar baris digabung.
3. **Ambang teks**: kurang dari 20 karakter huruf-angka menjadi galat `teks_tidak_terbaca`.
4. Tiga pekerjaan, dua di antaranya berjalan bersamaan:
   - **Pencarian cek fakta** (multilingual-e5-base lewat onnxruntime, tanpa PyTorch) memakai teks bersih.
   - **Model bahasa lewat API** (Groq, cadangan Gemini) memakai teks bersih yang nomor telepon, email, dan `@akun`-nya sudah disamarkan.
   - **Ciri regex**.
5. **Penggabungan ciri** (regex, LLM, dan pengaman struktural), **tingkat** (logika buatan sendiri, bukan LLM), **klaim utama**, dan **penjelasan dari template**.

LLM hanya mengusulkan klaim dan kandidat ciri beserta kutipan; kutipan diverifikasi terhadap teks. LLM tidak pernah menentukan tingkat dan tidak pernah menyatakan sesuatu benar atau salah.

- Gambar hanya dibaca di memori, tidak pernah ditulis ke disk dan tidak pernah dikirim ke pihak ketiga. Yang dikirim ke penyedia LLM hanya teks, setelah nomor telepon, email, dan `@akun` disamarkan. Nama orang dan isi pesan tidak disamarkan.
- Log hanya mencatat ukuran, dimensi, tingkat, durasi tiap tahap, serta (untuk LLM) nama penyedia, status HTTP, kode galat, jumlah token, dan durasi. Teks hasil baca, teks yang dikirim, balasan LLM, dan kunci API tidak pernah masuk log.
- Pemuatan RapidOCR dan model pencarian terjadi sekali saat server menyala (beberapa detik; RAM tambahan sekitar 1,5 GB untuk pencarian). Pembacaan dijalankan satu per satu di luar event loop, jadi beberapa HP sekaligus akan bergantian.
- Unggahan dibatasi 8 MB.

## Persiapan sekali saja

### Lingkungan Python

Butuh Python 3.12. Cek dengan `py -3.12 --version`. Semua perintah dijalankan dari folder `server`.

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server

# Buat lingkungan Python terpisah (venv) lalu pasang library
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

### Kunci API

Salin `.env.contoh` menjadi `.env` (berkas ini diabaikan git), lalu isi:

| Variabel | Fungsi |
|---|---|
| `GROQ_API_KEY` | Penyedia utama (`openai/gpt-oss-120b`) |
| `GEMINI_API_KEY` | Cadangan (`gemini-3.5-flash-lite`); boleh kosong |

Kunci dibaca dari variabel lingkungan lebih dulu, lalu `server\.env`. Tanpa kunci apa pun, server tetap jalan: ciri hanya dari regex dan `pemeriksaan_terbatas` berisi `"ai"`.

### Data lokal untuk pencarian cek fakta

Pencarian membutuhkan berkas berikut di `server\data_lokal\` (folder ini diabaikan git; cara membuatnya ada di [`alat/cek_fakta/README.md`](alat/cek_fakta/README.md)):

| Berkas | Isi |
|---|---|
| `cek_fakta\artikel.jsonl` | Database artikel cek fakta (21.342 artikel) |
| `cek_fakta\vektor_base_fp32.npy` dan `vektor_base_fp32.json` | Embedding seluruh artikel dan metadatanya; harus berasal dari `artikel.jsonl` yang sama |
| `model\e5-base\model.onnx` dan `tokenizer.json` | Model dan tokenizer e5-base |

Kalau ada yang hilang atau tidak cocok, server tetap menyala: pencarian ditandai tidak tersedia di banner, `cek_fakta` kosong, dan `pemeriksaan_terbatas` berisi `"cek_fakta"`.

## Menjalankan di Windows (PowerShell)

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server
.venv\Scripts\python -m app
```

Perintah di atas memanggil Python dari venv secara langsung, sehingga tidak perlu `Activate.ps1` (yang sering diblokir execution policy Windows).

Saat server mulai, pesan `Memuat pembaca teks ...` dan `Memuat pencarian cek fakta ...` tercetak lebih dulu. Setelah itu banner dan alamat yang bisa diketik di aplikasi:

```
============================================================
Server Veritas 0.6.0
Pencarian cek fakta: siap, 21.371 artikel (e5-base fp32), dimuat dalam 3,4 detik, RAM tambahan sekitar 1.472 MB
Analisis teks (LLM): groq -> gemini
Alamat yang bisa diketik di aplikasi:
  http://192.168.0.105:8000   <- Wi-Fi
  http://127.0.0.1:8000   <- lewat USB, setelah: adb reverse tcp:8000 tcp:8000
Tingkat hasil: dari analisis sungguhan (PAKSA_TINGKAT tidak diisi)
Ambang teks: minimal 20 karakter huruf-angka
============================================================
```

Baris `Analisis teks (LLM)` menunjukkan rantai penyedia yang kuncinya terisi: `groq -> gemini`, `groq saja (cadangan dimatikan)`, `dimatikan (CEKHOAKS_LLM=mati); ciri hanya dari regex`, atau `TIDAK TERSEDIA: ...`. Adaptor virtual (WSL, Hyper-V, Docker) disembunyikan dari daftar alamat. Pilih alamat dari jaringan yang juga dipakai HP.

Hentikan server dengan `Ctrl+C`.

## Sakelar dan pengaturan (variabel lingkungan)

Variabel hanya berlaku di jendela PowerShell tempat ia diisi dan dibaca saat server mulai. Nilai yang tidak sah membuat server menolak jalan dengan pesan yang menyebut nilai yang diterima (kode keluar 1).

```powershell
$env:CEKHOAKS_LLM = "mati"                 # contoh; hapus dengan: Remove-Item Env:CEKHOAKS_LLM
.venv\Scripts\python -m app
```

| Variabel | Bawaan | Fungsi |
|---|---|---|
| `CEKHOAKS_LLM` | `aktif` | `mati`: tidak memanggil API sama sekali (uji tanpa internet, cadangan demo). Ciri hanya dari regex, `pemeriksaan_terbatas` berisi `"ai"` |
| `CEKHOAKS_LLM_CADANGAN` | `aktif` | `mati`: hanya Groq, lalu tanpa LLM. Dipakai bila teks pasti tidak boleh dikirim ke Google. Bila Groq gagal, `pemeriksaan_terbatas` berisi `"ai"` |
| `CEKHOAKS_CEKFAKTA` | `aktif` | `mati`: tidak memuat dan tidak memakai pencarian cek fakta. `cek_fakta` kosong, `pemeriksaan_terbatas` berisi `"cek_fakta"`, dan RAM tambahan sekitar 1,5 GB tidak terpakai |
| `PAKSA_TINGKAT` | kosong | Memaksa hasil contoh (lihat di bawah) |
| `CEKHOAKS_CEKFAKTA_FOLDER`, `CEKHOAKS_MODEL_FOLDER` | `data_lokal\cek_fakta`, `data_lokal\model` | Lokasi data pencarian |
| `CEKHOAKS_HOST` | `0.0.0.0` | Antarmuka jaringan yang didengarkan |
| `CEKHOAKS_PORT` | `8000` | Port server |
| `CEKHOAKS_BATAS_GAMBAR_BYTE` | `8388608` | Ukuran gambar maksimal (8 MB) |
| `CEKHOAKS_JEDA_MIN`, `CEKHOAKS_JEDA_MAKS` | `0`, `0` | Rentang jeda buatan (detik), untuk menguji Batal; misalnya `3` dan `3` |
| `CEKHOAKS_AMBANG_TEKS` | `20` | Jumlah minimum karakter huruf-angka agar teks dianggap terbaca |

Angka lain (ambang skor, batas waktu LLM, dan seterusnya) ada di `app/konfigurasi.py`.

### Arti `pemeriksaan_terbatas`

Daftar di respons yang menyebut bagian pemeriksaan yang tidak berjalan pada permintaan itu:

| Nilai | Penyebab |
|---|---|
| `"cek_fakta"` | Pencarian dimatikan (`CEKHOAKS_CEKFAKTA=mati`), data atau model tidak tersedia, atau pencarian gagal |
| `"ai"` | LLM dimatikan, kunci kosong, atau semua penyedia gagal (429, batas waktu, laptop tanpa internet, balasan rusak atau terpotong) |

Daftar kosong berarti semuanya berjalan. Tingkat `tidak_ditemukan` dengan daftar tidak kosong **bukan** hasil pemeriksaan lengkap, dan aplikasi sebaiknya menyampaikannya begitu. Nama penyedia tidak pernah ada di respons.

### Rantai LLM dan batas kuota Groq

Groq `openai/gpt-oss-120b` → Gemini `gemini-3.5-flash-lite` → tanpa LLM. Batas waktu Groq 4 detik, Gemini 6 detik, total 9 detik. Setiap permintaan membawa `User-Agent: CekHoaks/<versi>`; tanpa itu Groq menolak dengan 403 `cf_1010`.

- **429:** bila waktu tunggu yang disarankan paling lama 3 detik dan anggaran waktu masih cukup, server menunggu lalu mencoba Groq sekali lagi. Selain itu langsung pindah penyedia (atau tanpa LLM bila cadangan dimatikan).
- **Kuota gratis Groq:** 8.000 token per menit per model. Satu permintaan memakai sekitar 1.100 token (maksimum terukur 1.528), jadi sekitar 7 permintaan per menit. Beberapa HP yang menganalisis berdekatan akan memicu 429. Pilihan untuk demo ada di catatan Tahap 8 di RANCANGAN.
- **Balasan terpotong** (`finish_reason: length`) dihitung gagal dan tidak diulang.
- Klaim kosong dari LLM tidak dicoba ulang; klaim diambil dari bukti `pernah_dibantah`, lalu heuristik.

### Teks tidak terbaca dan mode paksa (`PAKSA_TINGKAT`)

Kalau jumlah karakter huruf dan angka hasil baca (setelah pembersihan) di bawah ambang, server membalas galat `teks_tidak_terbaca` (422).

| `PAKSA_TINGKAT` atau `?paksa=` | OCR | Ambang teks | LLM dan pencarian | Hasil |
|---|---|---|---|---|
| kosong | berjalan | diperiksa | berjalan | analisis sungguhan |
| `kuat`, `hati_hati`, `tidak_ditemukan` | berjalan | dilewati | tidak berjalan | tingkat dan isi contoh sesuai nilai, `teks_terbaca` asli (bisa kosong), `pemeriksaan_terbatas` kosong |
| `teks_tidak_terbaca` | tidak berjalan | - | tidak berjalan | galat `teks_tidak_terbaca` langsung |

Mode paksa dipakai sebagai cadangan demo (misalnya tanpa internet sama sekali). Dari browser atau curl: `POST /analisis?paksa=hati_hati`; kalau variabel dan query sama-sama ada, query yang dipakai.

## Mencoba pipeline dari terminal

```powershell
.venv\Scripts\python -m app.cek C:\path\ke\gambar.png
```

`app.cek` menjalankan pipeline yang sama dengan endpoint (tanpa jeda buatan), mencetak JSON berformat respons API ke stdout, dan diagnostik ke stderr: teks mentah dan bersih, baris yang dibuang, ciri regex, kandidat artikel, percobaan LLM (penyedia, status, kode galat, token, durasi), klaim beserta sumbernya, bukti dan ciri yang dibuang, dan putusan tingkat. Kode keluar: 0 sukses, 1 galat API, 2 berkas tidak bisa dibaca. Memuat model memakan beberapa detik per perintah. Dengan `CEKHOAKS_LLM=mati` perintah ini tidak memanggil API.

## Alat uji 18 gambar

`alat\uji_analisis\tahap_b.py` menjalankan seluruh pipeline pada 18 screenshot uji, dengan atau tanpa LLM, lalu menulis tabel dan perbandingannya (lihat [`alat/uji_analisis/README.md`](alat/uji_analisis/README.md)):

```powershell
.venv\Scripts\python.exe alat\uji_analisis\tahap_b.py --tanpa-llm --nama tanpa_llm
.venv\Scripts\python.exe alat\uji_analisis\tahap_b.py --nama dengan_llm --acuan tanpa_llm.md   # memanggil API
```

## Test

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m pytest -m "not rapidocr"   # tanpa uji RapidOCR sungguhan (lebih cepat)
```

Test tidak memanggil jaringan dan tidak membaca kunci asli maupun `data_lokal`: pembaca teks, pencarian, dan transport LLM diganti tiruan (kecuali uji bertanda `rapidocr`, yang memakai RapidOCR sungguhan). Isinya: kontrak API, konfigurasi, tiap tahap pipeline, rantai LLM (urutan penyedia, 429, batas waktu, terpotong, privasi log), ujung ke ujung, dan `app.cek`.

Halaman dokumentasi interaktif tersedia di `http://127.0.0.1:8000/docs` selama server berjalan.

## Tiga cara menghubungkan HP ke laptop

Di aplikasi, buka bagian **Pengaturan server**, isi alamat, lalu tekan **Uji koneksi**. Hasilnya harus "Tersambung. Versi server: 0.6.0".

### 1. USB (`adb reverse`), paling stabil

HP tersambung dengan kabel USB dan USB debugging aktif. `adb reverse` meneruskan port 8000 di HP ke port 8000 di laptop, sehingga cara ini tidak bergantung pada jaringan atau firewall.

```powershell
adb reverse tcp:8000 tcp:8000
```

Kalau `adb` tidak dikenali, pakai path lengkapnya: `& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000`.

Di aplikasi, tekan **USB (adb reverse)** (alamatnya menjadi `http://127.0.0.1:8000`), lalu **Uji koneksi**. Perintah `adb reverse` perlu diulang setiap kali kabel dicabut atau HP dimulai ulang.

### 2. Wi-Fi yang sama

Laptop dan HP tersambung ke Wi-Fi yang sama. Ketik alamat `192.168.x.x` yang dicetak server.

Wi-Fi kampus atau Wi-Fi publik sering memblokir koneksi antarperangkat (fitur *client isolation*). Kalau Uji koneksi selalu gagal di Wi-Fi seperti itu, pakai cara 1 atau 3.

### 3. Hotspot dari HP

Nyalakan hotspot di HP, lalu sambungkan laptop ke hotspot itu. Jalankan server **setelah** laptop tersambung agar alamat barunya ikut tercetak. Alamatnya biasanya berawalan `10.`, `172.20.`, atau `192.168.`. Lalu ketik alamat itu di aplikasi.

Lalu lintas antara HP dan laptop tidak memakai kuota data. Cara ini direkomendasikan untuk showcase karena tidak bergantung pada Wi-Fi tempat acara.

## Windows Firewall

Saat server pertama kali dijalankan, Windows biasanya menanyakan apakah Python boleh diakses dari jaringan. Centang **Private networks**. Kalau pertanyaan itu terlewat, atau HP tetap tidak bisa terhubung lewat Wi-Fi atau hotspot (sementara USB berhasil):

1. Pastikan jaringan yang dipakai laptop berprofil **Private**, bukan Public. Buka Settings → Network & internet → Wi-Fi → (nama jaringan) → Network profile type → Private. Jaringan hotspot HP sering terdaftar sebagai Public.
2. Izinkan port 8000 untuk jaringan Private. Jalankan di PowerShell **sebagai Administrator**, cukup sekali:

   ```powershell
   New-NetFirewallRule -DisplayName "Cek Hoaks server (dev)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
   ```

   Untuk menghapusnya nanti: `Remove-NetFirewallRule -DisplayName "Cek Hoaks server (dev)"`.

Cara cepat memeriksa dari HP: buka `http://<alamat>:8000/health` di browser HP. Kalau muncul `{"status":"ok",...}`, jaringan dan firewall sudah benar.

## Catatan build aplikasi

Alamat `http://` (tanpa TLS) hanya diizinkan di **build debug**. Build release memblokirnya sesuai aturan Android. Jadi saat showcase, pakai build debug, atau pakai tunnel HTTPS (ngrok/Cloudflare Tunnel) kalau harus memakai build release.
