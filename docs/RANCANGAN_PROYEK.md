# Rancangan Proyek: Aplikasi Cek Hoaks dengan Tombol Mengambang

> Nama produk masih sementara. Dokumen ini menjadi acuan untuk seluruh tahap pengerjaan. Jika ada keputusan yang berubah, perbarui dokumen ini terlebih dahulu.

## 1. Latar belakang

Proyek ini dibuat untuk mata kuliah Venture Creation dengan tema: masyarakat sering menemukan informasi menarik di media sosial, tetapi kesulitan mengetahui apakah informasi tersebut benar. Pendekatannya menggabungkan technopreneur dan edupreneur: teknologi membantu pengguna mengecek informasi, sekaligus mengajari mereka mengenali ciri-ciri hoaks sendiri.

Produk akan dipamerkan dalam showcase sekitar 7-8 minggu dari awal pengerjaan dan dikerjakan oleh satu developer. Dosen menyetujui penggunaan model open source seperti Qwen dan menyarankan bentuk aplikasi HP dengan tombol mengambang.

## 2. Prinsip produk

1. **Pemandu, bukan hakim.** Sistem menunjukkan ciri-ciri yang mencurigakan beserta buktinya. Sistem tidak pernah menyatakan sebuah informasi "benar" hanya berdasarkan pendapat AI.
2. **Bukti di atas tebakan.** Kesimpulan paling kuat hanya diberikan jika klaim cocok dengan artikel cek fakta yang sudah terbit.
3. **Belajar sambil memakai.** Pengguna diajak menilai terlebih dahulu, lalu penilaiannya dibandingkan dengan temuan sistem.
4. **Satu ketukan dari tempat keraguan muncul.** Pengguna tidak perlu berpindah aplikasi untuk mengecek.
5. **Privasi.** Hanya area yang dipilih pengguna yang dikirim, dan gambar tidak disimpan.

## 3. Pengguna dan model bisnis

Pengguna mencakup semua kalangan, dari pelajar, mahasiswa, sampai orang tua. Karena itu UI harus jelas, tombol berukuran besar, teks mudah dibaca, dan bahasa yang dipakai adalah Bahasa Indonesia semi-formal.

Model bisnis versi awal: gratis untuk pengguna individu, dengan segmen pembayar pertama berupa institusi pendidikan (sekolah dan kampus) yang membayar modul literasi digital dan dashboard perkembangan kemampuan siswa.

Platform MVP hanya Android. iOS tidak mengizinkan tombol di atas aplikasi lain maupun screenshot di latar belakang, sehingga masuk roadmap dalam bentuk share sheet.

## 4. Alur pengguna (MVP lengkap)

1. Pengguna membuka aplikasi, memberikan izin yang dibutuhkan, lalu mengaktifkan tombol mengambang.
2. Saat membaca konten di aplikasi lain dan merasa ragu, pengguna mengetuk tombol mengambang.
3. Tombol disembunyikan sesaat dan layar diambil.
4. Layar pilih area muncul: tampilan layar dibekukan dengan lapisan gelap, pengguna menggeser dan mengatur ukuran kotak seleksi, lalu menekan "Cek Sekarang" atau "Batal".
5. Hanya potongan area yang dikirim ke server. Screenshot penuh langsung dibuang dari memori.
6. Selama server menganalisis, kartu kecil menampilkan pertanyaan sekali ketuk: "Menurutmu informasi ini: Percaya / Ragu / Tidak percaya?" Waktu tunggu analisis dimanfaatkan untuk bagian edukasi ini.
7. Kartu hasil singkat muncul di atas layar: tingkat indikasi dan ciri utama yang ditemukan.
8. Tombol "Pelajari lebih lanjut" membuka aplikasi dan menampilkan rincian setiap ciri beserta bukti dan penjelasannya, artikel cek fakta yang cocok, serta perbandingan dengan penilaian pengguna.
9. Di dalam aplikasi juga tersedia **mode Latih**: simulasi feed berisi hoaks yang sudah dibantah secara resmi, lengkap dengan skor dan penjelasan.

## 5. Arsitektur sistem

