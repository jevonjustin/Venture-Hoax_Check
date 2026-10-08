# Server Cek Hoaks (pembaca teks RapidOCR, Sesi 5.2b)

Server FastAPI yang menerima potongan layar dari aplikasi dan mengembalikan hasil analisis. Tahap membaca teks (`app/pipeline/baca.py`) sudah memakai **RapidOCR** sungguhan; tahap lain di `app/pipeline/` (bersih, klaim, cocok, ciri, tingkat, template) masih dummy dan diganti satu per satu. Karena itu `teks_terbaca` berisi teks asli dari gambar, sedangkan klaim, ciri, cek fakta, dan tingkat masih contoh yang tidak berkaitan dengan isi gambar. Server ini dipakai untuk menguji jalur kirim-terima dan kartu di aplikasi. Kontrak lengkapnya ada di [`docs/API.md`](../docs/API.md).

- Gambar hanya dibaca di memori, tidak pernah ditulis ke disk. Log hanya mencatat ukuran, dimensi, tingkat, dan durasi.
- Teks hasil baca tidak pernah dicatat di log. Yang dicatat hanya durasi tiap tahap dan jumlah karakter.
- Jeda buatan bawaan 0 (waktu baca sungguhan sudah cukup lama, sekitar 1-2 detik). Pengaturannya tetap ada untuk menguji pembatalan (lihat tabel pengaturan).
- RapidOCR dimuat sekali saat server menyala, bersama satu pemanasan. Pesan `Pembaca teks siap (...), dimuat dalam X,X detik` tercetak sebelum alamat server, dan permintaan baru diterima sesudahnya. Pembacaan dijalankan satu per satu (antrean) di luar event loop, jadi beberapa HP sekaligus akan bergantian.
- Unggahan dibatasi 8 MB.

## Menjalankan di Windows (PowerShell)

Butuh Python 3.12. Cek dengan `py -3.12 --version`. Semua perintah dijalankan dari folder `server`.

```powershell
cd server

# Sekali saja: buat lingkungan Python terpisah (venv) lalu pasang library
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt

# Menjalankan server
.venv\Scripts\python -m app
```

Perintah di atas memanggil Python dari venv secara langsung, sehingga tidak perlu `Activate.ps1` (yang sering diblokir execution policy Windows).

Saat server mulai, pesan `Memuat pembaca teks ...` lalu `Pembaca teks siap (RapidOCR 3.9.2), dimuat dalam X,X detik` tercetak lebih dulu. Setelah itu alamat yang bisa diketik di aplikasi tercetak seperti ini:

```
============================================================
Server Cek Hoaks 0.5.0 (pembaca teks: RapidOCR, tahap lain masih dummy)
Alamat yang bisa diketik di aplikasi:
  http://172.17.32.1:8000
  http://192.168.0.105:8000
  http://127.0.0.1:8000   <- lewat USB, setelah: adb reverse tcp:8000 tcp:8000
Tingkat hasil: bergiliran (PAKSA_TINGKAT tidak diisi)
Ambang teks: minimal 20 karakter huruf-angka
============================================================
```

Tidak semua alamat bisa dipakai. Pilih yang berasal dari jaringan yang juga dipakai HP. Alamat dari adapter virtual (misalnya WSL atau Hyper-V, sering berawalan `172.17.` atau `172.2x.`) tidak bisa dijangkau dari HP.

Hentikan server dengan `Ctrl+C`.

### Teks tidak terbaca dan aturan `PAKSA_TINGKAT`

Kalau jumlah karakter huruf dan angka hasil baca di bawah ambang (bawaan 20, variabel `CEKHOAKS_AMBANG_TEKS`), server membalas galat `teks_tidak_terbaca` (422). Dasarnya pengukuran Sesi 5.2: gambar tanpa teks menghasilkan 0 karakter, dan teks sah terpendek di data uji 93 karakter.

| `PAKSA_TINGKAT` | OCR | Ambang teks | Hasil |
|---|---|---|---|
| kosong | berjalan | diperiksa | tingkat bergiliran (dummy), `teks_terbaca` asli; teks terlalu sedikit menjadi galat |
| `kuat`, `hati_hati`, `tidak_ditemukan` | berjalan | dilewati (mode demo) | tingkat dan isi dummy sesuai nilai, `teks_terbaca` asli (bisa kosong) |
| `teks_tidak_terbaca` | tidak berjalan | - | galat `teks_tidak_terbaca` langsung |

