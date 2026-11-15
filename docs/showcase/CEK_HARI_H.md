# Daftar cek hari showcase (23 November)

Kerjakan berurutan. Semua perintah dijalankan di Windows PowerShell 5.1. Server dan ngrok masing-masing butuh jendela PowerShell sendiri yang dibiarkan terbuka sampai acara selesai.

Alamat publik: `https://skewer-bundle-viral.ngrok-free.dev` (D51). Link unduhan di QR: `https://github.com/jevonjustin/Venture-Hoax_Check/releases/latest/download/veritas.apk`.

## 1. Laptop: charger dan mode tidur

- [ ] Laptop tersambung ke charger (semua pengaturan di bawah hanya untuk mode charger/AC).
- [ ] Matikan tidur, hibernasi, layar mati otomatis, dan tidur saat layar ditutup (jalankan di jendela PowerShell biasa):

```powershell
powercfg /change standby-timeout-ac 0; powercfg /change hibernate-timeout-ac 0; powercfg /change monitor-timeout-ac 0; powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0; powercfg /setactive SCHEME_CURRENT
```

- [ ] Tunda pembaruan Windows supaya laptop tidak restart sendiri: Settings > Windows Update > **Pause updates** (1 minggu).

**Setelah acara, kembalikan ke nilai semula.** Nilai berikut dibaca dari laptop pada 2026-11-15 (skema Balanced): tidur di charger "tidak pernah", hibernasi di charger "tidak pernah", layar mati setelah 15 menit, tutup layar di charger = tidur.

```powershell
powercfg /change standby-timeout-ac 0; powercfg /change hibernate-timeout-ac 0; powercfg /change monitor-timeout-ac 15; powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1; powercfg /setactive SCHEME_CURRENT
```

Untuk memeriksa nilai sebelum mengubah (bila pengaturan sempat diganti sejak tanggal di atas): `powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE`, `powercfg /q SCHEME_CURRENT SUB_VIDEO VIDEOIDLE`, dan `powercfg /qh SCHEME_CURRENT SUB_BUTTONS LIDACTION` (baris "Current AC Power Setting Index"; layar dalam detik, heksadesimal: 0x384 = 900 detik = 15 menit).

## 2. Nyalakan server, lalu ngrok

- [ ] Laptop tersambung ke internet (Wi-Fi acara, atau hotspot HP bila Wi-Fi acara lemah).
- [ ] **Jendela 1, server** (tunggu sampai log menampilkan alamat dan "Analisis teks (LLM): groq saja (cadangan dimatikan)"; memuat pencarian cek fakta butuh beberapa detik):

```powershell
Set-Location C:\Users\User\AndroidStudioProjects\CekHoaks\server; $env:CEKHOAKS_LLM_CADANGAN = "mati"; .venv\Scripts\python.exe -m app
```

- [ ] **Jendela 2, ngrok** (`--inspect=false` wajib supaya isi permintaan tidak disimpan agen ngrok):

```powershell
& "C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000 --url https://skewer-bundle-viral.ngrok-free.dev --inspect=false
```

  Tampilan ngrok harus menunjukkan `Session Status  online` dan baris `Forwarding https://skewer-bundle-viral.ngrok-free.dev -> http://localhost:8000`.