```
[HP Android]                                    [Laptop developer, GPU NVIDIA 6 GB]
Tombol mengambang (overlay)                      FastAPI
  -> ambil layar (MediaProjection)                 -> Qwen-VL via Ollama: baca teks, ekstrak klaim,
  -> pilih area (overlay crop)                        deteksi ciri dari daftar tetap (output JSON)
  -> kirim potongan gambar (HTTP) ---------------> -> pencocokan klaim dengan database cek fakta
                                                      (embedding + pgvector)
                                                   -> validasi ciri: aturan + classifier IndoBERT
  <- kartu hasil (overlay) <---------------------- -> logika tingkat indikasi (kode sendiri) -> JSON
```

Koneksi HP ke laptop bisa lewat tiga cara: USB dengan `adb reverse`, Wi-Fi yang sama, atau hotspot dari HP. Alamat server diatur di layar utama aplikasi. Saat showcase, gunakan hotspot sendiri, USB, atau tunnel (ngrok atau Cloudflare Tunnel), dan jangan bergantung pada Wi-Fi kampus. Langkah untuk setiap cara ada di `server/README.md`.

## 6. Komponen aplikasi Android

| Komponen | Tanggung jawab | Tahap |
|---|---|---|
| `MainActivity` (Compose) | Status izin, mengaktifkan dan mematikan tombol; nantinya rincian hasil dan mode Latih | 1, 7 |
| `FloatingButtonService` (foreground service) | Memasang dan melepas tombol overlay; nantinya menyimpan sesi MediaProjection | 1, 2 |
| Pengambil layar | MediaProjection, VirtualDisplay, ImageReader untuk menghasilkan Bitmap layar penuh | 2 |
| Overlay pilih area | View layar penuh berisi gambar beku, lapisan gelap, kotak seleksi, tombol Batal dan Cek Sekarang | 3 |
| Klien API | Mengirim potongan gambar ke server (multipart) dan menerima JSON | 4 |
| Kartu status dan hasil | Overlay kartu kecil: status analisis, pertanyaan sikap, hasil singkat | 4, 6 |

## 7. Komponen server (mulai tahap 4)

- **Framework:** Python FastAPI, satu endpoint utama untuk menerima gambar.
- **Model vision:** Qwen-VL ukuran kecil yang dikuantisasi (misalnya Qwen2.5-VL 3B atau Qwen3-VL 4B), dijalankan dengan Ollama. Pilih yang muat di VRAM 6 GB dan cek ketersediaannya saat tahap 5. Qwen hanya bertugas membaca teks, merangkum klaim, dan menandai ciri dari daftar tetap. Qwen tidak menentukan kesimpulan akhir.
- **Pencocokan cek fakta:** embedding `multilingual-e5-base` (wajib memakai awalan `query: ` dan `passage: `), disimpan di PostgreSQL dengan pgvector. Cadangan: `multilingual-e5-small` jika lambat, `bge-m3` jika kurang akurat.
- **Validator ciri:** aturan (regex dan daftar kata kunci) ditambah classifier multi-label hasil fine-tuning sendiri (IndoBERTweet untuk bahasa media sosial atau IndoBERT base). Bila perlu, diekspor ke ONNX int8.
- **OCR pembanding (opsional):** PaddleOCR untuk memeriksa teks yang dibaca Qwen.
- **Penjelasan ciri:** teks template yang ditulis sendiri untuk setiap ciri, bukan dibuat oleh LLM.
- **Privasi:** gambar diproses di memori dan tidak disimpan maupun dicatat di log.

### Format respons

Kontrak API (endpoint, field, dan kode galat) ditetapkan di tahap 4 dan didokumentasikan di `docs/API.md`. Tahap 5 mengisi kontrak yang sama dengan hasil analisis sungguhan. Perbedaan dari draf awal:
- `bukti` berupa daftar, karena satu ciri bisa muncul lebih dari sekali.
- Setiap artikel cek fakta punya `label` (kesimpulan artikel) dan `tanggal` terbit.
- Gambar tanpa teks yang terbaca dijawab dengan galat `teks_tidak_terbaca`, bukan tingkat "tidak ditemukan".
- Teks peringatan "bukan jaminan kebenaran" ada di aplikasi (`strings.xml`), tidak dikirim server.

