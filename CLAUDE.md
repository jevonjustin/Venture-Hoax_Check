# CLAUDE.md — Aplikasi Cek Hoaks (nama sementara)

## Ringkasan proyek

Aplikasi Android untuk mata kuliah Venture Creation. Pengguna yang ragu dengan informasi di layar HP mengetuk tombol mengambang, memilih area layar, lalu potongan gambar dikirim ke server di laptop untuk dianalisis (Qwen-VL, database cek fakta, dan model validasi). Hasilnya berupa ciri-ciri hoaks beserta bukti dan penjelasan, bukan vonis mutlak.

Rancangan lengkap ada di `docs/RANCANGAN_PROYEK.md`. Baca dokumen itu sebelum mengerjakan tahap baru. Daftar proyek referensi dan lisensinya ada di `docs/REFERENSI.md`.

## Status tahap

- Tahap aktif: **Tahap 5 berjalan (Sesi 5.1–5.4 selesai, Sesi 5.5 belum dimulai)**
- Tahap selesai: Tahap 1 (tombol mengambang overlay), Tahap 2 (tombol bisa digeser, ketukan mengambil screenshot layar penuh sebagai Bitmap), Tahap 3 (layar pilih area, menghasilkan Bitmap potongan di memori; mode navigasi gestur belum diuji), Tahap 4 (server FastAPI dummy, kartu status, uji koneksi USB/hotspot/Wi-Fi rumah; Wi-Fi kampus dan mode navigasi gestur belum diuji), Tahap 5, Sesi 5.1–5.4: kerangka pipeline server, RapidOCR, database cek fakta, pengukuran API LLM, pembersih teks UI (sudah dipakai /analisis), serta detektor ciri regex, penggabungan ciri, template penjelasan, dan klaim heuristik (baru dipakai di python -m app.cek; /analisis masih memakai tingkat dan ciri dummy sampai Sesi 5.5)

Perbarui bagian ini setiap kali developer menyatakan sebuah tahap selesai.

## Aturan kerja

1. Kerjakan hanya cakupan tahap aktif. Jangan menambahkan fitur, izin, dependensi, atau kerangka kode untuk tahap berikutnya, termasuk kelas kosong dan komentar TODO.
2. Sebelum menulis kode untuk tahap baru, tampilkan rencana singkat (file yang dibuat atau diubah beserta fungsinya) dan tunggu persetujuan developer.
3. Developer belum berpengalaman membuat aplikasi Android. Setelah perubahan, jelaskan dalam Bahasa Indonesia apa yang dibuat dan kenapa. Beri komentar singkat berbahasa Indonesia hanya pada konsep Android yang tidak jelas dari kodenya.
4. Semua teks yang tampil ke pengguna ditulis di `res/values/strings.xml` dalam Bahasa Indonesia semi-formal yang ramah. Teks UI menghindari kata ganti orang kedua (misalnya "kamu", "Anda", "-mu").
5. Pastikan build berhasil sebelum menyatakan pekerjaan selesai.
6. Jika ada keputusan yang tidak dibahas di rancangan, tanyakan dulu. Jangan menebak.
7. Proyek ini tidak memakai `AccessibilityService` dalam bentuk apa pun.
8. Hanya developer yang menjalankan perintah git yang mengubah repositori (add, commit, push, pull, merge, rebase, reset, stash, checkout/switch branch, tag, dan sejenisnya). Claude hanya boleh memakai perintah git yang membaca, seperti `git status`, `git diff`, dan `git log`. Saat pekerjaan siap di-commit, tulis ringkasan perubahan dan usulan pesan commit di chat, lalu developer yang menjalankannya.

## Kebijakan kode referensi

Proyek open source di `docs/REFERENSI.md` dipakai sebagai bahan belajar dan sumber pola.

- Ambil hanya bagian yang dibutuhkan tahap aktif. Jangan menyalin file utuh, modul, kelas utilitas, atau kode yang tidak dipakai.
- Periksa lisensi setiap repositori sebelum mengambil kode:
  - MIT, Apache-2.0, atau BSD: boleh diadaptasi seperlunya, dengan atribusi di komentar kode dan di `docs/REFERENSI.md`.
  - GPL atau tanpa lisensi: jangan salin baris kode. Pelajari caranya, lalu tulis implementasi sendiri.
- Salinan repositori referensi disimpan di `_referensi/`, masuk `.gitignore`, dan tidak pernah ikut di-build.

## Tech stack

- Android: Kotlin, Gradle Kotlin DSL, minSdk 26, compileSdk dan targetSdk mengikuti template Android Studio.
- UI aplikasi: Jetpack Compose (bawaan template).
- UI overlay (tombol mengambang, layar pilih area, kartu hasil): Android View biasa yang dipasang lewat `WindowManager`.
- Server (mulai tahap 4): Python FastAPI yang berjalan di laptop developer.

## Perintah

- Build debug: `./gradlew assembleDebug` (Windows: `gradlew.bat assembleDebug`)
