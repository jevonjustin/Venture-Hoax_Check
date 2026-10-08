# Alat ukur pembacaan teks (Sesi 5.2)

Skrip untuk membandingkan pembaca teks pada screenshot uji: waktu baca per gambar dan CER terhadap transkripsi acuan. Kandidat yang dikenal: `rapidocr` (bawaan), `rapidocr_latin`, `paddleocr`, dan `praproses` (hanya praproses, tanpa pembaca). Alat ini hanya untuk pengukuran. Server (`server/app/`) tidak memakainya.

Hasil Sesi 5.2 dan keputusannya (RapidOCR bawaan) ada di `docs/RANCANGAN_PROYEK.md`.

Semua data ada di `server/data_lokal/` (masuk `.gitignore`, tidak ikut repo):

| Folder atau berkas | Isi |
|---|---|
| `screenshot_uji/` | 18 gambar bernama `01` sampai `18` (`.jpg`, `.jpeg`, `.png`, atau `.webp`). Tidak pernah diubah oleh skrip. |
| `sumber_gambar.csv` | Asal, ukuran asli, dan catatan tiap gambar. |
| `transkripsi/` | Transkripsi acuan (`NN.txt`) untuk menghitung CER. |
| `transkripsi_draf/` | Arsip draf transkripsi. Tidak dipakai skrip. |
| `hasil_ukur/` | Keluaran skrip: `KANDIDAT.csv`, `KANDIDAT.meta.json`, folder `KANDIDAT/` berisi teks mentah per gambar (`NN.txt`), dan `ringkasan.csv`. |

## Menyiapkan lingkungan

Butuh Python 3.12. Semua perintah dijalankan dari folder `server`. Ada dua lingkungan terpisah, keduanya di luar `.venv` milik server supaya library OCR tidak masuk ke dependensi server.

```powershell
cd server

# RapidOCR (kandidat rapidocr dan rapidocr_latin, serta semua subperintah selain paddleocr)
py -3.12 -m venv .venv-ukur
.venv-ukur\Scripts\python -m pip install -r alat\ukur_baca\requirements-ukur.txt

# PaddleOCR (kandidat paddleocr saja; dipisah karena bentrok numpy dan opencv dengan RapidOCR)
py -3.12 -m venv .venv-ukur-paddle
.venv-ukur-paddle\Scripts\python -m pip install -r alat\ukur_baca\requirements-ukur-paddle.txt
```

Subperintah yang tidak memanggil pembaca (`hitung-ulang`, `ringkas`, `kata-tak-terbaca`, `daftar`) bisa dijalankan dengan lingkungan mana pun yang punya Pillow.

## Subperintah `ukur.py`

Format: `python alat\ukur_baca\ukur.py [--acuan FOLDER] SUBPERINTAH`. Opsi `--acuan` mengganti folder transkripsi acuan dan harus ditulis sebelum nama subperintah.