- [ ] Di dashboard ngrok (https://dashboard.ngrok.com/settings#observability), Full Capture tetap **mati**.

## 3. Periksa /health lewat domain ngrok

- [ ] Jalankan di jendela PowerShell ketiga:

```powershell
try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 15 -Headers @{'ngrok-skip-browser-warning'='1'} https://skewer-bundle-viral.ngrok-free.dev/health; "OK $($r.StatusCode) $($r.Content)" } catch { $s = $_.Exception.Response; if ($s) { "GAGAL HTTP $([int]$s.StatusCode) $($s.Headers['Ngrok-Error-Code'])" } else { "GAGAL: $($_.Exception.Message)" } }
```

| Keluaran | Arti | Tindakan |
|---|---|---|
| `OK 200 {"status":"ok","versi":"0.7.0"}` | Server dan ngrok siap | Lanjut ke langkah 4 |
| `GAGAL HTTP 404 ERR_NGROK_3200` | ngrok tidak berjalan | Lihat jendela 2, jalankan ulang ngrok |
| `GAGAL HTTP 502 ERR_NGROK_8012` | ngrok berjalan, server mati | Lihat jendela 1, jalankan ulang server |
| `GAGAL: ...` tanpa kode HTTP | Laptop tidak tersambung internet | Lihat bagian 5, "Internet bermasalah" |

## 4. Siapkan HP demo

- [ ] HP terisi daya (bawa charger atau power bank) dan tersambung internet.
- [ ] Veritas yang terpasang versi 1.0.1: Settings > Apps > Veritas, versi di bagian bawah.
- [ ] Buka Veritas: izin tampil di atas aplikasi lain "Sudah diizinkan", lalu **Aktifkan tombol cek** dan pilih **Seluruh layar**.
- [ ] Cek satu gambar demo dari galeri sampai hasil muncul (gambar demo 1, `tidak_ditemukan`).
- [ ] Kecerahan layar tinggi dan layar tidak cepat mati (Settings > Display > Screen timeout, misalnya 10 menit).
- [ ] QR (`qr_veritas.png` atau `qr_veritas.svg`, cetak minimal 10 cm) dan kartu langkah di `RILIS.md` terpasang. Pindai QR sekali dengan HP lain dan pastikan unduhan `veritas.apk` dimulai.

## 5. Bila ada masalah

Kartu di HP pengunjung membantu menebak sumber masalah:

| Kartu di HP | Kemungkinan penyebab |
|---|---|
| Server tidak bisa dihubungi | Internet HP pengunjung, atau laptop putus dari internet |
| Server sedang tidak aktif | ngrok mati (`ERR_NGROK_3200`) atau server mati (`ERR_NGROK_8012`) |
| Server terlalu lama menjawab | Unggahan lambat (sinyal pengunjung lemah) atau laptop berat |
| Server sedang sibuk | Lebih dari 2 analisis bersamaan dan antrean lewat 20 detik; minta coba lagi |

### Server bermasalah (jendela 1 berhenti atau menampilkan galat)

1. Tekan `Ctrl+C` di jendela 1 bila masih berjalan, lalu jalankan ulang perintah server di langkah 2. ngrok tidak perlu dimatikan.
2. Ulangi pemeriksaan /health (langkah 3).
3. Bila Groq bermasalah (log menunjukkan galat Groq berulang, hasil di HP "pemeriksaan terbatas"), aplikasi tetap jalan dengan ciri dari regex. Untuk menghindari waktu tunggu Groq, jalankan ulang server dengan LLM dimatikan:

```powershell
Set-Location C:\Users\User\AndroidStudioProjects\CekHoaks\server; $env:CEKHOAKS_LLM = "mati"; .venv\Scripts\python.exe -m app
```

### ngrok bermasalah

1. Tekan `Ctrl+C` di jendela 2, jalankan ulang perintah ngrok di langkah 2, lalu ulangi /health.
2. Pesan `ERR_NGROK_334` (endpoint sudah dipakai): agen ngrok lain masih berjalan dengan domain yang sama. Tutup semua jendela ngrok atau jalankan `Stop-Process -Name ngrok`, lalu jalankan ulang.
3. Pesan galat autentikasi atau kuota: periksa https://dashboard.ngrok.com. Bila tidak bisa diperbaiki cepat, pakai cadangan mode lokal USB di bawah (hanya untuk HP demo; HP pengunjung tidak bisa dilayani).

### Internet bermasalah

- **Wi-Fi acara mati atau lemah:** sambungkan laptop ke hotspot HP demo. Server dan ngrok tidak perlu dijalankan ulang, karena ngrok menyambung kembali sendiri. Tunggu jendela 2 kembali `online`, lalu ulangi /health. Data yang dipakai laptop kecil (gambar dari pengunjung adalah data masuk, beberapa ratus KB per pengecekan).
- **Tidak ada internet sama sekali:** pengunjung tidak bisa dilayani. Pakai cadangan mode lokal USB di bawah untuk demo, dengan server yang dijalankan memakai `CEKHOAKS_LLM = "mati"`.

### Cadangan: mode lokal lewat USB (HP demo saja)

Build release menolak alamat `http://`, jadi mode ini memakai aplikasi **Veritas (debug)** (`com.example.cekhoaks.debug`), yang bisa terpasang berdampingan dengan versi release. Pasang sebelum hari H dan coba sekali.

1. Sambungkan HP demo ke laptop dengan kabel USB (USB debugging aktif).
2. Jalankan server di jendela 1 (perintah biasa di langkah 2, atau dengan `CEKHOAKS_LLM = "mati"` bila tanpa internet).
3. Teruskan port HP ke laptop (ulangi setiap kali kabel dicabut atau HP dimulai ulang):

```powershell
& "C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
```

4. Buka **Veritas (debug)** > Pengaturan server > **USB (adb reverse)** > **Uji koneksi**. Harus muncul "Tersambung. Versi server: 0.7.0".
5. Matikan tombol cek di Veritas release bila sedang aktif, lalu aktifkan tombol cek di Veritas (debug).

Bila Veritas (debug) belum terpasang, bangun dan pasang dari laptop:

```powershell
Set-Location C:\Users\User\AndroidStudioProjects\CekHoaks; $env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"; .\gradlew.bat installDebug
```

## 6. Setelah acara

- [ ] Matikan ngrok (`Ctrl+C` di jendela 2), lalu server (`Ctrl+C` di jendela 1).
- [ ] Kembalikan pengaturan daya (perintah di bagian 1) dan lanjutkan pembaruan Windows.
