# Alat uji analisis (Sesi 5.5)

Menjalankan pipeline `/analisis` yang sama dengan server pada 18 screenshot di `server\data_lokal\screenshot_uji\`, lalu menulis tabel ringkasan ke `server\data_lokal\hasil_analisis\` beserta perbandingan dengan putaran sebelumnya. Gambar hanya dibaca dari disk. Berkas hasil memuat teks gambar dan klaim, jadi tetap lokal (folder itu masuk `.gitignore`). Semua perintah dijalankan dari folder `server`.

| Berkas | Fungsi |
|---|---|
| `tahap_b.py` | Alat utama: pipeline lengkap, dengan atau tanpa LLM |
| `diagnosa_llm.py` | Menguji penyedia LLM dengan teks contoh (status HTTP, kode galat, durasi). Memanggil API |
| `tahap_a.py` | Putaran awal tanpa LLM (acuan `tahap_a.md`); fungsi bantunya dipakai `tahap_b.py` |

## Satu perintah, 18 gambar

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server

# Tanpa LLM: tidak memanggil API, tanpa jaringan
.venv\Scripts\python.exe alat\uji_analisis\tahap_b.py --tanpa-llm --nama tanpa_llm

# Dengan LLM (MEMANGGIL API Groq, cadangan Gemini dimatikan), dibandingkan dengan putaran tanpa LLM
.venv\Scripts\python.exe alat\uji_analisis\tahap_b.py --nama dengan_llm --acuan tanpa_llm.md
```

| Opsi | Bawaan | Fungsi |
|---|---|---|
| `--nama` | `tahap_b` | Nama berkas hasil (`<nama>.md`) |
| `--acuan` | `tahap_a.md` | Berkas pembanding di folder yang sama |
| `--tanpa-llm` | mati | Tidak memanggil API LLM |
| `--jeda` | `10` (0 bila `--tanpa-llm`) | Jeda antar gambar (detik). Kuota gratis Groq 8.000 token per menit, sekitar 1.100 token per gambar |
| `--cadangan` | mati | Mengizinkan Gemini sebagai cadangan. Bawaannya mati supaya hasil seluruhnya Groq dan teks tidak ke Google |
| `--ulang-429` | `3` | Berapa kali satu gambar diulang setelah Groq kena 429 (menunggu sesuai Retry-After) |

## Isi tabel

- Ringkasan: tingkat, penyedia, sumber klaim, kutipan LLM yang ditolak, token (rata-rata dan maksimum), durasi (median dan p95).
- **Konfirmasi:** 03, 06, 08 tetap `hati_hati` dengan `permintaan_data_rahasia` tinggi, dan 07 tetap `tidak_ditemukan` tanpa ciri.
- Tabel per gambar: tingkat dan varian, klaim, rantai percobaan penyedia, ciri, token, sumber klaim.
- Bukti dan ciri yang dibuang oleh pengaman struktural, aturan `sumber_tidak_jelas`, dan aturan ciri sedang tunggal.
- Perbandingan dengan berkas acuan: perubahan tingkat, ciri, dan klaim.
- Rincian per gambar: klaim LLM beserta kesetiaannya, ciri beserta bukti, dan artikel kandidat.

## Evaluasi data berlabel (Sesi 5.6): `evaluasi_berlabel.py`