## 8. Daftar ciri hoaks (draf)

Daftar ini dipakai bersama oleh sistem dan pertanyaan kepada pengguna, sehingga hasilnya bisa dibandingkan. Finalisasi beserta teks penjelasannya dilakukan di tahap 5.

| id | Ciri | Deteksi utama |
|---|---|---|
| `ajakan_menyebarkan` | Ajakan menyebarkan ("sebarkan", "viralkan") | Aturan |
| `desakan_waktu` | Desakan waktu ("sebelum dihapus", "segera") | Aturan + Qwen |
| `kapital_tanda_seru` | Huruf kapital dan tanda seru berlebihan | Aturan |
| `link_mencurigakan` | Tautan pemendek atau tautan tidak jelas | Aturan |
| `sumber_tidak_jelas` | Tidak menyebut sumber yang bisa dicek | Qwen + aturan |
| `judul_clickbait` | Judul clickbait | Classifier (CLICK-ID) + Qwen |
| `bahasa_provokatif` | Bahasa provokatif, memancing emosi atau panik | Classifier + Qwen |
| `pernah_dibantah` | Klaim serupa sudah dibantah media cek fakta | Pencocokan embedding |

## 9. Tingkat indikasi (draf logika)

1. Ada artikel cek fakta dengan kemiripan di atas ambang, dan artikel tersebut menyatakan klaimnya salah atau hoaks: **Indikasi kuat hoaks**.
2. Tidak ada artikel yang cocok, tetapi ditemukan beberapa ciri berkeyakinan tinggi: **Perlu hati-hati**.
3. Selain itu: **Tidak ditemukan indikasi hoaks**, disertai pesan bahwa ini bukan jaminan kebenaran dan saran untuk mengecek sumbernya.

Keyakinan ciri dianggap tinggi jika terdeteksi oleh aturan, atau oleh minimal dua sumber deteksi. Nilai ambang dan jumlah ciri ditentukan dengan data uji di tahap 5. Perbandingan antara penilaian pengguna dan temuan sistem cukup memakai logika perbandingan himpunan, tanpa LLM.

## 10. Data dan lisensi (untuk tahap 5)

| Data | Kegunaan | Catatan lisensi |
|---|---|---|
| API Yudistira TurnBackHoax (Mafindo) | Database artikel cek fakta | Cek status API dan minta izin kepada Mafindo |
| CLICK-ID (15.000 judul berlabel) | Latih deteksi clickbait | CC BY 4.0, boleh komersial dengan atribusi |
| Dataset Ibrohim & Budi 2019 (tweet ujaran kebencian) | Latih deteksi bahasa provokatif | CC BY-NC-SA 4.0, hanya untuk prototipe; versi komersial perlu izin atau data sendiri |
| 300-500 narasi hoaks berlabel sendiri | Data uji realistis, tambahan data latih, konten mode Latih | Diambil dari artikel cek fakta yang sudah terbit |

## 11. Spesifikasi visual (dari prototipe)

