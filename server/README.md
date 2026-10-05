# Server Cek Hoaks (dummy, tahap 4)

Server FastAPI yang menerima potongan layar dari aplikasi dan mengembalikan hasil analisis **contoh**. Belum ada model maupun OCR. Server ini dipakai untuk menguji jalur kirim-terima dan kartu di aplikasi. Kontrak lengkapnya ada di [`docs/API.md`](../docs/API.md).

- Gambar hanya dibaca di memori, tidak pernah ditulis ke disk. Log hanya mencatat ukuran, dimensi, tingkat, dan durasi.
- Ada jeda buatan 1-3 detik supaya kartu "Sedang menganalisis…" sempat terlihat.
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

Saat server mulai, alamat yang bisa diketik di aplikasi tercetak seperti ini:

```
============================================================
Server dummy Cek Hoaks 0.4.0
Alamat yang bisa diketik di aplikasi:
  http://172.17.32.1:8000
  http://192.168.0.105:8000
  http://127.0.0.1:8000   <- lewat USB, setelah: adb reverse tcp:8000 tcp:8000
Tingkat hasil: bergiliran (PAKSA_TINGKAT tidak diisi)
============================================================
```

Tidak semua alamat bisa dipakai. Pilih yang berasal dari jaringan yang juga dipakai HP. Alamat dari adapter virtual (misalnya WSL atau Hyper-V, sering berawalan `172.17.` atau `172.2x.`) tidak bisa dijangkau dari HP.

Hentikan server dengan `Ctrl+C`.

### Memaksa hasil tertentu

Tanpa pengaturan apa pun, hasil bergiliran `kuat` → `hati_hati` → `tidak_ditemukan`. Untuk menguji satu jenis kartu berulang kali, isi `PAKSA_TINGKAT` sebelum menjalankan server:

```powershell
$env:PAKSA_TINGKAT = "kuat"                # atau hati_hati, tidak_ditemukan, teks_tidak_terbaca
.venv\Scripts\python -m app

Remove-Item Env:PAKSA_TINGKAT              # kembali ke mode bergiliran
```

Variabel ini hanya berlaku di jendela PowerShell tempat ia diisi. Dari browser atau curl, hasil bisa juga dipaksa lewat query, misalnya `POST /analisis?paksa=hati_hati`.

### Test

```powershell
.venv\Scripts\python -m pytest
```

Halaman dokumentasi interaktif tersedia di `http://127.0.0.1:8000/docs` selama server berjalan. Di halaman itu, `/analisis` bisa dicoba dengan mengunggah gambar dari browser.

## Tiga cara menghubungkan HP ke laptop

Di aplikasi, buka bagian **Pengaturan server**, isi alamat, lalu tekan **Uji koneksi**. Hasilnya harus "Tersambung. Versi server: 0.4.0".

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
