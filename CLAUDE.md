# CLAUDE.md — Aplikasi Cek Hoaks (nama sementara)

## Ringkasan proyek

Aplikasi Android untuk mata kuliah Venture Creation. Pengguna yang ragu dengan informasi di layar HP mengetuk tombol mengambang, memilih area layar, lalu potongan gambar dikirim ke server di laptop untuk dianalisis (Qwen-VL, database cek fakta, dan model validasi). Hasilnya berupa ciri-ciri hoaks beserta bukti dan penjelasan, bukan vonis mutlak.

Rancangan lengkap ada di `docs/RANCANGAN_PROYEK.md`. Baca dokumen itu sebelum mengerjakan tahap baru. Daftar proyek referensi dan lisensinya ada di `docs/REFERENSI.md`.

## Status tahap

- Tahap aktif: belum ditentukan (Tahap 7 selesai)
- Tahap selesai: Tahap 1 (tombol mengambang overlay), Tahap 2 (tombol bisa digeser, ketukan mengambil screenshot layar penuh sebagai Bitmap), Tahap 3 (layar pilih area, menghasilkan Bitmap potongan di memori; mode navigasi gestur belum diuji), Tahap 4 (server FastAPI dummy, kartu status, uji koneksi USB/hotspot/Wi-Fi rumah; Wi-Fi kampus dan mode navigasi gestur belum diuji), Tahap 5, Sesi 5.1–5.5: kerangka pipeline server, RapidOCR, database cek fakta, pengukuran API LLM, pembersih teks UI, detektor ciri, template, klaim; /analisis memakai pipeline sungguhan (pencarian e5, LLM Groq dengan cadangan Gemini, tingkat buatan sendiri); Sesi 5.6 (evaluasi 138 gambar berlabel dengan set uji beku; profil ambang `akhir` sebagai bawaan server dan `lama` lewat `CEKHOAKS_PROFIL_AMBANG=lama`; teruji HP 2026-10-19), Tahap 6 (kartu hasil lengkap, keadaan khusus, onboarding privasi, fixture debug; teruji HP tema gelap dan terang), Sesi 6.1 (teks perbandingan per penyebab dan penyeragaman istilah; teruji HP 2026-10-19), Tahap 7 (kolom alamat server: normalisasi skema dan port, teks bantuan alamat lokal/online; teruji HP 2026-10-23)

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

## Harness
- **Spec**:
  - file: docs/RANCANGAN_PROYEK.md (kontrak API: docs/API.md; referensi dan lisensi: docs/REFERENSI.md)
  - log deviasi: docs/RANCANGAN_PROYEK.md (keputusan dicatat di bagian tahap/sesi masing-masing, butir terbuka di "Catatan terbuka"; tidak ada file log terpisah)
- **Area kritis**:
  - logika tingkat dan pemeriksaan ciri di `server/app/pipeline/`;
  - kontrak API: `docs/API.md`, `server/app/skema.py`, `KontrakApiTest`, dan model data respons di Android;
  - aturan privasi: apa yang disamarkan, dikirim ke LLM, atau ditulis ke log;
  - teks UI yang menyangkut prinsip produk: label dan keterangan tingkat (termasuk "bukan jaminan" pada `tidak_ditemukan`), teks onboarding tentang data yang dikirim, larangan kata ganti orang kedua, larangan persentase keyakinan, dan larangan menyatakan informasi "benar"/"fakta".
- **Perintah** (shell tool Bash = Git Bash/MINGW64; semua perintah dijalankan dari root repo):
  - test: `(cd server && .venv/Scripts/python -m pytest -m "not rapidocr")`
  - test lengkap (RapidOCR sungguhan): `(cd server && .venv/Scripts/python -m pytest)`
  - test Android: `JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" ./gradlew testDebugUnitTest`
  - run: `(cd server && .venv/Scripts/python -m app)`; hanya dijalankan pemilik di jendela PowerShell terpisah, agent tidak menjalankannya
  - lint: `JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" ./gradlew lintDebug`
  - build: `JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" ./gradlew assembleDebug`
  - baseline (2026-10-15, commit 5b72189): pytest tanpa rapidocr 757 lulus (5 deselected); pytest lengkap 762 lulus; tes unit Android 68 lulus (0 gagal, 0 dilewati); lint 0 error, 22 warning; build berhasil
- **Resource berat**:
  - Gradle (build, test, lint): satu per satu, tidak pernah paralel;
  - server (port 8000, RAM tambahan sekitar 1,5 GB untuk pencarian e5);
  - pytest dengan marker `rapidocr`;
  - panggilan API LLM sungguhan (Groq/Gemini, termasuk alat di `server/alat/`): dibatasi per tugas, batasnya ditentukan di prompt tugas, dengan jeda minimal 8 detik antarpanggilan;
  - HP lewat adb: hanya tersedia setelah pemilik menyatakan HP sudah tersambung.
  - output adb yang bisa memuat data aplikasi lain (`dumpsys notification`, `dumpsys activity`, `logcat`, `uiautomator dump` di luar aplikasi CekHoaks) wajib disaring ke `com.example.cekhoaks` sebelum ditampilkan, misalnya dengan `grep`; screencap panel notifikasi dipotong ke notifikasi CekHoaks saja.
- **Path terlarang**:
  - dilarang dibaca dan diubah: `server/.env`;
  - hanya boleh dibaca, tidak boleh diubah atau dihapus: `server/data_lokal/`, `_referensi/`; pengecualian: berkas BARU boleh ditambahkan di `server/data_lokal/uji_hp/tahap6/` (dan subfolder `uji_hp/` lain untuk tahap berikutnya);
  - tidak boleh diubah: `server/.venv*/`, `local.properties`, `build/`, `app/build/`.
- **Install/unduh**: dilarang tanpa izin
- **Branch**:
  - default: main
  - prefix run: tidak ada. Tanpa branch run dan tanpa worktree; semua agent bekerja langsung di working tree pada `main`. Hanya pemilik yang menjalankan perintah git yang mengubah repo (commit dilakukan pemilik); agent hanya boleh `git status`, `git diff`, dan perintah baca lainnya.
- **State**:
  - path: .orkestrasi/
  - commit: tidak
- **Paralel maksimal**: 3 (Gradle tetap satu per satu)
