# Kontrak API Server Cek Hoaks

Versi kontrak: **0.5** (ditetapkan di tahap 4, diperluas di Sesi 5.5 dengan `pemeriksaan_terbatas`, `url_format_lama`, dan id ciri baru `permintaan_data_rahasia`). Versi server: 0.6.0. Kalau kontrak berubah, perbarui dokumen ini, `server/app/skema.py`, dan `app/src/main/java/com/example/cekhoaks/KontrakApi.kt` sekaligus.

- Semua field memakai Bahasa Indonesia dengan gaya `snake_case`.
- Respons berformat JSON UTF-8.
- Aplikasi mengabaikan field yang tidak dikenalnya. Karena itu, server boleh menambah field baru tanpa merusak aplikasi versi lama. Mengganti nama atau menghapus field berarti kontrak berubah.
- Server tidak pernah menyimpan gambar, baik di disk maupun di log.

## `GET /health`

Dipakai tombol "Uji koneksi" di aplikasi.

```json
{"status": "ok", "versi": "0.6.0"}
```

## `POST /analisis`

Body berupa `multipart/form-data` dengan satu field:

| Field | Isi |
|---|---|
| `gambar` | Potongan layar berformat JPEG. Server juga menerima PNG, tetapi aplikasi selalu mengirim JPEG. Ukuran maksimal 8 MB (8.388.608 byte). |

Aplikasi memperkecil potongan sampai sisi terpanjangnya paling besar 2000 px, lalu menyandikannya sebagai JPEG kualitas 90.

**Mode demo:** query `?paksa=kuat|hati_hati|tidak_ditemukan|teks_tidak_terbaca` memaksa hasil tertentu dengan data contoh (teks tetap dibaca sungguhan). Nilai yang sama bisa diberikan lewat variabel lingkungan `PAKSA_TINGKAT`. Kalau keduanya ada, query yang dipakai. Kalau keduanya kosong, hasil berasal dari analisis sungguhan; tidak ada lagi hasil bergiliran. Dalam mode demo `pemeriksaan_terbatas` selalu kosong.

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
      "tanggal": "2025-11-04",
      "url_format_lama": false
    }
  ],
  "teks_terbaca": "VIRAL!! Air keran di Jakarta ... SEBARKAN ke keluarga sebelum dihapus!!!",
  "durasi_ms": 1876,
  "pemeriksaan_terbatas": []
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `id_permintaan` | string | UUID tanpa tanda hubung. Dipakai untuk mencocokkan log HP dengan log server |
| `tingkat` | `"kuat"` \| `"hati_hati"` \| `"tidak_ditemukan"` | Tingkat indikasi (RANCANGAN §9) |
| `klaim_utama` | string \| null | Satu kalimat inti pesan yang dicek. Kata-katanya diambil dari teks layar (hasil rangkuman model bahasa yang diperiksa kesetiaannya, atau potongan teks), tidak pernah menyatakan benar atau salah, dan tanpa kata ganti orang kedua. Bernilai null jika tidak ada kalimat yang layak |
| `ciri` | daftar | Ciri hoaks yang ditemukan, diurutkan dari keyakinan tinggi lebih dulu. Boleh kosong. Satu ciri berkeyakinan `sedang` yang tidak didukung ciri lain dan tidak disertai artikel tidak ditampilkan: tingkatnya `tidak_ditemukan` dan daftar ini kosong |
| `ciri[].id` | string | Salah satu dari sembilan id tetap di bawah. **Id ini bagian dari kontrak** karena dipakai untuk membandingkan penilaian pengguna dengan temuan sistem (tahap 6). Aplikasi sebaiknya punya teks cadangan untuk id yang tidak dikenal (tahap 6) |
| `ciri[].nama` | string | Nama ciri untuk ditampilkan |
| `ciri[].bukti` | daftar string | Potongan teks dari gambar yang menunjukkan ciri ini. Minimal satu. Setiap bukti adalah potongan **persis** dari `teks_terbaca` sampai perbedaan spasi dan baris baru (keduanya sudah dirapikan menjadi satu spasi), sehingga aplikasi bisa menyorotnya dengan membandingkan teks tanpa memperhatikan spasi. Untuk `pernah_dibantah`, buktinya kalimat di layar yang paling mirip dengan artikel |
| `ciri[].penjelasan` | string | Teks template yang ditulis sendiri, bukan buatan LLM, dan tanpa kata ganti orang kedua |
| `ciri[].keyakinan` | `"tinggi"` \| `"sedang"` | Tinggi jika terdeteksi oleh aturan berpola kuat atau oleh dua sumber (aturan dan model bahasa). Sedang jika hanya satu sumber. Tidak ada angka persentase |
| `cek_fakta` | daftar | Artikel cek fakta yang mirip, diurutkan dari skor tertinggi, paling banyak 3. Hanya artikel dengan skor sedikitnya 0,85 yang judulnya juga relevan dengan teks. Boleh kosong |
| `cek_fakta[].judul` | string | |
| `cek_fakta[].sumber` | string | Nama media cek fakta |
| `cek_fakta[].url` | string | |
| `cek_fakta[].skor_kemiripan` | angka 0-1 | |
| `cek_fakta[].label` | string | Kesimpulan artikel di database: `salah`, `penipuan`, `klarifikasi`, `benar`, `satir`, `belum_terbukti`, atau `lainnya`. Hanya `salah` dan `penipuan` yang bisa menaikkan tingkat ke `kuat`; label lain tampil sebagai rujukan |
| `cek_fakta[].tanggal` | string \| null | Tanggal terbit artikel (ISO 8601, contoh `2025-11-04`). Bernilai null jika tidak diketahui |
| `cek_fakta[].url_format_lama` | boolean | `true` jika `url` berformat lama turnbackhoax.id yang sudah mati (404); judul artikel tetap bisa dicari di web. Bawaan `false` |
| `teks_terbaca` | string | Teks bersih hasil baca gambar (elemen antarmuka sudah dibuang). Setiap `bukti[]` adalah potongan teks ini, dengan spasi dan baris baru dirapikan menjadi satu spasi |
| `durasi_ms` | integer | Lama pemrosesan di server |
| `pemeriksaan_terbatas` | daftar string | Bagian pemeriksaan yang tidak berjalan pada analisis ini: `"cek_fakta"` (pencarian database nonaktif atau gagal) dan `"ai"` (analisis teks oleh model bahasa gagal atau dimatikan). Kosong berarti semuanya berjalan. Tingkat `tidak_ditemukan` dengan daftar tidak kosong bukan hasil pemeriksaan lengkap. Tidak memuat nama penyedia. Bawaan kosong |