Menjalankan pipeline `/analisis` yang sama (lewat `orkestrator.jalankan`, tanpa menduplikasi logika) pada gambar di `server\data_lokal\evaluasi\` (`metadata.csv`, `gambar\`, `uji_beku.sha256`). Tiga tahap berat memakai cache per gambar di `server\data_lokal\evaluasi\cache\`:

| Tahap | Berkas cache | Kunci |
|---|---|---|
| OCR (+ teks bersih) | `ocr\<sha256 gambar>.json` | sha256 gambar + versi RapidOCR |
| Pencarian (top-20 lengkap dengan skor dan id) | `cari\<sha256>__biasa.json`, `__loo.json` | gambar + hash kueri + sidik database dan model e5 |
| LLM (respons mentah + hasil parse) | `llm\<sha256>.json` (`jalan` 1..N) | hash teks yang dikirim (sudah disamarkan) + model + hash badan permintaan (prompt, skema, parameter) |

Karena kunci LLM memuat hash teks, model, dan prompt, panggilan ulang hanya terjadi bila salah satunya berubah. Teks yang sampai ke LLM hanya lewat orkestrator (penyamaran `samarkan.py`). LLM tidak menerima hasil pencarian, jadi cache LLM dipakai bersama mode `biasa` dan `loo`. Mode `loo` mengeluarkan artikel `id_artikel_sumber` dari pencarian (hook `Pencarian.cari(kecualikan_id=...)`, tidak terhubung ke server); gambar tanpa `id_artikel_sumber` memakai hasil `biasa`.

Perintah (PowerShell; opsi `--log` bawaan `C:\Users\User\AndroidStudioProjects\CekHoaks\.orkestrasi\logs\evaluasi_berlabel.log` berisi PID di awal lalu progres `n/total`, hanya id dan angka):

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server
$py = "C:\Users\User\AndroidStudioProjects\CekHoaks\server\.venv\Scripts\python.exe"
$alat = "C:\Users\User\AndroidStudioProjects\CekHoaks\server\alat\uji_analisis\evaluasi_berlabel.py"

# 1. Kumpul tanpa LLM (OCR + pencarian biasa dan loo; tanpa jaringan; memuat e5 sekitar 1,5 GB RAM). Tidak mencetak tingkat.
& $py $alat kumpul --set semua --tanpa-llm

# 2. Kumpul dengan LLM (Groq saja, jeda 8 detik, --maks-panggilan WAJIB; MEMANGGIL API). Berhenti bila sisa kuota harian < 25 atau 3x 429 beruntun;
#    cache adalah checkpoint, jalankan perintah yang sama untuk melanjutkan. --ulang-llm 3 menambah jalan ke-2 dan ke-3 (stabilitas).
& $py $alat kumpul --set semua --tahap llm --maks-panggilan 200
& $py $alat kumpul --set dev --tahap llm --maks-panggilan 450 --ulang-llm 3
#    Batasi gambar: --id ev001,ev005 atau --id-berkas <berkas, satu id per baris> (id set uji ditolak bila --set dev).
#    Token dicatat dari usage Groq per jalan (cache LLM, kunci "usage") dan per tanggal lokal di cache\jumlah_panggilan_llm.json
#    ("per_hari"). --maks-token-hari N berhenti (kode 3) bila token hari ini + rata-rata per panggilan (bawaan 1200) > N.
#    429 yang menyebut batas harian ("per day"/TPD/RPD) langsung berhenti (alasan 429_harian), tanpa menunggu.
& $py $alat kumpul --set dev --tahap llm --maks-panggilan 100 --ulang-llm 3 --id-berkas C:\jalur\id_stabilitas.txt --maks-token-hari 90000
& $py $alat ringkas-token        # cetak penghitung panggilan dan token per hari, tanpa memanggil apa pun

# 3. Nilai set dev dari cache (boleh berulang; tanpa OCR dan LLM). Laporan: server\data_lokal\hasil_analisis\<nama>.md
& $py $alat nilai --set dev --nama dev_awal
& $py $alat nilai --set dev --nama dev_ambang --ambang skor_kuat=0.88,relevansi=0.40
& $py $alat nilai --set dev --nama dev_jalan2 --jalan 2            # memakai jalan LLM ke-2
& $py $alat nilai --set dev --nama dev_tanpa_llm --tanpa-llm        # abaikan cache LLM

# 4. Sapuan grid (nama=awal:akhir:langkah atau nama=a/b/c, dipisah koma; hanya set dev)
& $py $alat nilai --set dev --nama sapuan_1 --sapu "skor_kuat=0.86:0.92:0.02,relevansi=0.30/0.40/0.50"

# 5. Segel: simpan hasil kode AWAL untuk set uji (tanpa ringkasan) SEBELUM menyetel ambang
& $py $alat --profil lama segel-awal

# 6. Penilaian uji final (sekali; membutuhkan uji_beku.sha256 yang cocok; kali kedua ditolak kecuali --paksa)
& $py $alat --profil akhir nilai --set uji --final --nama uji_final_akhir
```