- **Warna:** utama `#0F766E`, aksen `#F97316`, teks utama `#0F172A`, teks sekunder `#64748B`.
- **Tombol mengambang:** lingkaran 56dp berwarna utama dengan opacity sekitar 93%, ikon perisai centang putih 26dp, bayangan halus, menempel di tepi kanan dengan jarak 14dp, posisi awal sekitar 40% tinggi layar.
- **Layar pilih area:** kilatan putih 150 ms saat layar diambil, lalu gambar layar beku dengan lapisan gelap `#080F1A` opacity sekitar 68% di luar seleksi. Kotak seleksi bergaris putih 3dp dengan sudut membulat 8dp dan cincin hijau muda tipis di luarnya. Kotak awal berada di tengah (80% lebar, 40% tinggi layar), dan ukuran minimumnya 96dp. Pegangan sudut berupa titik putih 16dp bergaris warna utama. Pegangan sisi berupa garis pendek putih yang lebih samar. Area sentuh semua pegangan 48dp. Panel bawah berisi kotak instruksi gelap, tombol teks "Pilih seluruh layar", lalu tombol "Batal" (sekunder) dan "Cek Sekarang" (warna aksen) setinggi 52dp. Panel memudar selama jari mengatur kotak dan muncul lagi setelah jari diangkat.
- **Perilaku layar pilih area:** seret di luar kotak untuk menggambar kotak baru, seret di dalam kotak untuk memindahkannya, dan seret sudut atau sisi untuk mengubah ukurannya. Kotak tidak bisa keluar dari batas layar. Tombol Back sama dengan Batal. Kalau layar diputar, pemilihan dibatalkan.
- **Kartu status:** latar putih, sudut membulat 20dp, thumbnail potongan 72dp, indikator loading, teks "Sedang menganalisis...", tombol "Batal" yang benar-benar membatalkan permintaan ke server. Prototipe memakai label "Tutup", tetapi diganti "Batal" agar sesuai dengan tindakannya. Setelah hasil atau galat tampil, tombol yang sama berlabel "Tutup". Galat yang berkaitan dengan alamat server (belum diatur atau tidak terjangkau) punya tombol tambahan "Buka pengaturan".
- **Font:** Plus Jakarta Sans; untuk sementara boleh memakai sans-serif bawaan sistem.
- **Prototipe interaktif:** https://claude.ai/artifact/WQgUGxKrXNEvJrbqK3w7kj (hanya bisa dibuka oleh pemilik akun; jika tidak bisa diakses, gunakan spesifikasi di atas).

## 12. Proyek referensi open source

| Repositori | Lisensi | Dipakai untuk | Tahap | Catatan |
|---|---|---|---|---|
| https://github.com/ervareza/screen-translator | MIT | Overlay `TYPE_APPLICATION_OVERLAY`, notifikasi foreground service dengan aksi berhenti, MediaProjection, perbaikan Android 14/15 | 1-2 | Paling mirip konsepnya, tetapi pemicu tangkap layarnya lewat layanan aksesibilitas (`InactivityAccessibilityService`); bagian itu jangan diikuti |
| https://github.com/SavinduK/SnapCrop | MIT menurut README (file `LICENSE` tidak disertakan); diperlakukan sebagai MIT | Pola pasang/lepas overlay dan lapisan crop transparan | 1, 3 | README mencantumkan izin tampil di atas aplikasi lain (`SYSTEM_ALERT_WINDOW`), tetapi berdasarkan kodenya overlay dipasang dengan `TYPE_ACCESSIBILITY_OVERLAY` dari layanan aksesibilitas, dan pemicunya juga lewat layanan aksesibilitas. Bagian itu jangan diikuti |
| https://github.com/EdwardSierra/ScreenshotApp | GPLv3 | Alur ambil layar penuh lalu crop, penyimpanan izin screen capture | 2-3 | Pemicunya Quick Settings tile. Jangan salin kode kecuali aplikasi dirilis sebagai GPLv3 (diputuskan di awal tahap 2) |
| https://github.com/cvzi/ScreenshotTile | GPLv3 | Referensi matang: screenshot area tertentu, MediaProjection di berbagai versi Android | 2-3 | Jangan salin kode kecuali aplikasi dirilis sebagai GPLv3. Tombol mengambangnya bergantung pada layanan aksesibilitas (`TYPE_ACCESSIBILITY_OVERLAY`); jangan ikuti pendekatan itu |
| https://github.com/mtsahakis/MediaProjectionDemo | "Do whatever you want License." (tidak standar) | Dasar MediaProjection API | 2 | Kode lama, hanya untuk memahami konsep |

Proyek ini memasang tombol mengambang dengan `SYSTEM_ALERT_WINDOW` + `TYPE_APPLICATION_OVERLAY` dari foreground service biasa, cara yang tidak dipakai oleh referensi mana pun. Rincian file dan kode yang diambil ada di `docs/REFERENSI.md`. Kebijakan penggunaan kode referensi dijelaskan di `CLAUDE.md`.