### Memaksa hasil tertentu

Tanpa pengaturan apa pun, hasil bergiliran `kuat` → `hati_hati` → `tidak_ditemukan`. Untuk menguji satu jenis kartu berulang kali, isi `PAKSA_TINGKAT` sebelum menjalankan server:

```powershell
$env:PAKSA_TINGKAT = "kuat"                # atau hati_hati, tidak_ditemukan, teks_tidak_terbaca
.venv\Scripts\python -m app

Remove-Item Env:PAKSA_TINGKAT              # kembali ke mode bergiliran
```

Variabel ini hanya berlaku di jendela PowerShell tempat ia diisi. Dari browser atau curl, hasil bisa juga dipaksa lewat query, misalnya `POST /analisis?paksa=hati_hati`.

Kalau `PAKSA_TINGKAT` berisi nilai yang tidak dikenal (misalnya salah ketik), server menolak jalan: pesan galat mencetak nilai yang diterima beserta daftar nilai sah, dan kode keluarnya 1. Nilai kosong berarti tidak dipaksa.

### Pengaturan lain (variabel lingkungan)

Semua pengaturan ada di `app/konfigurasi.py`. Nilai bawaan cocok untuk pemakaian biasa; variabel di bawah hanya perlu diisi kalau ingin menimpa.

| Variabel | Bawaan | Fungsi |
|---|---|---|
| `CEKHOAKS_HOST` | `0.0.0.0` | Antarmuka jaringan yang didengarkan |
| `CEKHOAKS_PORT` | `8000` | Port server |
| `CEKHOAKS_BATAS_GAMBAR_BYTE` | `8388608` | Ukuran gambar maksimal (8 MB) |
| `CEKHOAKS_JEDA_MIN`, `CEKHOAKS_JEDA_MAKS` | `0`, `0` | Rentang jeda buatan (detik), untuk menguji Batal; misalnya `3` dan `3` |
| `CEKHOAKS_AMBANG_TEKS` | `20` | Jumlah minimum karakter huruf-angka agar teks dianggap terbaca |
| `PAKSA_TINGKAT` | kosong | Memaksa hasil (lihat di atas) |

### Mencoba pipeline dari terminal

```powershell
$env:PAKSA_TINGKAT = "kuat"                # opsional
.venv\Scripts\python -m app.cek C:\path\ke\gambar.png
```

`app.cek` menjalankan pipeline yang sama dengan endpoint `/analisis` (tanpa jeda buatan), termasuk **pembacaan teks sungguhan** (pemuatan model sekitar beberapa detik tiap perintah; pesan memuat tercetak ke stderr) dan mencetak JSON berformat respons API, termasuk format galat seragam. Kode keluar: 0 sukses, 1 galat API, 2 berkas tidak bisa dibaca. Tanpa `PAKSA_TINGKAT`, hasilnya selalu `kuat`: giliran `kuat` → `hati_hati` → `tidak_ditemukan` hanya berjalan di dalam satu proses server, sedangkan tiap perintah `app.cek` adalah proses baru. Perilaku ini hilang setelah Sesi 5.5, saat hasil dummy diganti hasil analisis sungguhan.

### Test

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m pytest -m "not rapidocr"   # tanpa uji RapidOCR sungguhan (lebih cepat)
```

Test memakai `TestClient` FastAPI dengan gambar yang dibuat di memori. Bawaannya pembaca teks diganti pembaca palsu (cepat), kecuali uji bertanda `rapidocr` di `tests/test_rapidocr.py` yang memakai RapidOCR sungguhan. Isinya: kontrak API (bentuk respons, id ciri terkunci, semua kode galat), konfigurasi, pipeline (durasi tahap dicatat tanpa teks), dan `app.cek`.

### Folder `data_lokal/`

`server/data_lokal/` disiapkan untuk screenshot uji dan dataset mentah di sesi berikutnya. Isinya masuk `.gitignore`, jadi tidak pernah ikut repo.

Halaman dokumentasi interaktif tersedia di `http://127.0.0.1:8000/docs` selama server berjalan. Di halaman itu, `/analisis` bisa dicoba dengan mengunggah gambar dari browser.

## Tiga cara menghubungkan HP ke laptop

Di aplikasi, buka bagian **Pengaturan server**, isi alamat, lalu tekan **Uji koneksi**. Hasilnya harus "Tersambung. Versi server: 0.5.0".

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