### Nilai `ciri[].id` (kontrak 0.5)

| id | Ciri |
|---|---|
| `permintaan_data_rahasia` | Permintaan kode, data rahasia, atau uang |
| `ajakan_menyebarkan` | Ajakan menyebarkan |
| `desakan_waktu` | Desakan waktu |
| `kapital_tanda_seru` | Huruf kapital dan tanda seru berlebihan |
| `link_mencurigakan` | Tautan pemendek atau tidak resmi |
| `sumber_tidak_jelas` | Merujuk sumber samar tanpa nama |
| `judul_clickbait` | Judul memancing klik |
| `bahasa_provokatif` | Bahasa provokatif |
| `pernah_dibantah` | Klaim serupa sudah dibantah media cek fakta (ditentukan pencarian, bukan model bahasa) |

`permintaan_data_rahasia` baru di kontrak 0.5. Aplikasi lama yang tidak mengenalnya tetap menampilkannya dengan nama dan penjelasan dari server.

### Nilai `cek_fakta[].label`

`salah`, `penipuan`, `klarifikasi`, `benar`, `satir`, `belum_terbukti`, `lainnya`. Hanya `salah` dan `penipuan` yang menentukan tingkat `kuat`. Artikel berlabel `benar`, `klarifikasi`, atau `satir` tampil sebagai rujukan dan, bila skornya setara atau lebih tinggi dari artikel `salah` atau `penipuan`, menurunkan hasil ke `hati_hati`. Server tidak pernah menyatakan sebuah informasi benar atas dasar pendapatnya sendiri.

### `pemeriksaan_terbatas`

Daftar bagian yang tidak berjalan: `"cek_fakta"` dan/atau `"ai"`. Aplikasi (tahap 6) sebaiknya menampilkan keterangan ketika daftarnya tidak kosong, terutama untuk `tidak_ditemukan`. Dalam mode demo (`?paksa=`) daftar selalu kosong karena hasilnya contoh dan bukan pemeriksaan.

### Mode demo

`?paksa=` atau `PAKSA_TINGKAT` mengembalikan hasil contoh dengan `teks_terbaca` yang asli. Pembersihan teks dan pembacaan tetap berjalan; ambang `teks_tidak_terbaca` dilewati (kecuali nilai `teks_tidak_terbaca`, yang langsung mengembalikan galat), serta pencarian dan model bahasa tidak dipakai. `bukti` pada hasil contoh tidak berasal dari `teks_terbaca`.

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

Kalau aplikasi memutus koneksi (tombol Batal), server menghentikan pemrosesan dan mencatat `Permintaan <id> dibatalkan klien` di log.

## Batas waktu di aplikasi

Nilainya diatur di `KlienApi.kt` (`TIMEOUT_CONNECT_DETIK`, `TIMEOUT_READ_DETIK`).

| Batas | Nilai | Galat yang tampil jika terlewati |
|---|---|---|
| Menyambung ke server | 5 detik | Server tidak terjangkau |
| Menunggu jawaban `/analisis` | 60 detik | Server terlalu lama menjawab |
| Menunggu jawaban `/health` | 5 detik | Server terlalu lama menjawab |