## 13. Tahapan pengerjaan

| Tahap | Cakupan | Selesai jika | Perkiraan |
|---|---|---|---|
| 1 | Tombol mengambang overlay: izin tampil di atas aplikasi lain, foreground service, tombol tampil di aplikasi lain, ketukan tanpa aksi | Tombol tampil stabil di atas aplikasi lain dan bisa diaktifkan serta dimatikan | Minggu 1 |
| 2 | Tombol bisa digeser vertikal di tepi kanan; ketukan mengambil layar dengan MediaProjection; tombol disembunyikan saat pengambilan | Bitmap layar penuh tersedia di memori | Minggu 2 |
| 3 | Overlay pilih area sesuai prototipe | Bitmap potongan sesuai kotak seleksi; screenshot penuh dibuang | Minggu 2-3 |
| 4 | Server FastAPI dummy dan kartu status | HP mengirim potongan gambar dan menerima respons dummy dari laptop | Minggu 3 |
| 5 | Pipeline analisis di server | Respons JSON sesuai format final, diuji dengan data uji | Minggu 3-5 |
| 6 | Pertanyaan sikap saat menunggu dan kartu hasil singkat | Alur dari ketukan sampai hasil berjalan utuh | Minggu 5-6 |
| 7 | Aplikasi utama: rincian hasil, perbandingan penilaian, mode Latih | Mode Latih berisi minimal 10 konten | Minggu 6-7 |
| 8 | Uji di beberapa HP, koneksi showcase, materi demo | Demo lancar tanpa bergantung pada internet kampus | Minggu 7-8 |

Pengumpulan data dan fine-tuning classifier dikerjakan paralel mulai minggu 2 di luar proyek Android.

### Catatan teknis untuk tahap berikutnya

