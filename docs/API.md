# Kontrak API Server Cek Hoaks

Versi kontrak: **0.4** (ditetapkan di tahap 4, dipakai tahap 5 dan 6). Kalau kontrak berubah, perbarui dokumen ini, `server/app/skema.py`, dan `app/src/main/java/com/example/cekhoaks/KontrakApi.kt` sekaligus.

- Semua field memakai Bahasa Indonesia dengan gaya `snake_case`.
- Respons berformat JSON UTF-8.
- Aplikasi mengabaikan field yang tidak dikenalnya. Karena itu, server boleh menambah field baru tanpa merusak aplikasi versi lama. Mengganti nama atau menghapus field berarti kontrak berubah.
- Server tidak pernah menyimpan gambar, baik di disk maupun di log.

## `GET /health`

Dipakai tombol "Uji koneksi" di aplikasi.

```json
{"status": "ok", "versi": "0.4.0"}
```

## `POST /analisis`

Body berupa `multipart/form-data` dengan satu field:

| Field | Isi |
|---|---|
| `gambar` | Potongan layar berformat JPEG. Server juga menerima PNG, tetapi aplikasi selalu mengirim JPEG. Ukuran maksimal 8 MB (8.388.608 byte). |

Aplikasi memperkecil potongan sampai sisi terpanjangnya paling besar 2000 px, lalu menyandikannya sebagai JPEG kualitas 90.

**Khusus server dummy:** query `?paksa=kuat|hati_hati|tidak_ditemukan|teks_tidak_terbaca` memaksa hasil tertentu. Nilai yang sama bisa diberikan lewat variabel lingkungan `PAKSA_TINGKAT`. Kalau keduanya ada, query yang dipakai. Kalau keduanya kosong, tingkat hasil bergiliran: `kuat` → `hati_hati` → `tidak_ditemukan`. Server sungguhan (tahap 5) tidak memiliki parameter ini.

### Respons sukses (200)

