# Alat database cek fakta (Sesi 5.3)

Membangun database artikel cek fakta lokal dan mencari artikel yang mirip dengan sebuah klaim. Alat ini belum terpasang ke `/analisis` (pemasangan dikerjakan di Sesi 5.5). Hasil perbandingan model, keputusan, dan keterbatasan ada di `docs/RANCANGAN_PROYEK.md` (bagian Sesi 5.3).

Semua data ada di `server/data_lokal/` (masuk `.gitignore`, tidak ikut repo):

| Lokasi | Isi |
|---|---|
| `dataset_mentah/kaggle_*` | Tiga dataset Kaggle apa adanya |
| `cek_fakta/tbh_artikel.jsonl` | Hasil pengumpulan turnbackhoax.id (satu baris JSON per artikel) |
| `cek_fakta/tbh_checkpoint.json`, `tbh_status.json`, `tbh_log.txt` | Checkpoint, status terakhir, dan log pengumpul |
| `cek_fakta/artikel.jsonl` | Database gabungan (keluaran `bangun.py`) |
| `cek_fakta/laporan_gabung.txt` | Jumlah per sumber, label, tahun, dan cakupan narasi |
| `cek_fakta/vektor_UKURAN_VARIAN.npy` (+ `.json`) | Embedding seluruh artikel |
| `cek_fakta/uji/` | Data uji pencarian dan `hasil_*.json` |
| `model/e5-small`, `model/e5-base` | Model ONNX dan tokenizer |

## Menyiapkan lingkungan

Butuh Python 3.12. Semua perintah dijalankan dari folder `server\alat\cek_fakta`. Lingkungan Python ada di `server\.venv-cekfakta` (terpisah dari `.venv` milik server).

```powershell
cd server
py -3.12 -m venv .venv-cekfakta
.venv-cekfakta\Scripts\python -m pip install -r alat\cek_fakta\requirements.txt
cd alat\cek_fakta

# Mengunduh model (small sekitar 0,5 GB, base sekitar 1,1 GB; tambahkan --varian fp32 int8 untuk model int8)
..\..\.venv-cekfakta\Scripts\python unduh_model.py --ukuran small base
```

## Membangun ulang database (satu perintah)

```powershell
..\..\.venv-cekfakta\Scripts\python bangun.py
..\..\.venv-cekfakta\Scripts\python evaluasi.py vektor --ukuran base --varian fp32
```

`bangun.py` membaca ketiga dataset Kaggle dan `tbh_artikel.jsonl` (kalau ada), membuang duplikat, lalu menulis `artikel.jsonl` dan `laporan_gabung.txt`. Vektor harus dibangun ulang hanya kalau id, judul, narasi, atau urutan artikel berubah: kecocokan diperiksa lewat `teks_sha1` (id dan teks yang di-embed, sesuai urutan) di berkas `vektor_*.json`, sehingga perubahan label, URL, atau field lain tidak membatalkan vektor. `cari.py` menolak vektor yang tidak cocok.

Label: dari awalan judul; untuk judul tanpa label atau berlabel `ISU`, dilengkapi dari "Hasil Periksa Fakta" halaman situs (Salah atau False: `salah`; Klarifikasi, Clarification, Benar, atau True: `klarifikasi`; lainnya tetap `lainnya`). Rinciannya ada di `docs/RANCANGAN_PROYEK.md` (Sesi 5.3).

## Pengumpulan dari turnbackhoax.id

Aturan: satu permintaan dalam satu waktu, jeda minimal 1 detik, user-agent `CekHoaksResearchBot/0.1`, berhenti otomatis setelah 429 atau 403 berulang, dan menunggu lalu mencoba lagi (30, 60, 120, 240, 480 detik) kalau jaringan putus sebelum berhenti dengan rapi. Yang disimpan hanya judul, URL, tanggal, label, kategori, dan cuplikan narasi (maksimal 500 karakter).