- **Tahap 2 (Android 14 ke atas):** persetujuan screen capture harus diminta untuk setiap sesi; intent hasil persetujuan tidak boleh dipakai ulang; `MediaProjection.Callback` wajib didaftarkan sebelum `createVirtualDisplay`; `createVirtualDisplay` tidak boleh dipanggil lebih dari sekali pada objek MediaProjection yang sama; foreground service bertipe `mediaProjection` dimulai setelah persetujuan diperoleh dan sebelum `getMediaProjection`. Di dialog persetujuan, pengguna bisa memilih "satu aplikasi" atau "seluruh layar", jadi arahkan untuk memilih seluruh layar.
- **Tahap 3 (selesai):**
  - `OverlayPilihArea.kt` memasang jendela `TYPE_APPLICATION_OVERLAY` selebar layar fisik: `FLAG_LAYOUT_IN_SCREEN` dan `FLAG_LAYOUT_NO_LIMITS`, cutout `ALWAYS` (API 30+) atau `SHORT_EDGES` (API 28-29), dan `fitInsetsTypes = 0` (API 30+).
  - Jendela ini bisa menerima fokus agar tombol Back sampai. Back ditangani lewat `KeyEvent` dan `OnBackInvokedCallback` (Android 13+).
  - `CropSelectionView.kt` menggambar layar beku dan menangani gestur.
  - Perhitungan kotak dan pemetaan koordinat view ke piksel Bitmap ada di `GeometriSeleksi.kt` dan diuji di `GeometriSeleksiTest.kt`.
  - Screenshot penuh di-`recycle()` setelah dipotong maupun dibatalkan. Potongan hanya ditampilkan sebagai thumbnail sementara, lalu ikut di-`recycle()`. Tidak ada gambar yang ditulis ke disk.
  - Selama overlay terbuka, ketukan tombol mengambang diabaikan.
  - Rotasi (termasuk putaran 180°) dipantau lewat `DisplayManager` dan membatalkan pemilihan.
  - **Hasil verifikasi otomatis:** `assembleDebug` berhasil, 27 unit test di `GeometriSeleksiTest` lulus, dan lint tidak menemukan peringatan baru.
  - **Hasil uji manual:** Samsung Galaxy A55 5G, Android 16, mode navigasi 3 tombol. Semua uji di daftar bawah lulus di mode ini. Potongan di pojok status bar dan navigation bar pas, gambar beku sejajar dengan layar asli, Back berfungsi, dan tidak ada sentuhan yang membuka layar Home.
  - **Belum diuji:** mode navigasi gestur, termasuk risiko seretan di dekat tepi bawah terbaca sebagai gestur Home dan Back lewat gestur geser dari tepi. Daftar uji perlu diulang di mode gestur.
  - **Daftar uji manual** (pantau Logcat dengan filter `CekHoaks`; setiap pemotongan mencatat `Potongan: L x T dari (x, y)`):
    - [x] Pojok kiri atas (area status bar): potongan berisi jam dan ikon status bar secara utuh, tidak bergeser.
    - [x] Pojok kanan bawah (area navigation bar): potongan sampai tepi paling bawah layar; di log, `x + L` sama dengan lebar layar dan `y + T` sama dengan tinggi layar.
    - [x] Gambar beku sejajar dengan layar asli, tidak "melompat", termasuk di HP berponi atau berlubang kamera. Tidak muncul log `Ukuran view ... berbeda dari tangkapan ...`.
    - [x] Uji di atas dengan navigasi 3 tombol: tidak ada sentuhan yang membuka layar Home.
    - [ ] Uji di atas dengan navigasi gestur: catat apakah menyeret di dekat tepi bawah terbaca sebagai gestur Home, dan seberapa mengganggu.
    - [x] Keempat sudut dan keempat sisi: hanya tepi yang dipegang yang bergerak; kotak berhenti di ukuran minimum 96dp dan di tepi layar.
    - [x] Pindah kotak ke keempat tepi layar; menyeret di luar kotak menggambar kotak baru; ketukan sekali di luar kotak tidak menghapus kotak lama.
    - [x] Panel bawah memudar saat jari menggeser dan muncul lagi setelah jari diangkat.
    - [x] "Pilih seluruh layar" menghasilkan potongan seukuran layar penuh dari `(0, 0)`.
    - [x] Batal lewat tombol Batal dan lewat tombol Back ◁: overlay tertutup, tombol mengambang muncul lagi, aplikasi di bawahnya bisa disentuh dan diketik normal.
    - [ ] Batal lewat gestur Back (geser dari tepi kiri atau kanan, mode navigasi gestur).
    - [x] Rotasi layar saat overlay terbuka: overlay tertutup tanpa crash, tombol mengambang muncul lagi.
    - [x] Ketuk tombol mengambang sekitar 5 kali dengan cepat: hanya satu layar pilih area yang muncul.
    - [x] Proses cek diulang 10 kali (campuran Cek dan Batal): tanpa crash, dan grafik memori di Profiler tidak terus naik.
    - [x] Tombol cek dimatikan dari notifikasi saat overlay terbuka: overlay ikut tertutup tanpa crash.
