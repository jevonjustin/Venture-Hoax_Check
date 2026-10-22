# Veritas

Aplikasi Android untuk memeriksa indikasi hoaks pada informasi yang sedang dibaca di layar HP. Proyek mata kuliah Venture Creation. Nama teknis proyek dan package tetap `cekhoaks` (`com.example.cekhoaks`).

## Cara kerja

1. Pengguna mengetuk tombol cek yang mengambang di atas aplikasi lain, lalu memilih bagian layar yang ingin diperiksa.
2. Sambil menunggu, pengguna boleh memberi penilaian awal (Percaya, Ragu-ragu, atau Tidak percaya).
3. Potongan gambar dikirim ke server analisis. Server membaca teksnya, mencari artikel cek fakta yang mirip, dan memeriksa ciri-ciri hoaks.
4. Hasilnya berupa tingkat indikasi, ciri yang ditemukan beserta kutipannya, artikel cek fakta terkait, dan perbandingan dengan penilaian awal. Hasil ini pemandu, bukan vonis benar atau salah.

## Isi repo

- `app/`: aplikasi Android (Kotlin, Jetpack Compose untuk layar aplikasi, View lewat `WindowManager` untuk overlay).
- `server/`: server analisis Python (FastAPI). Server membaca teks dengan RapidOCR, mencari di database lokal berisi 21.371 artikel cek fakta dari TurnBackHoax (MAFINDO) dan klarifikasi Komdigi dengan multilingual-e5-base, lalu memakai model bahasa lewat API (Groq, cadangan Gemini) untuk mengusulkan klaim dan ciri. Tingkat indikasi ditentukan logika server sendiri, bukan oleh model bahasa. Database dan model tidak ikut di repo. Cara menjalankannya ada di [`server/README.md`](server/README.md).
- `docs/`: rancangan proyek ([`RANCANGAN_PROYEK.md`](docs/RANCANGAN_PROYEK.md)), kontrak API ([`API.md`](docs/API.md)), dan proyek referensi beserta lisensinya ([`REFERENSI.md`](docs/REFERENSI.md)).

## Privasi

Gambar hanya dibaca di memori server dan tidak disimpan. Yang dikirim ke penyedia model bahasa hanya teks, setelah nomor telepon, email, dan `@akun` disamarkan. Rinciannya ada di [`server/README.md`](server/README.md).
