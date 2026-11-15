# Teks rilis Veritas 1.0.1

Berkas ini berisi dua teks siap pakai:

1. **Deskripsi GitHub Release**: salin semua isi di antara garis `BATAS AWAL` dan `BATAS AKHIR` ke kolom deskripsi rilis `v1.0.1`.
2. **Kartu cetak di samping QR**: maksimal 6 langkah, dipasang bersama `qr_veritas.png` atau `qr_veritas.svg`.

Teks privasi di bawah sama dengan butir onboarding aplikasi (`onboarding_4_isi` di `app/src/main/res/values/strings.xml`). Bila teks onboarding berubah, ubah juga di sini.

---

<!-- BATAS AWAL: deskripsi GitHub Release -->

## Veritas 1.0.1

Veritas membantu memeriksa informasi yang meragukan di layar HP. Ketuk tombol cek yang melayang, pilih bagian layar yang ingin dicek, lalu Veritas menampilkan ciri-ciri hoaks yang ditemukan beserta bukti, penjelasan, dan artikel cek fakta yang relevan. Hasilnya berupa petunjuk, bukan putusan akhir.

**Unduh:** [veritas.apk](https://github.com/jevonjustin/Venture-Hoax_Check/releases/latest/download/veritas.apk) (Android 8.0 ke atas)

### Cara memasang

1. **Unduh** `veritas.apk` dari tautan di atas, lalu buka berkasnya dari notifikasi unduhan atau aplikasi File.
2. **Izinkan instal dari browser.** Bila muncul pesan bahwa browser tidak diizinkan memasang aplikasi, ketuk **Setelan**, aktifkan **Izinkan dari sumber ini**, lalu kembali dan ketuk **Instal**.
3. **Peringatan Play Protect.** Veritas belum terdaftar di Google Play, jadi Play Protect bisa menampilkan peringatan aplikasi tidak dikenal. Ketuk **Detail lainnya** (atau tanda panah), lalu **Tetap instal**. Bila ditawari mengirim aplikasi untuk dipindai, pilihan apa pun tidak memengaruhi pemasangan.
4. **Onboarding.** Saat pertama dibuka, Veritas menampilkan empat halaman singkat tentang cara kerja dan data yang dikirim. Baca halaman terakhir, lalu ketuk **Mulai**.
5. **Izin tampil di atas aplikasi lain.** Ketuk **Berikan izin**, pilih **Veritas** di daftar aplikasi, aktifkan izinnya, lalu kembali ke Veritas.
6. **Izin rekam layar.** Ketuk **Aktifkan tombol cek**, lalu **Lanjutkan**. Di dialog Android, pilih **Seluruh layar** (bukan satu aplikasi), lalu mulai.
7. **Mulai mengecek.** Buka aplikasi lain, ketuk tombol cek yang melayang, atur kotak pada bagian yang ingin dicek, lalu ketuk **Cek Sekarang**.

Sudah memasang versi 1.0? Versi 1.0.1 bisa langsung dipasang di atasnya tanpa menghapus aplikasi lama.

### Penting diketahui

- **Butuh internet.** Potongan layar dianalisis di server Veritas, jadi HP harus tersambung ke internet (Wi-Fi atau data seluler).
- **Hanya aktif selama showcase.** Server Veritas berjalan di laptop pengembang dan hanya dinyalakan selama acara showcase. Di luar waktu itu, aplikasi menampilkan pesan "Server sedang tidak aktif".
- **Indikasi, bukan putusan.** "Tidak Ditemukan Indikasi Hoaks" bukan jaminan informasi itu benar. Tetap periksa sumbernya.

### Privasi: apa saja yang dikirim

- Hanya bagian layar yang dipilih yang dikirim ke server Veritas, yang berjalan di laptop pengembang dan terhubung ke internet lewat layanan terowongan ngrok.
- Gambar melewati ngrok dalam perjalanan ke server, tetapi tidak disimpan di HP maupun di server dan tidak dikirim ke penyedia AI.
- Teks hasil bacaan gambar dikirim ke penyedia AI pihak ketiga (Groq) untuk dianalisis, setelah nomor telepon, alamat email, dan nama akun berawalan @ disamarkan.
- Penyamaran dilakukan otomatis berdasarkan pola, jadi bisa ada yang terlewat. Nama orang, tautan, dan isi pesan itu sendiri tidak disamarkan. Sebaiknya jangan cek bagian yang memuat data pribadi.

### Perubahan dari 1.0

- Pesan saat server tidak bisa dihubungi kini menyarankan memeriksa koneksi internet.
- Saat server Veritas tidak aktif, aplikasi menampilkan "Server sedang tidak aktif" alih-alih "Server sedang bermasalah".

Veritas dibuat untuk mata kuliah Venture Creation.

<!-- BATAS AKHIR -->

---

## Kartu cetak di samping QR

```
VERITAS: cek hoaks langsung dari layar HP
Pindai QR untuk mengunduh (Android 8.0 ke atas, butuh internet)

1. Pindai QR, unduh veritas.apk, lalu buka berkasnya.
2. Izinkan browser memasang aplikasi bila diminta.
3. Muncul peringatan Play Protect? Ketuk "Detail lainnya", lalu "Tetap instal".
4. Buka Veritas, baca halaman pengenalan, lalu ketuk "Mulai".
5. Berikan izin tampil di atas aplikasi lain, lalu ketuk "Aktifkan tombol cek" dan pilih "Seluruh layar".
6. Ketuk tombol melayang, pilih bagian yang ingin dicek, lalu "Cek Sekarang".

Server hanya aktif selama showcase. Hanya bagian layar yang dipilih yang dikirim;
gambar tidak disimpan. Rincian privasi ada di aplikasi, menu "Cara kerja dan privasi".
```