- **Tahap 4 (selesai):**
  - Kontrak API ada di `docs/API.md`. Server dummy ada di `server/`, dengan cara menjalankan dan tiga cara koneksi di `server/README.md`.
  - Server membaca body sendiri (maksimal 8 MB) lalu mem-parse multipart di memori dengan python-multipart, karena `UploadFile` bawaan Starlette menulis unggahan di atas 1 MB ke file sementara. Ada pytest yang memastikan tidak ada file yang ditulis. Jeda buatan 1-3 detik memeriksa apakah klien memutus koneksi, sehingga Batal di HP terlihat di log server.
  - Hasil bisa dipaksa lewat `PAKSA_TINGKAT` (termasuk `teks_tidak_terbaca`). Kalau kosong, hasil bergiliran.
  - Alamat server disimpan di SharedPreferences (`PengaturanServer.kt`), bawaannya kosong. Alamat divalidasi dan dirapikan ke bentuk `http://host:port`. Bagian "Pengaturan server" di layar utama berisi tombol Uji koneksi (`/health`) dan pilihan cepat USB (`http://127.0.0.1:8000`).
  - HTTP tanpa TLS hanya diizinkan di build debug, lewat `app/src/debug/res/xml/network_security_config.xml` yang dipasang oleh `app/src/debug/AndroidManifest.xml`. Build release tetap memblokirnya dan menampilkan pesan galat.
  - Alur setelah "Cek Sekarang": salinan kecil potongan dibuat untuk thumbnail kartu, lalu kartu "Sedang menganalisis…" tampil dan status berubah menjadi `MENGIRIM` (ketukan tombol mengambang diabaikan tanpa pesan). Potongan disandikan ke JPEG di `Dispatchers.Default` (sisi terpanjang maksimal 2000 px, kualitas 90) lalu langsung di-`recycle()`, kemudian dikirim dengan OkHttp. Batal memanggil `Call.cancel()`. Potongan juga dibuang jika pekerjaan dibatalkan sebelum sempat berjalan (`invokeOnCompletion`). Thumbnail dibuang saat kartu ditutup.
  - Kartu hasil sementara hanya menampilkan tingkat dan jumlah ciri. Kartu hasil lengkap dikerjakan di tahap 6. Thumbnail 1,5 detik dari tahap 3 sudah dihapus.
  - Timeout koneksi dibedakan menjadi dua: gagal menyambung dalam 5 detik berarti "server tidak terjangkau", sedangkan sudah tersambung tetapi tidak dijawab dalam 60 detik berarti "server terlalu lama menjawab". Pembedanya adalah `EventListener` OkHttp.
  - **Hasil verifikasi otomatis:** `assembleDebug` dan `assembleRelease` berhasil. 51 unit test Android lulus (`KlienApiTest` dengan MockWebServer, `KontrakApiTest`, `PengaturanServerTest`, `PenyandiJpegTest`, dan 27 test lama). 24 pytest server lulus. Lint tidak menemukan peringatan baru. Merged manifest release tidak memuat `networkSecurityConfig`.
  - **Hasil uji manual:** Samsung Galaxy A55 5G, Android 16, navigasi 3 tombol.
    - USB (`adb reverse`): uji koneksi berhasil; giliran kuat → hati_hati → tidak_ditemukan sesuai; keempat nilai `PAKSA_TINGKAT` berhasil, termasuk `teks_tidak_terbaca` (422); Batal tercatat "dibatalkan klien" di log server; ketukan berulang saat `MENGIRIM` diabaikan; kartu hasil tertutup dan tidak ikut tertangkap saat tombol mengambang diketuk lagi.
    - Galat: alamat kosong (diuji setelah `pm clear`, karena kolom URL menolak disimpan kosong) memunculkan kartu dengan tombol "Buka pengaturan"; server mati dan port salah memunculkan "server tidak bisa dihubungi"; `PAKSA_TINGKAT` salah ketik (500) memunculkan pesan galat ramah tanpa crash.
    - Hotspot HP dan Wi-Fi rumah: uji koneksi dan cek berhasil; IP salah memunculkan "tidak terjangkau", bukan "terlalu lama menjawab".
    - Memori (Profiler, Live Telemetry, 10 kali cek campuran): tidak ada pola naik bertahap. Native kembali ke kisaran awal (sekitar 24-30 MB); lonjakan Graphics saat overlay terbuka turun lagi setelah ditutup.
    - File: `run-as ls -R` tidak menemukan file gambar di HP; tidak ada file gambar baru di folder server.
    - **Belum diuji:** Wi-Fi kampus dan mode navigasi gestur.
  - **Daftar uji manual** (Logcat filter `CekHoaks`, log server di jendela PowerShell):
    - [x] Uji koneksi lewat USB (`adb reverse`): "Tersambung. Versi server: 0.4.0".
    - [x] Uji koneksi lewat hotspot HP.
    - [x] Uji koneksi lewat Wi-Fi yang sama.
    - [x] Alamat salah format (misalnya `http://192.168.1.5:8000/analisis`): pesan format belum benar, alamat tidak tersimpan.
    - [x] Cek dengan `PAKSA_TINGKAT` = `kuat`, `hati_hati`, `tidak_ditemukan`: judul dan jumlah ciri di kartu sesuai.
    - [x] Cek dengan `PAKSA_TINGKAT=teks_tidak_terbaca`: kartu galat menyarankan memilih area dengan tulisan yang lebih jelas, tanpa tombol "Buka pengaturan".
    - [x] Tanpa `PAKSA_TINGKAT`: tiga cek berturut-turut menghasilkan kuat, hati-hati, lalu tidak ditemukan.
    - [x] Alamat server dikosongkan (hapus data aplikasi): kartu galat dengan tombol "Buka pengaturan" yang membuka aplikasi dan menggulir ke bagian Pengaturan server.
    - [x] Server dimatikan: kartu galat "Server belum bisa dihubungi" dengan tombol "Buka pengaturan", tidak crash, dan tombol mengambang bisa dipakai lagi.
    - [x] Batal saat kartu "Sedang menganalisis…" tampil: kartu tertutup, log server menampilkan `Permintaan … dibatalkan klien`, dan tidak ada baris `tingkat …` untuk permintaan itu.
    - [x] Ketuk tombol mengambang berkali-kali saat mengirim: tidak ada layar pilih area baru, Logcat menampilkan `Ketukan diabaikan, status: MENGIRIM`.
    - [x] Ketuk tombol mengambang saat kartu hasil masih tampil: kartu tertutup dan tidak ikut tertangkap di layar pilih area.
    - [x] Tombol cek dimatikan dari notifikasi saat mengirim: kartu tertutup tanpa crash.
    - [x] Ulangi 10 kali berturut-turut (campuran hasil, galat, dan Batal) sambil memantau Profiler: grafik memori tidak terus naik.
    - [x] "Pilih seluruh layar" lalu cek: log `Mengirim JPEG … byte` menunjukkan ukuran wajar, dan log server menunjukkan dimensi dengan sisi terpanjang maksimal 2000.
    - [x] Tidak ada file gambar baru: `adb shell run-as com.example.cekhoaks ls -R` hanya berisi `shared_prefs` dan folder bawaan, dan folder `server/` tidak berisi file gambar.