```json
{
  "id_permintaan": "1d3527b25b394e1bab098b3f9112b28f",
  "tingkat": "kuat",
  "klaim_utama": "Air keran di Jakarta mengandung zat berbahaya yang menyebabkan penyakit misterius",
  "ciri": [
    {
      "id": "ajakan_menyebarkan",
      "nama": "Ajakan menyebarkan",
      "bukti": ["SEBARKAN ke keluarga"],
      "penjelasan": "Pesan yang mendesak untuk segera disebarkan sering dibuat agar ...",
      "keyakinan": "tinggi"
    }
  ],
  "cek_fakta": [
    {
      "judul": "[SALAH] Air Keran di Jakarta Sebabkan Penyakit Misterius dalam Semalam",
      "sumber": "Contoh Cek Fakta",
      "url": "https://example.com/cek-fakta/air-keran-penyakit-misterius",
      "skor_kemiripan": 0.87,
      "label": "salah",
      "tanggal": "2025-11-04"
    }
  ],
  "teks_terbaca": "VIRAL!! Air keran di Jakarta ... SEBARKAN ke keluarga sebelum dihapus!!!",
  "durasi_ms": 1876
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `id_permintaan` | string | UUID tanpa tanda hubung. Dipakai untuk mencocokkan log HP dengan log server |
| `tingkat` | `"kuat"` \| `"hati_hati"` \| `"tidak_ditemukan"` | Tingkat indikasi (RANCANGAN §9) |
| `klaim_utama` | string \| null | Ringkasan satu kalimat tentang hal yang dicek. Bernilai null jika tidak ada klaim yang jelas |
| `ciri` | daftar | Ciri hoaks yang ditemukan, diurutkan dari yang paling penting. Boleh kosong |
| `ciri[].id` | string | Id tetap dari daftar ciri di RANCANGAN §8. **Id ini bagian dari kontrak** karena dipakai untuk membandingkan penilaian pengguna dengan temuan sistem (tahap 6) |
| `ciri[].nama` | string | Nama ciri untuk ditampilkan |
| `ciri[].bukti` | daftar string | Potongan teks dari gambar yang menunjukkan ciri ini. Minimal satu |
| `ciri[].penjelasan` | string | Teks template yang ditulis sendiri, bukan buatan LLM, dan tanpa kata ganti orang kedua |
| `ciri[].keyakinan` | `"tinggi"` \| `"sedang"` | Tinggi jika terdeteksi oleh aturan atau oleh minimal dua sumber deteksi |
| `cek_fakta` | daftar | Artikel cek fakta yang mirip dengan klaim, diurutkan dari skor tertinggi. Boleh kosong |
| `cek_fakta[].judul` | string | |
| `cek_fakta[].sumber` | string | Nama media cek fakta |
| `cek_fakta[].url` | string | |
| `cek_fakta[].skor_kemiripan` | angka 0-1 | |
| `cek_fakta[].label` | string | Kesimpulan artikel, misalnya `salah`, `hoaks`, `menyesatkan`. Tingkat `kuat` hanya boleh muncul jika ada artikel dengan label yang menyatakan klaimnya salah |
| `cek_fakta[].tanggal` | string \| null | Tanggal terbit artikel (ISO 8601, contoh `2025-11-04`). Bernilai null jika tidak diketahui |
| `teks_terbaca` | string | Seluruh teks yang dibaca dari gambar |
| `durasi_ms` | integer | Lama pemrosesan di server |

Tingkat `tidak_ditemukan` hanya dipakai jika teks berhasil dibaca dan dianalisis. Gambar tanpa teks yang terbaca mendapat galat `teks_tidak_terbaca`, bukan tingkat `tidak_ditemukan`. Kalau yang dikembalikan `tidak_ditemukan`, pengguna bisa mengira informasinya sudah diperiksa dan aman.

**Untuk perbandingan dengan penilaian pengguna (tahap 6)**, aplikasi tidak mengirim penilaian pengguna ke server. Perbandingan dilakukan di HP dengan dua cara:
- Sikap pengguna dibandingkan dengan `tingkat`: Tidak percaya ↔ `kuat`, Ragu ↔ `hati_hati`, Percaya ↔ `tidak_ditemukan`.
- Ciri yang dipilih pengguna dibandingkan dengan `ciri[].id` memakai logika himpunan.

### Respons galat

Semua respons dengan status selain 2xx memakai format berikut:

```json
{"galat": {"kode": "terlalu_besar", "pesan": "Body 9437184 byte melebihi batas"}}
```

`pesan` hanya untuk log developer. Teks yang tampil ke pengguna dipilih aplikasi dari `strings.xml` berdasarkan `kode`.

| Kode | HTTP | Kapan |
|---|---|---|
| `gambar_kosong` | 400 | Field `gambar` ada tetapi isinya 0 byte |
| `terlalu_besar` | 413 | Gambar atau body melebihi 8 MB |
| `bukan_gambar` | 415 | Isi field bukan JPEG/PNG yang utuh |
| `permintaan_tidak_valid` | 422 | Body bukan multipart, field `gambar` tidak ada, atau nilai `paksa` tidak dikenal |
| `teks_tidak_terbaca` | 422 | Gambar tidak berisi teks yang bisa dibaca |
| `tidak_ditemukan` | 404 | Rute tidak ada |
| `metode_salah` | 405 | Metode HTTP salah untuk rute ini |
| `galat_http` | sesuai galat aslinya (selain 404 dan 405) | Galat HTTP lain yang dihasilkan kerangka server dan tidak punya kode khusus di tabel ini. Aplikasi menampilkannya sebagai kartu galat umum |
| `galat_server` | 500 | Galat internal yang tidak terduga di server |

Kalau aplikasi memutus koneksi (tombol Batal), server dummy menghentikan pemrosesan dan mencatat `Permintaan <id> dibatalkan klien` di log.

## Batas waktu di aplikasi

Nilainya diatur di `KlienApi.kt` (`TIMEOUT_CONNECT_DETIK`, `TIMEOUT_READ_DETIK`).

| Batas | Nilai | Galat yang tampil jika terlewati |
|---|---|---|
| Menyambung ke server | 5 detik | Server tidak terjangkau |
| Menunggu jawaban `/analisis` | 60 detik | Server terlalu lama menjawab |
| Menunggu jawaban `/health` | 5 detik | Server terlalu lama menjawab |