| Subperintah | Fungsi |
|---|---|
| `daftar` | Mencetak nama kandidat yang dikenal. |
| `jalankan KANDIDAT [--ulang N]` | Memproses semua gambar dan menjalankan kandidat. Satu pemanasan dibuang, lalu tiap gambar dibaca N kali (bawaan 1) dan waktunya adalah median. Teks hasil pembacaan pertama disimpan di `hasil_ukur\KANDIDAT\NN.txt`, metrik dihitung, dan `KANDIDAT.csv` serta `KANDIDAT.meta.json` ditulis. Transkripsi diperiksa dulu: kalau ada `[?ragu: ...]` atau berkas yang hilang, program berhenti (kode keluar 2) sebelum model dimuat. |
| `hitung-ulang [KANDIDAT ...]` | Menghitung ulang metrik dari teks yang sudah tersimpan, tanpa memanggil pembaca. Dipakai setelah transkripsi diubah. Tanpa argumen, semua kandidat di `hasil_ukur\` (kecuali `praproses`). |
| `ringkas` | Rata-rata tiap kandidat, untuk semua gambar dan tanpa gambar 08. Mencetak tabel Markdown dan menulis `ringkasan.csv`. |
| `kata-tak-terbaca` | Daftar kata isi transkripsi (tanpa baris `[UI]` dan bagian `[?]`) yang tidak muncul di hasil satu kandidat pun. Kata dianggap terbaca kalau muncul utuh di hasil, atau (untuk kata sepanjang empat huruf lebih) sebagai potongan hasil yang spasinya dibuang, supaya kata yang menempel ke kata lain tidak ikut terdaftar. Dipakai untuk memeriksa apakah acuan memuat tebakan. |

Contoh:

```powershell
cd server
.venv-ukur\Scripts\python alat\ukur_baca\ukur.py jalankan rapidocr --ulang 3
.venv-ukur-paddle\Scripts\python alat\ukur_baca\ukur.py jalankan paddleocr --ulang 3
.venv-ukur\Scripts\python alat\ukur_baca\ukur.py ringkas
```

## Kolom CSV

| Kolom | Arti |
|---|---|
| `nama_file`, `lebar_asli`, `tinggi_asli` | Gambar asli. |
| `diperbesar` | `ya` kalau gambar mengalami perbesaran ke lebar 1080 px (lihat praproses di bawah). |
| `lebar_kirim`, `tinggi_kirim`, `ukuran_jpeg_byte` | Gambar yang dibaca mesin, yaitu hasil decode JPEG kiriman. |
| `detik_baca` | Median waktu satu kali baca (tanpa praproses dan tanpa pemanasan). |
| `cer_isi` | Metrik utama (aturan di bawah). Kosong untuk gambar tanpa teks. |
| `cer_penuh` | Pembanding: karakter baris `[UI]` diperlakukan seperti isi. |
| `ui_terbaca` | Proporsi karakter baris `[UI]` yang muncul di hasil (kecocokan potongan terdekat). |
| `karakter_karangan` | Jumlah karakter hasil yang tidak cocok dengan isi, UI, maupun wildcard. |
| `karakter_hasil` | Jumlah karakter hasil setelah normalisasi. |

## Praproses yang ditiru

Dikerjakan di memori oleh `praproses.py`, dalam urutan ini:

1. Gambar yang lebarnya di bawah 1080 px diperbesar ke lebar 1080 px dengan Lanczos. Ini meniru gambar terusan yang dibuka layar penuh di galeri HP lalu di-screenshot.
2. Praproses aplikasi: sisi terpanjang maksimal 2000 px, lalu JPEG kualitas 90.

Perbesaran tidak menambah detail asli, jadi waktu dan CER pada gambar beresolusi rendah hanya perkiraan kasar untuk screenshot HP yang sebenarnya.

## Aturan metrik (`cer.py`)

Format transkripsi acuan (`NN.txt`):

- Hanya teks yang terlihat di gambar. Emoji dilewati.
- Baris teks antarmuka media sosial diawali `[UI] `.
- Bagian yang tidak terbaca, tertutup, atau meragukan ditulis `[?]`.
- `[?ragu: ...]` tidak boleh ada di transkripsi akhir.

Acuan dan hasil sama-sama dinormalisasi (NFKC, huruf kecil, spasi dan baris baru dilipat jadi satu spasi), lalu dijajarkan dengan jarak edit karakter terhadap seluruh acuan (isi dan baris `[UI]`):

| Jenis karakter acuan | Cocok | Salah atau diganti | Hilang |
|---|---|---|---|
| isi | 0 | 1 | 1 |
| UI (dan spasi antarbaris) | 0 | 0 | 0 |
| `[?]` (wildcard) | menyerap nol, satu, atau banyak karakter hasil tanpa biaya | | |

Karakter hasil yang tidak terjajar dengan apa pun (sisipan) bernilai 1 dan dicatat sebagai `karakter_karangan`. `cer_isi` adalah biaya dibagi jumlah karakter isi bukan-wildcard.

Gambar 15 tidak berisi teks, jadi hanya dipakai untuk `karakter_karangan`. `ringkas` menampilkan dua variasi: semua gambar, dan tanpa gambar 08 (terlalu banyak wildcard). Menjalankan `python alat\ukur_baca\cer.py` mengeksekusi uji kecil untuk aturan ini.