- **Tahap 5 (pekerjaan dari temuan tahap 4):** server sebaiknya menolak jalan sejak awal (gagal saat start dengan pesan jelas) kalau `PAKSA_TINGKAT` berisi nilai yang tidak dikenal. Saat ini nilai salah ketik baru memunculkan galat 500 pada saat cek.
- **Tahap 7 (catatan dari uji tahap 4):** skema `http://` ditambahkan otomatis, tetapi port tidak, jadi "192.168.0.101" menjadi `http://192.168.0.101` (port 80) dan gagal terhubung. Perbaikan: kolom URL diberi placeholder `http://192.168.x.x:8000`, dan kalau alamat `http://` tidak menyebut port, tambahkan `:8000` secara otomatis.
- **Tahap 8 (persiapan showcase):**
  - APK di HP harus build debug, karena HTTP tanpa TLS (cleartext) hanya diizinkan di varian itu.
  - Profil jaringan laptop harus Private (`Set-NetConnectionProfile` lewat PowerShell Administrator). Kalau tidak, HP tidak bisa menghubungi server lewat Wi-Fi atau hotspot.
  - Alamat IP laptop di hotspot HP berubah setiap kali tersambung ulang (contoh: 10.248.150.58 lalu 10.190.18.58). Setiap kali server dijalankan, cek alamat yang dicetak dan perbarui di aplikasi.
  - `adb reverse` hilang setiap kali kabel dicabut atau HP di-restart.
- **Umum:** sistem atau aplikasi tertentu (misalnya halaman pengaturan izin dan aplikasi perbankan) dapat menyembunyikan overlay. Ini perilaku normal.

## 14. Di luar cakupan MVP (roadmap)

- iOS melalui share sheet.
- Video: transkripsi audio dengan Whisper, lalu dianalisis sebagai teks.
- Pencocokan gambar dengan database hoaks memakai CLIP.
- Panduan reverse image search yang lebih lengkap.
- Dashboard institusi untuk sekolah dan kampus.
- Deteksi gambar editan atau buatan AI tidak dijanjikan, karena detektor yang ada belum cukup andal; topik ini cukup diangkat sebagai materi edukasi di mode Latih.