```powershell
# Tahap 1: sejak 2024-11-01. Tahap 2: sejak 2023-01-01. Tahap 3: semua.
..\..\.venv-cekfakta\Scripts\python kumpul_tbh.py lengkap --tahap 1

# Pembaruan: hanya artikel baru (untuk dijalankan lagi menjelang showcase)
..\..\.venv-cekfakta\Scripts\python kumpul_tbh.py pembaruan
```

- **Hanya satu pengumpul sekaligus:** pengumpul membuat berkas kunci `tbh.lock` (berisi PID) di folder datanya dan memeriksa apakah ada proses lain yang menjalankan `kumpul_tbh.py`. Pengumpul kedua menolak jalan dengan pesan `DITOLAK` dan kode keluar 4. Kunci basi (prosesnya sudah tidak ada) diambil alih otomatis dengan peringatan. Jangan menghapus `tbh.lock` secara manual selagi pengumpul berjalan.
- **Tahan galat tulis:** berkas status dan checkpoint ditulis lewat berkas sementara bernama unik; kalau `PermissionError` atau `OSError` lain terjadi, penulisan dicoba lagi lima kali, lalu dicatat sebagai `PERINGATAN` dan pengumpulan tetap berjalan.
- **Memantau:** `Get-Content ..\..\data_lokal\cek_fakta\tbh_log.txt -Wait -Tail 20 -Encoding UTF8` di jendela lain. Ringkasan jumlah per tahun ada di `tbh_status.json`.
- **Menghentikan dengan aman:** buat berkas `BERHENTI` (`New-Item ..\..\data_lokal\cek_fakta\BERHENTI`), atau tekan `Ctrl+C`. Hapus berkas itu sebelum melanjutkan.
- **Melanjutkan:** jalankan perintah yang sama; pengumpul membaca `tbh_checkpoint.json` dan melewati artikel yang sudah ada.
- **Uji kecil:** tambahkan `--folder PATH_SAMPEL --maks-artikel 5`.

## Mencari

```powershell
..\..\.venv-cekfakta\Scripts\python cari.py "Air keran di Jakarta mengandung zat berbahaya"
..\..\.venv-cekfakta\Scripts\python cari.py --gambar C:\path\ke\gambar.png
```

Keluaran: lima artikel teratas dengan skor, label, sumber, tanggal, dan URL (artikel yang hanya punya URL format lama diberi penanda). Bawaan: e5-base fp32. Opsi `--ukuran small|base`, `--varian fp32|int8`, `--top N`.

## Evaluasi dan perbandingan model

```powershell
..\..\.venv-cekfakta\Scripts\python evaluasi.py ukur --ukuran small --varian fp32 --ulang
..\..\.venv-cekfakta\Scripts\python evaluasi.py ukur --ukuran base --varian fp32 --ulang
..\..\.venv-cekfakta\Scripts\python evaluasi.py ringkas
```

Data uji (di `data_lokal\cek_fakta\uji`): teks OCR screenshot 09 sampai 15 (`siapkan-ocr`), 50 parafrase pesan berantai (`parafrase.json`, ditulis manual dari `sampel-parafrase`), dan 30 kueri negatif (`negatif.json`: 20 kalimat berita CNN, Kompas, dan Tempo, ditambah 10 kalimat sehari-hari).

## Membersihkan hasil pengumpulan

```powershell
# Hanya melapor (tidak mengubah apa pun)
..\..\.venv-cekfakta\Scripts\python bersihkan.py --hanya-lapor
# Membersihkan, dengan cadangan tbh_artikel.jsonl.cadangan-WAKTU
..\..\.venv-cekfakta\Scripts\python bersihkan.py
```

Yang dibuang hanya baris rusak (bukan JSON utuh), baris tanpa url atau judul, dan duplikat URL. Baris tanpa narasi atau tanpa tanggal tetap dipakai; tanggal yang tidak sah (misalnya `0000-00-00`) menjadi `null`. Menolak jalan selagi pengumpul berjalan.

## Uji otomatis

```powershell
..\..\.venv-cekfakta\Scripts\python -m pytest tests -q
```

Hanya fungsi murni (label, narasi, penggabungan, parser HTML); tidak memakai jaringan maupun model.