Profil ambang (`--profil`, opsi global sebelum subperintah) diambil dari `konfigurasi.PROFIL_AMBANG`, tabel yang sama dengan server: `lama` (bawaan alat, perilaku commit 7742a73) atau `akhir` (bawaan server). `CEKHOAKS_PROFIL_AMBANG` diabaikan alat. `--ambang` dan `--maks-token-kueri` menimpa nilai profil.

Ambang yang bisa ditimpa (`--ambang`, `--sapu`); kolom Bawaan = nilai profil `lama`:

| Nama | Bidang `Pengaturan` | Bawaan |
|---|---|---|
| `skor_kuat` (atau `skor_cocok`) | `ambang_cocok` | 0,88 |
| `skor_mirip` | `ambang_mirip` | 0,85 |
| `relevansi` | `relevansi_minimum` | 0,40 |
| `selisih` | `selisih_konflik` | 0,02 |
| `satir` | `satir_hati_hati` | ya |
| `top_k` | `cocok_top_k` (maks 20) | 5 |
| `teks` | `ambang_teks_karakter` | 20 |
| `kesetiaan` | `klaim_kesetiaan_minimum` | 0,5 |
| `cek_fakta_maks`, `klaim_skor_minimum` | sama | 3 dan 3,0 |
| `toleransi_ocr` (+ `relevansi_edit_pendek`, `relevansi_edit_panjang`) | `relevansi_toleransi_ocr` | mati (1 dan 2 huruf) |
| `kombinasi`, `kombinasi_skor`, `kombinasi_relevansi`, `kombinasi_kata` | `kuat_kombinasi_aktif`, `_skor`, `_relevansi`, `_min_kata` | mati, 0,86, 0,70, 4 |
| `lolos` | `relevansi_lolos_skor` (peringkat 1 lolos tanpa syarat relevansi) | kosong = `ambang_cocok` |
| `kesetiaan_ketat` | `periksa_kesetiaan_klaim` | mati |

Bila `toleransi_ocr` atau batas editnya diubah, relevansi di cache pencarian dihitung ulang dari judul kandidat dan kueri (IDF dari `artikel.jsonl`), dengan fungsi `cocok.relevansi_judul` yang sama. Laporan juga mencatat gambar tanpa cache LLM (dinilai seperti LLM gagal, bukan galat) dan gambar tanpa tahap LLM (teks_tidak_terbaca).

Catatan:
- Panggilan LLM sungguhan memakai klien `llm.py` dengan transport sendiri (hanya Groq; cadangan Gemini tidak pernah dipakai walau env menyalakannya), yang menghitung setiap percobaan HTTP (termasuk ulang) ke `cache\jumlah_panggilan_llm.json` dan menjaga jeda minimal 8 detik. Batas waktu per panggilan diperlebar sebesar jeda karena transport tidur di dalamnya. Hanya hasil sukses yang disimpan.
- Laporan hanya memuat id, kategori, label, dan angka (tanpa teks OCR, narasi, atau `catatan`). Hasil dipisah semua, asli, dan sintetis; mode `loo` terpisah dari `biasa`.
- Opsi global `--akar` mengganti folder evaluasi (untuk uji asap di folder sementara).
- Set uji: `kumpul` memproses dev dan uji tetapi tidak mencetak hasil; `nilai --set uji` hanya dengan `--final`, memverifikasi `uji_beku.sha256`, lalu menulis `cache\uji_sudah_dinilai.json`.
- `pytest` untuk alat ini: `server\tests\test_evaluasi_berlabel.py` (tanpa jaringan).
