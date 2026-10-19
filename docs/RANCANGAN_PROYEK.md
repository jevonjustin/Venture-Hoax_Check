# Rancangan Proyek: Aplikasi Cek Hoaks dengan Tombol Mengambang

> Nama produk masih sementara. Dokumen ini menjadi acuan untuk seluruh tahap pengerjaan. Jika ada keputusan yang berubah, perbarui dokumen ini terlebih dahulu.

## 1. Latar belakang

Proyek ini dibuat untuk mata kuliah Venture Creation dengan tema: masyarakat sering menemukan informasi menarik di media sosial, tetapi kesulitan mengetahui apakah informasi tersebut benar. Pendekatannya menggabungkan technopreneur dan edupreneur: teknologi membantu pengguna mengecek informasi, sekaligus mengajari mereka mengenali ciri-ciri hoaks sendiri.

Produk akan dipamerkan dalam showcase sekitar 7-8 minggu dari awal pengerjaan dan dikerjakan oleh satu developer. Dosen menyetujui penggunaan model open source seperti Qwen dan menyarankan bentuk aplikasi HP dengan tombol mengambang. Kemudian proyek memutuskan (Sesi 5.4a) bahwa API LLM gratis boleh dipakai untuk analisis teks, dengan batasan privasi di §2.

## 2. Prinsip produk

1. **Pemandu, bukan hakim.** Sistem menunjukkan ciri-ciri yang mencurigakan beserta buktinya. Sistem tidak pernah menyatakan sebuah informasi "benar" hanya berdasarkan pendapat AI.
2. **Bukti di atas tebakan.** Kesimpulan paling kuat hanya diberikan jika klaim cocok dengan artikel cek fakta yang sudah terbit.
3. **Belajar sambil memakai.** Pengguna diajak menilai terlebih dahulu, lalu penilaiannya dibandingkan dengan temuan sistem.
4. **Satu ketukan dari tempat keraguan muncul.** Pengguna tidak perlu berpindah aplikasi untuk mengecek.
5. **Privasi.** Hanya area yang dipilih pengguna yang dikirim ke server, dan gambar tidak disimpan. Gambar tidak pernah dikirim ke pihak ketiga. API LLM gratis boleh dipakai, tetapi yang dikirim ke penyedia hanya teks OCR yang nomor telepon, email, dan nama akunnya sudah disamarkan. LLM tidak menentukan tingkat indikasi dan tidak menyatakan informasi benar atau salah; perannya mengekstrak klaim dan menandai kandidat ciri beserta kutipan bukti yang diverifikasi server.

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
[HP Android]                                    [Laptop developer, CPU saja]
Tombol mengambang (overlay)                      FastAPI
  -> ambil layar (MediaProjection)                 -> baca teks (OCR atau Qwen-VL kecil, diputuskan
  -> pilih area (overlay crop)                        dari pengukuran di Sesi 5.2)
  -> kirim potongan gambar (HTTP) ---------------> -> bersihkan teks, ambil klaim_utama (heuristik)
                                                   -> pencocokan klaim dengan database cek fakta
                                                      (multilingual-e5, vektor NumPy di memori)
                                                   -> deteksi ciri (regex)
  <- kartu hasil (overlay) <---------------------- -> logika tingkat indikasi (kode sendiri) -> JSON
```

Laptop showcase: Lenovo, Ryzen 7 8840HS, iGPU Radeon 780M (tanpa GPU NVIDIA dan tanpa ROCm), RAM 16 GB, Windows. Karena itu seluruh pipeline dirancang untuk CPU.

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
- **Pembacaan teks:** diputuskan dari pengukuran di Sesi 5.2 pada 18 screenshot berlabel: RapidOCR bawaan dipilih setelah dibandingkan dengan RapidOCR Latin dan PaddleOCR. Pembaca teks hanya membaca teks dan tidak menentukan kesimpulan akhir.
- **Klaim utama dan kandidat ciri:** LLM lewat API (keputusan Sesi 5.4a: Groq `openai/gpt-oss-120b`, cadangan Google `gemini-3.5-flash-lite`; keputusan penerapan Sesi 5.5 di bagian Sesi 5.5). Model hanya mengusulkan klaim dan kutipan ciri; tingkat tidak pernah ditentukan model. Klaim melewati uji kesetiaan, lalu cadangan bertingkat (bukti `pernah_dibantah`, heuristik, kosong). `klaim_utama` hanya ditampilkan; kueri pencarian cek fakta tetap teks bersih hasil OCR.
- **Pencocokan cek fakta:** embedding `multilingual-e5` (wajib memakai awalan `query: ` dan `passage: `), vektor disimpan sebagai NumPy di memori. pgvector hanya disebut sebagai rencana skala besar. Ukuran model (`base` atau `small`) diputuskan dari kecepatan di CPU; `bge-m3` sebagai cadangan jika kurang akurat.
- **Deteksi ciri:** aturan (regex dan daftar kata kunci) bersama kandidat LLM yang kutipannya diverifikasi dan diperiksa pengaman struktural (§8). Classifier IndoBERT/IndoBERTweet hasil fine-tuning termasuk jalur opsional setelah Tahap 6-7 aman.
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
| `permintaan_data_rahasia` | Permintaan kode OTP atau verifikasi, PIN, kata sandi, data kartu, atau uang (transfer, QRIS, biaya admin untuk refund atau hadiah) | Regex (pola kuat; kalimat larangan seperti "JANGAN BERIKAN kode OTP" dibuang) + kandidat LLM |
| `ajakan_menyebarkan` | Ajakan menyebarkan ("sebarkan", "viralkan") | Regex (pola kuat dan lemah) + kandidat LLM |
| `desakan_waktu` | Desakan waktu ("sebelum dihapus", "segera") | Regex (pola kuat dan lemah) + kandidat LLM |
| `kapital_tanda_seru` | Huruf kapital dan tanda seru berlebihan | Regex dan hitungan sederhana + kandidat LLM |
| `link_mencurigakan` | Tautan pemendek atau tautan tidak jelas | Regex (pola kuat dan lemah) + kandidat LLM |
| `sumber_tidak_jelas` | Merujuk sumber samar tanpa nama ("katanya", "info dari grup", "forwarded") | Regex (atribusi samar); LLM hanya menyetujui atau tidak. Kutipan LLM saja dibuang (Sesi 5.5) |
| `judul_clickbait` | Judul clickbait | Kandidat LLM; regex hanya pola lemah sebagai cadangan |
| `bahasa_provokatif` | Bahasa provokatif, memancing emosi atau panik | Kandidat LLM; regex hanya pola lemah sebagai cadangan |
| `pernah_dibantah` | Klaim serupa sudah dibantah media cek fakta | Pencarian embedding di database cek fakta (bukan regex, bukan LLM) |

Arsitektur deteksi (Sesi 5.4, diperbarui Sesi 5.5): regex berperan sebagai pemeriksa dan cadangan, sedangkan LLM hanya menandai kandidat ciri beserta kutipan yang diverifikasi server terhadap teks. Kutipan yang tidak ditemukan di teks membuat ciri dibuang. Keyakinan tinggi untuk ciri yang ditemukan LLM dan regex sekaligus, atau regex dengan pola kuat; keyakinan sedang untuk ciri yang hanya ditemukan LLM dengan kutipan terverifikasi. Jika LLM gagal, hasil regex dipakai sendiri (pola kuat tinggi, pola lemah sedang). Jika LLM berhasil tetapi tidak menandai ciri yang hanya ditemukan regex lemah, ciri itu dibuang. Bukti selalu potongan persis dari `teks_terbaca` (dengan perbedaan spasi diabaikan). Penjelasan selalu dari template. Pengaman struktural pada kutipan LLM (tidak bergantung model): bukti `link_mencurigakan` harus berbentuk tautan atau domain; bukti `kapital_tanda_seru` harus didominasi huruf kapital atau memuat tanda seru berulang; bukti ciri yang hanya ditemukan LLM minimal tiga kata (kecuali tautan). Bukti yang gagal dibuang satu per satu dan ciri hilang hanya bila tidak ada bukti tersisa. Ciri `permintaan_data_rahasia` membuang kalimat larangan dan edukasi: kata larangan hanya berlaku dalam klausa yang sama dan mendahului kata kerja permintaan dalam tiga token, dan "jangan lupa", "jangan ragu", dan sejenisnya bukan larangan. Qwen dan classifier IndoBERT tidak dipakai di jalur utama; classifier tetap jalur opsional di §13.

## 9. Tingkat indikasi (logika Sesi 5.5)

Logika ada di `server/app/pipeline/tingkat.py`, sepenuhnya buatan sendiri; LLM tidak ikut menentukan. Artikel dihitung hanya bila *relevan*: bagian bobot IDF kata isi judul artikel yang muncul di teks sedikitnya 0,40 (artikel peringkat satu dengan skor sedikitnya 0,88 lolos tanpa syarat ini).

1. **Indikasi kuat hoaks:** ada artikel berlabel `salah` atau `penipuan` yang relevan, skor kemiripan sedikitnya 0,88, dan unggul lebih dari 0,02 dari semua artikel berlabel `benar`, `klarifikasi`, atau `satir`. Kalau tidak unggul, terjadi konflik: hasilnya **Perlu hati-hati** (varian `konflik`) dan `pernah_dibantah` berkeyakinan sedang.
2. **Perlu hati-hati:** artikel `salah` atau `penipuan` yang relevan di rentang skor 0,85-0,88 (varian `mirip`); artikel `satir` dengan skor sedikitnya 0,88 (varian `satir`); atau tanpa artikel, ada sedikitnya satu ciri berkeyakinan tinggi atau dua ciri berkeyakinan sedang (varian `ciri_saja`).
3. **Tidak ditemukan indikasi hoaks:** selain itu, selalu disertai keterangan bahwa ini bukan jaminan informasi benar. Bila ada artikel berlabel lain yang tampil, keterangannya memakai varian `rujukan`. Satu ciri berkeyakinan sedang yang berdiri sendiri tidak ditampilkan (tercatat di diagnostik server).

Keyakinan ciri tinggi jika terdeteksi aturan berpola kuat atau dua sumber (aturan dan LLM), sedang jika satu sumber; tidak ada angka persentase. Bukti `pernah_dibantah` adalah kalimat layar yang paling mirip dengan artikel (kata judul didahulukan). Semua ambang masih titik awal dan ditetapkan final di Sesi 5.6. Perbandingan antara penilaian pengguna dan temuan sistem cukup memakai logika perbandingan himpunan, tanpa LLM.

## 10. Data dan lisensi (untuk tahap 5)

| Data | Kegunaan | Catatan lisensi |
|---|---|---|
| API Yudistira TurnBackHoax (Mafindo) | Database artikel cek fakta | Cek status API dan minta izin kepada Mafindo |
| CLICK-ID (15.000 judul berlabel) | Latih deteksi clickbait | CC BY 4.0, boleh komersial dengan atribusi |
| Dataset Ibrohim & Budi 2019 (tweet ujaran kebencian) | Latih deteksi bahasa provokatif | CC BY-NC-SA 4.0, hanya untuk prototipe; versi komersial perlu izin atau data sendiri |
| 300-500 narasi hoaks berlabel sendiri | Data uji realistis, tambahan data latih, konten mode Latih | Diambil dari artikel cek fakta yang sudah terbit |

## 11. Spesifikasi visual (dari prototipe)

Rujukan desain satu-satunya untuk pengembangan adalah `docs/prototype/prototype.html`. Figma hanya untuk presentasi. Tautan prototipe interaktif lama (artifact) tidak dipakai lagi.

- **Warna merek:** navy `#1B3A6B` (`navy` di `colors.xml`) sebagai satu-satunya sumber warna merek untuk layar pilih area, lembar, dan onboarding; turunannya `navy_lembut` `#EAF0FA` dan `latar_lembar` `#F4F7FC`. Teks: judul `#142033`, isi `#2A3850`, redup `#4A5A72`.
- **Warna tingkat** (bg/fg untuk banner, soft/ink untuk lencana dan kotak temuan):
  - `kuat`: bg `#C7372F`, fg putih, soft `#FDECEA`, ink `#B42318`.
  - `hati_hati`: bg `#F2B01E`, fg `#3D2A00`, soft `#FFF4D6`, ink `#7A4F00`.
  - `tidak_ditemukan`: bg `#5B6F94`, fg putih, soft `#E8EDF5`, ink `#3D4F6E`. Tingkat tak dikenal memakai palet yang sama.
- **Tombol mengambang:** tetap teal `#0F766E` dengan opacity sekitar 93% (`tombol_cek_latar` = `#ED0F766E`); di luar cakupan Tahap 6. Lingkaran 56dp, ikon perisai centang putih 26dp, bayangan halus, menempel di tepi kanan dengan jarak 14dp, posisi awal sekitar 40% tinggi layar.
- **Layar pilih area:** kilatan putih 150 ms saat layar diambil, lalu gambar layar beku dengan lapisan gelap `#080F1A` opacity sekitar 68% di luar seleksi. Kotak seleksi bergaris putih 3dp dengan sudut membulat 8dp dan cincin hijau muda tipis di luarnya. Kotak awal berada di tengah (80% lebar, 40% tinggi layar), dan ukuran minimumnya 96dp. Pegangan sudut berupa titik putih 16dp bergaris navy. Pegangan sisi berupa garis pendek putih yang lebih samar. Area sentuh semua pegangan 48dp. Panel bawah berisi kotak instruksi gelap (ikon teal), tombol teks "Pilih seluruh layar", lalu tombol "Batal" (sekunder) dan "Cek Sekarang" (latar putih, teks navy) setinggi 52dp. Panel memudar selama jari mengatur kotak dan muncul lagi setelah jari diangkat.
- **Perilaku layar pilih area:** seret di luar kotak untuk menggambar kotak baru, seret di dalam kotak untuk memindahkannya, dan seret sudut atau sisi untuk mengubah ukurannya. Kotak tidak bisa keluar dari batas layar. Tombol Back sama dengan Batal. Kalau layar diputar, pemilihan dibatalkan.
- **Alur setelah "Cek Sekarang":** pilih area, lembar penilaian awal (analisis berjalan di latar), kartu memuat, lalu lembar hasil atau lembar galat. Semuanya View via WindowManager (lihat Keputusan Tahap 6).
- **Font:** sans-serif bawaan sistem (Plus Jakarta Sans butuh unduh dan belum diizinkan).

### Urutan lembar hasil

1. Banner tingkat: ikon, "HASIL ANALISIS", label tingkat, keterangan umum tingkat (`tidak_ditemukan` selalu memuat kalimat "bukan jaminan").
2. Keterangan pemeriksaan terbatas, bila `pemeriksaan_terbatas` tidak kosong.
3. Chip ringkasan: jumlah ciri dan jumlah artikel cek fakta.
4. "Inti pesan" (disembunyikan bila kosong).
5. "Artikel cek fakta": pil label, judul, sumber dan tanggal, tombol "Buka artikel" (atau "Cari judul di web" untuk `url_format_lama`).
6. "Ciri yang ditemukan": nama, teks keyakinan, bukti berkutip, penjelasan.
7. "Dibanding penilaian awal".
8. "Teks yang terbaca" (terlipat, bukti disorot).
9. "Tips" per tingkat.
10. Kaki tetap: tombol "Tutup".

### Keputusan Tahap 6

- **Varian keterangan tingkat tidak ada di respons (D3).** Server menghitung varian (ciri_saja, mirip, satir, konflik, rujukan), tetapi kontrak tidak mengirimkannya. Android memakai keterangan umum per tingkat yang ditulis agar akurat untuk semua varian. Menebak varian di HP akan menduplikasi logika area kritis server.
- **Arsitektur overlay (D4).** Tiga lembar bawah dan satu kartu memuat, semuanya View via WindowManager (aturan stack), jendela MATCH_PARENT dengan lapisan gelap dan tanpa `FLAG_NOT_FOCUSABLE` agar Back bisa ditangani. Back atau ketuk lapisan: penilaian dan memuat membatalkan analisis, hasil dan galat menutup. Activity terpisah ditolak karena prototipe menampilkan hasil di atas aplikasi lain.
- **Alur edukasi sesuai prototipe (D5).** Tiga opsi (Percaya, Ragu-ragu, Tidak percaya) dan "Lewati"; perbandingan hanya antara `tidak_ditemukan` dan bukan. Pengguna tidak memilih ciri, padahal `docs/API.md` menyebut perbandingan himpunan ciri; ini keputusan terbuka untuk pemilik. Penilaian hanya di memori service untuk satu pengecekan, tidak dikirim dan tidak disimpan. Riwayat, dashboard, statistik, dan belajar hoaks tidak dibuat.
- **Kartu memuat tanpa tiga langkah (D6).** Prototipe menampilkan langkah dengan waktu palsu; server tidak melaporkan kemajuan, jadi diganti spinner, judul, satu kalimat, dan tombol Batal agar jujur.
- **"Inti pesan" (D7).** Menggantikan "Klaim yang dicek" karena untuk obrolan penipuan dan konten edukasi istilah "klaim" kurang cocok.
- **Teks keyakinan (D8).** "Keyakinan tinggi" atau "Keyakinan sedang", tanpa persentase (prinsip produk). Nilai tak dikenal tidak ditampilkan.
- **Label artikel cek fakta (D9).** salah "SALAH", penipuan "PENIPUAN" (merah lembut), klarifikasi "KLARIFIKASI", satir "SATIR", belum_terbukti "BELUM TERBUKTI", dan benar serta nilai lain atau tak dikenal "RUJUKAN" (netral, latar `navy_lembut`). `benar` menjadi "RUJUKAN" karena UI tidak boleh menyatakan informasi "benar"; judul artikel tetap tampil sehingga kesimpulannya terbaca dari sumber. Cukup ganti satu string untuk membatalkan.
- **Nama ciri (D10).** Nama dari aplikasi untuk sembilan id terkunci (sesuai tabel `docs/API.md`), cadangan `nama` dari server, dan bila kosong "Ciri lain".
- **Tingkat TIDAK_DIKENAL (D11).** Nilai tingkat tak dikenal tidak lagi menjadi galat: banner netral "Hasil Analisis" dengan keterangan bahwa jenis hasil belum dikenali versi aplikasi ini dan bukan jaminan; rincian tetap tampil. Dikerjakan agar aplikasi tidak gagal total bila server menambah tingkat. Menyentuh kontrak Android (area kritis), jadi diverifikasi.
- **Teks perbandingan dan tips (D12).** Diambil dari prototipe tanpa kata ganti orang kedua. Tingkat tak dikenal: "Jenis hasil ini belum bisa dibandingkan dengan penilaian awal."
- **Lembar galat (D13, D22).** JPEG ditahan hanya di memori service sampai lembar ditutup (tidak ke disk). Prototipe hanya punya tiga varian; sisanya mengikuti pola yang sama.

  | Kondisi | Judul | Tindakan utama |
  |---|---|---|
  | teks_tidak_terbaca | Teks tidak terbaca | Pilih Ulang |
  | terlalu_besar | Area terlalu besar | Pilih Ulang |
  | gambar_kosong, bukan_gambar, galat penyandian | Gambar belum terkirim utuh | Pilih Ulang |
  | Tidak terjangkau | Server tidak bisa dihubungi | Coba Lagi, plus "Buka pengaturan" |
  | URL belum diatur | Alamat server belum diatur | Buka pengaturan |
  | Waktu habis | Server terlalu lama menjawab | Coba Lagi |
  | galat_server, galat_http, kode tak dikenal, null | Server sedang bermasalah | Coba Lagi |
  | Respons tidak dikenali | Jawaban server tidak dikenali | Buka pengaturan |
  | Cleartext (D22) | Alamat server tidak bisa dipakai | Buka pengaturan |

  "Pilih Ulang" mengambil layar baru lalu membuka pilih area; "Coba Lagi" mengirim ulang JPEG yang sama.
- **Onboarding (D14, D21).** Empat halaman Compose: tiga dari prototipe (halaman 1 diubah menjadi "...tetapi tidak semuanya bisa langsung dipercaya" karena prototipe memakai kata "benar"; halaman 3 menambah sifat hasil sebagai pemandu, bukan penentu benar atau salah) dan halaman 4 baru tentang apa yang dikirim (privasi). Ilustrasi prototipe diganti ikon sederhana (tidak tersedia sebagai vector). Layar izin, berhasil, dan dashboard prototipe tidak dibuat. Tampil sekali (SharedPreferences), bisa dibuka lagi dari tombol teks di layar utama. Selalu tema terang dan `dynamicColor` dimatikan agar warna merek konsisten di Samsung; "Lewati" berarti selesai.
- **Notifikasi sesi rekam layar berhenti, B3 (D15, D21).** Android tidak membedakan alasan berhenti, dan `MediaProjection.Callback.onStop` satu-satunya sinyal relevan; persetujuan harus diminta ulang tiap sesi (Android 14+), sehingga tombol tidak bisa menyala otomatis. Maka saat `onStop` dari sistem, service memasang notifikasi (channel `pemeriksaan_berhenti`, ketuk membuka MainActivity) dan menyimpan tanda; layar utama menampilkan kotak keterangan sampai tombol cek diaktifkan lagi (hilang saat service terdeteksi berjalan, bukan saat tombol diketuk, agar tidak hilang bila izin ditolak). Toast tidak dipakai karena tidak terlihat saat HP terkunci. Tanpa AccessibilityService.
- **Font sistem (D16).** Sans-serif bawaan karena Plus Jakarta Sans butuh unduh.
- **Pilih area (D16, D20).** "Cek Sekarang" putih dengan teks navy dan pegangan sudut bergaris navy sesuai prototipe; label dan tata letak Tahap 3 lainnya tetap. Cincin seleksi hijau muda dan ikon petunjuk teal tidak diubah (bukan token merek; prototipe tidak punya cincin). Tombol mengambang tetap teal.
- **Lembar hasil menutup setelah tautan dibuka (D17).** Overlay layar penuh akan menutupi browser. Hanya skema http/https yang dibuka; selain itu dialihkan ke pencarian judul.
- **Thumbnail (D18).** Selebar lembar, tinggi maksimal 120dp, fitCenter. Prototipe memakai 96x64 dengan cuplikan teks, tetapi cuplikan belum ada sebelum hasil sehingga thumbnail tampak kosong.
- **Target ketuk (D19).** Tombol teks 48dp (prototipe 44dp) demi target minimal 48dp; lembar berhenti di atas navigation bar (padding insets).
- **Perbaikan hasil verifikasi (D22).** Kalimat AI dibatasi, pemindai string diperketat, teks privasi menyebut penyamaran berbasis pola bisa terlewat dan tautan tidak disamarkan, pesan perbandingan "Percaya" tidak bergantung pada adanya ciri, judul galat cleartext tersendiri, dan opacity label banner minimal 0,95 demi kontras.
- **Fixture debug (D23).** `app/src/debug/assets/fixture` dan `AktivitasFixture` menampilkan lembar tanpa server; teks UI-nya di `app/src/debug/res/values/strings_debug.xml`. Hanya alat developer, tidak ikut rilis.
- **Tinggi lembar (D24).** Mengikuti isi (`wrap_content`) dengan batas 92% layar, bukan tinggi tetap prototipe.
- **Chip dan tambahan hasil (D25).** Chip "%d artikel cek fakta terkait" menggantikan "Cocok dengan 1 artikel cek fakta"; kartu "Pemeriksaan belum lengkap" dan bagian "Teks yang terbaca" adalah tambahan di luar prototipe.
- **Pesan perbandingan (D26).** Kedua pesan `tidak_ditemukan` memuat kalimat bukan jaminan dan tanpa kata "juga" yang terbaca mengesahkan kepercayaan pengguna.
- **Ukuran teks (D27).** Teks informatif minimal 14sp; hanya label kapital kecil dekoratif (mis. "HASIL ANALISIS", "BAGIAN YANG DIPILIH") boleh 12sp.
- **REFERENSI.md (D28).** Satu baris rujukan `ic_geser` ikut diubah ke `docs/prototype/prototype.html`.
- **Refactor internal (D29).** Akar jendela overlay dan Back diekstrak ke `AkarOverlay.kt` (dipakai juga `OverlayPilihArea`); `KartuAnalisis`, layout, drawable, dan warna kartu lama dihapus; `PesanGalat.perluPengaturan` dihapus.
- **Perbaikan review T6b (D30).** Catatan berhenti di layar utama ikut diperbarui saat service berhenti ketika aplikasi di depan; "Buka pengaturan" memanggil `startActivity` sebelum jendela overlay dilepas; JPEG dibuang dari memori segera setelah hasil sukses.
- **Warna teks layar utama di tema gelap (D32).** Ditemukan saat uji HP: teks navy langsung di atas latar layar (judul, status izin, "Cara kerja dan privasi", serta spinner dan teks "Tersambung" di pengaturan server) hampir tidak terbaca di tema gelap. Teks itu kini memakai `MaterialTheme.colorScheme.primary` (navy di tema terang, `navy_lembut` di tema gelap). Tombol navy bertulisan putih dan kotak catatan berlatar `navy_lembut` tetap memakai warna tetap karena kontrasnya aman di kedua tema. Onboarding dan semua lembar overlay selalu terang.

### Keputusan Sesi 6.1

- **Penilaian awal tetap tiga opsi (A7).** Percaya, Ragu-ragu, Tidak percaya, plus Lewati; pengguna tidak memilih ciri. Keputusan pemilik. `docs/API.md` menyebut perbandingan himpunan ciri, tetapi aplikasi cukup membandingkan penilaian dengan tingkat.
- **Label `benar` tetap "RUJUKAN" (D9).** Keputusan pemilik.
- **Statistik, riwayat, dan dashboard.** Tidak dibangun sebelum showcase; cukup di Figma.
- **Teks perbandingan per penyebab.** `hati_hati` + Percaya dibedakan menurut penyebab yang disimpulkan aplikasi dari respons, tanpa mengubah kontrak: (1) ada ciri; (2) tanpa ciri dengan artikel berlabel satir; (3) tanpa ciri dengan artikel lain; (4) umum. `tidak_ditemukan` dibedakan per penilaian (Percaya, Ragu-ragu, Tidak percaya) dan semuanya memuat kalimat bukan jaminan. `kuat` + Percaya memakai teks baru yang mengingatkan bahwa pesan meyakinkan pun bisa memakai pola hoaks. Penilaian Ragu-ragu atau Tidak percaya pada `kuat` dan `hati_hati` tidak berubah. Teks lengkap ada di `strings.xml` (`banding_pesan_*`).
- **Penyeragaman istilah.** Teks perbandingan dan keterangan tingkat memakai "indikasi hoaks"; "ciri" hanya untuk daftar ciri. Kata "benar" di teks UI hanya muncul dalam frasa "bukan jaminan informasi ini benar" (dijaga `StringResourcesTest`), sehingga `server_url_tidak_valid` menjadi "belum sesuai" dan tips `tidak_ditemukan` serta `tidak_dikenal` ikut diubah.
- **Fixture debug.** `AktivitasFixture` (debug) diberi padding system bars. Fixture baru `hati_hati_satir`, `hati_hati_artikel`, dan `hati_hati_umum` (penyebab ciri sudah dicakup `hati_hati_mirip`).

### Keputusan Sesi 5.6

- **Data berlabel.** 138 gambar di `server/data_lokal/evaluasi/` (tidak masuk repo): dev 83 untuk penyetelan, uji 55 dibekukan (hash) dan dinilai sekali di akhir. Alat `server/alat/uji_analisis/evaluasi_berlabel.py` menjalankan `orkestrator.jalankan` yang sama dengan server, dengan cache OCR, pencarian, dan LLM (hanya Groq).
- **Profil ambang.** Semua ambang ada di `konfigurasi.PROFIL_AMBANG`. Server memakai profil `akhir`; `CEKHOAKS_PROFIL_AMBANG=lama` mengembalikan perilaku commit 7742a73 (cadangan demo). Alat evaluasi memakai tabel yang sama (`--profil`), dan tes memastikan konfigurasi server sama dengan konfigurasi alat.
- **Perubahan ambang (lama → akhir):**
  - kueri e5: 256 → 512 token (hasil dev identik, menghapus risiko kueri terpotong);
  - toleransi salah eja OCR pada relevansi: mati → menyala (selisih 1 huruf untuk kata 5-6 huruf, 2 huruf untuk kata ≥ 7 huruf; hanya relevansi, tidak berlaku untuk kesetiaan klaim);
  - `kuat` lewat kombinasi: mati → menyala (artikel salah/penipuan dengan skor ≥ 0,855, relevansi ≥ 0,70, dan ≥ 4 kata isi judul ada di teks);
  - batas skor peringkat 1 yang lolos tanpa syarat relevansi: 0,88 → 0,90;
  - ambang teks: tetap 20 karakter huruf-angka (penyetelan dev sempat menaikkan ke 25; lihat butir ambang teks di bawah);
  - pemeriksaan kesetiaan klaim (angka, nama, negasi, kata pengganti, kata berat baru): mati → menyala (tidak mengubah tingkat).
- **Tetap:** `ambang_cocok` 0,88, `ambang_mirip` 0,85, `relevansi_minimum` 0,40 (0,53 menghapus satu hati_hati negatif dev tetapi juga positif asli; celahnya terlalu sempit), `selisih_konflik` 0,02. e5 tetap fp32: int8 lebih cepat dan hemat RAM, tetapi peringkat artikel sumber dev memburuk (MRR 0,914 → 0,844). Regex usulan dari dataset Kaggle tidak diadopsi (tidak mengurangi salah tandai negatif).
- **Hasil set uji (55 gambar, lama → akhir):** negatif (23) kuat 0 → 0, hati_hati 1 → 1; recall positif (31) mode biasa 30 → 29 (kuat 21 → 22), mode tanpa artikel sumber (leave-one-out) 17 → 18; peringkat artikel sumber rank@1 22/22 → 21/22 (MRR 1,000 → 0,955). Angka ini dinilai sekali dengan profil akhir saat ambang teks masih 25. Satu-satunya positif yang hilang adalah teks penipuan 24 karakter yang menjadi `teks_tidak_terbaca`.
- **Ambang teks kembali ke 20 (keputusan produk, bukan untuk menaikkan skor).** Kasusnya ditemukan dari set uji: teks penipuan asli 24 karakter ditolak ambang 25. Pemeriksaan ulang di set dev menunjukkan bahwa 25 tidak mencegah satu pun `kuat` atau `hati_hati` keliru pada konten negatif; yang tersaring hanya obrolan pendek yang di ambang 20 tetap `tidak_ditemukan` tanpa ciri (dev ev134, uji ev135). Pesan penipuan pendek (misalnya permintaan OTP) penting bagi produk, sedangkan teks pendek tanpa makna di bawah 25 karakter tidak berbahaya, jadi profil akhir memakai 20. Profil akhir dengan teks 25 → 20, dari cache tanpa LLM (penilaian ulang ini tidak menggantikan penilaian sekali di atas): set uji negatif kuat 0 → 0, hati_hati 1 → 1; recall biasa 29 → 30 dari 31 (kuat 22 → 22; teks penipuan 24 karakter menjadi `hati_hati` mirip), loo 18 → 18; rank@1 21/22 → 22/22 (MRR 0,955 → 1,000); cocok label harapan biasa 51 → 50 dari 55 (obrolan pendek menjadi `tidak_ditemukan`, padahal labelnya `teks_tidak_terbaca`). Set dev: negatif dan recall sama; hanya ev134 berubah.
- **Batas waktu Groq tanpa cadangan.** Dengan `CEKHOAKS_LLM_CADANGAN=mati`, batas Groq naik dari 4 menjadi 7 detik (`LLM_TIMEOUT_GROQ_SENDIRI`), karena waktu yang biasanya disisakan untuk Gemini tidak terpakai. Anggaran total tetap 9 detik. Alasannya: pada uji HP 2026-10-19, satu panggilan butuh 3,5 detik. Kalau cadangan menyala, batasnya tetap 4 detik. Perubahan ini diuji dengan transport palsu, tanpa panggilan Groq.
- **Lowongan Nestle.** Setelah database diperbarui, hasilnya `kuat` dengan artikel sumber di peringkat 1. Tanpa artikelnya di database, hasilnya `tidak_ditemukan` tanpa ciri.

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
- **Tahap 2, perbaikan tangkapan saat layar diam (ditemukan saat uji HP otomatis setelah Sesi 5.5):**
  - **Gejala:** ketukan tombol cek sering menghasilkan Toast "Gambar layar belum berhasil diambil" bila layar diam sebelum diketuk. Hasil uji lewat adb sebelum perbaikan: 11 dari 20 percobaan berhasil, tanpa pola terhadap lama diam.
  - **Akar masalah:** layar virtual `AUTO_MIRROR` hanya mengirim frame saat isi layar berubah. Pendengar `ImageReader` menutup frame tersimpan sebelum memanggil `acquireLatestImage()`, padahal fungsi itu mengambil semua frame yang antre sekaligus dan mengembalikan null bila pendengar berjalan lagi untuk frame yang sudah ikut terambil. Frame bagus pun hilang, dan pada layar diam tidak ada frame pengganti.
  - **Perbaikan:** logika pemilihan frame dipisah ke `PemilihFrame.kt` (diuji di `PemilihFrameTest.kt` dengan frame dan jam palsu). Saat idle, frame yang masuk langsung ditutup, jadi isi layar tidak dipegang di memori. `ambil()` dipanggil tepat setelah tombol disembunyikan. Frame lama hanya ditutup bila frame baru ada, dan yang dipakai adalah frame terbaru saat jeda minimum 150 ms selesai, supaya frame transisi tidak terpakai (tombol disembunyikan tanpa animasi). Bila sampai 1 detik tidak ada frame, surface layar virtual dilepas lalu dipasang lagi untuk memaksa frame baru, lalu ditunggu 300 ms sebelum Toast. Log `Frame dipakai: tiba X ms ...` hanya mencatat waktu dan jumlah frame.
  - **Hasil uji sesudah perbaikan:** 20 dari 20 percobaan berhasil (diam 0, 5, 15, dan 30 detik, masing-masing 5 kali). Pada layar diam, frame setelah tombol disembunyikan selalu tiba dalam 39-69 ms, sehingga cadangan tidak pernah terpakai tetapi tetap dipasang sebagai pengaman. Pada 20 gambar beku di layar pilih area tidak ada sisa tombol mengambang.
  - **Perilaku sistem (Android 16, bukan bug ini):** saat layar HP dimatikan dan terkunci, sistem menghentikan sesi rekam layar (log `Sesi rekam layar dihentikan oleh sistem`). Tombol cek hilang dan harus diaktifkan lagi setelah HP dibuka, tanpa crash.
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
- **Tahap 5 (versi CPU, sedang berjalan):**
  - **Pipeline target:** gambar → pembacaan teks → pembersihan teks (termasuk membuang teks UI media sosial) → `klaim_utama` (heuristik) → pencocokan ke database cek fakta → deteksi ciri (regex) → logika tingkat buatan sendiri → penjelasan dari template.
  - **Pembagian sesi:**
    - 5.1 Fondasi server dan beres-beres (kode selesai; uji manual di HP belum).
    - 5.2 Pengukuran OCR (RapidOCR, RapidOCR Latin, PaddleOCR) di laptop Lenovo, pada 18 screenshot berlabel (selesai; RapidOCR bawaan dipilih).
    - 5.2b Pemasangan RapidOCR ke server (selesai; uji manual lulus).
    - 5.3 Database cek fakta dan pencarian vektor.
    - 5.4 Daftar ciri, regex, template penjelasan (daftar ciri di §8 difinalkan di sini).
    - 5.5 Penyatuan pipeline di `/analisis` (selesai kode dan uji otomatis; menunggu uji manual di HP; rincian di bagian Sesi 5.5).
    - 5.6 Evaluasi dan penetapan ambang.
    - Opsional, setelah Tahap 6-7 aman: classifier IndoBERT/IndoBERTweet. (LLM untuk `klaim_utama` sudah diputuskan lewat API di Sesi 5.4a.)
  - **Keputusan yang sudah diambil:**
    - Vektor disimpan sebagai NumPy di memori; pgvector hanya rencana skala besar.
    - Target kecepatan di bawah 10 detik sebagai sasaran dan 15 detik sebagai batas, diukur dari ketukan kirim sampai kartu hasil muncul di HP.
    - Data uji berlabel 120-150 dulu: sekitar sepertiga hoaks yang ada di database, sepertiga hoaks yang tidak ada, sepertiga informasi biasa.
    - Artikel cek fakta yang labelnya bukan hoaks tetap ditampilkan sebagai rujukan dengan label apa adanya beserta sumbernya. Artikel seperti itu tidak pernah menaikkan tingkat ke `kuat`, dan sistem sendiri tetap tidak menyatakan informasi benar.
    - Pembacaan teks memakai RapidOCR bawaan (Sesi 5.2). Qwen-VL lokal tidak diukur karena proyek beralih ke kemungkinan memakai API LLM.
    - API LLM dipakai untuk `klaim_utama` dan kandidat ciri: penyedia utama Groq `openai/gpt-oss-120b`, cadangan Google `gemini-3.5-flash-lite` (Sesi 5.4a; rincian di bagian Sesi 5.4a).
  - **Keputusan yang masih terbuka:** tanggal pasti showcase (perkiraan awal November); apakah dan berapa banyak artikel cek fakta terbaru ditambahkan manual untuk demo; apakah jalur opsional dikerjakan.
  - **Sesi 5.1, yang dikerjakan:**
    - `PAKSA_TINGKAT` tidak dikenal membuat server menolak jalan (pesan memuat nilai yang diterima dan daftar nilai sah, kode keluar 1). Daftar nilai sah satu sumber di `server/app/konfigurasi.py` (`NILAI_PAKSA`). Karena itu galat 500 untuk kasus ini tidak lagi bisa sampai ke HP; deskripsi `galat_server` di `docs/API.md` sudah disesuaikan dan `galat_http` ditambahkan ke tabel galat (klien Android sudah menampilkan kode tak dikenal sebagai kartu galat umum, tanpa crash).
    - Satu file konfigurasi `server/app/konfigurasi.py` (modul Python biasa, tanpa dependensi baru). Bawaan bisa ditimpa variabel lingkungan: `CEKHOAKS_HOST`, `CEKHOAKS_PORT`, `CEKHOAKS_BATAS_GAMBAR_BYTE`, `CEKHOAKS_JEDA_MIN`, `CEKHOAKS_JEDA_MAKS`, `PAKSA_TINGKAT`. Pengaturan ambang kemiripan dan pilihan model ditambahkan saat sesi yang memakainya.
    - Logika analisis dipecah ke `server/app/pipeline/`: `baca`, `bersih`, `klaim`, `cocok`, `ciri`, `tingkat`, `template`, dan `orkestrator` yang memanggil semuanya berurutan serta mencatat durasi tiap tahap (tanpa teks atau isi gambar). Semua modul masih dummy dengan keluaran sama seperti server Tahap 4. `main.py` hanya mengurus HTTP; endpoint dan `app.cek` memanggil `orkestrator.jalankan` yang sama.
    - `python -m app.cek PATH_GAMBAR` menjalankan pipeline yang sama dari terminal tanpa jeda buatan (kode keluar 0 sukses, 1 galat API, 2 berkas tak terbaca).
    - `server/data_lokal/` untuk screenshot uji dan dataset mentah di sesi berikutnya. Folder ini masuk `.gitignore`, jadi gambar dan dataset mentah tidak ikut repo. Aturan "gambar tidak disimpan" berlaku untuk server dan aplikasi, bukan untuk berkas uji milik developer di folder ini.
    - 54 pytest (kontrak API, konfigurasi, pipeline, `app.cek`); gambar uji dibuat di memori.
  - **Sesi 5.2, bahan ukur (keterbatasan):** 18 gambar uji di `server/data_lokal/screenshot_uji/` bukan screenshot dari HP developer. Sepuluh gambar berasal dari unduhan developer (kebanyakan tangkapan layar penipuan lewat WhatsApp, Facebook, dan Messenger), tujuh diambil dari header artikel turnbackhoax.id (sudah di-crop dari bingkai ilustrasi), satu dari artikel merahputih.com. Semuanya beresolusi rendah (lebar 376-1100 px); hanya dua yang lebarnya 1080 px atau lebih, sisanya 16 gambar di bawah itu. Karena itu alat ukur (`server/alat/ukur_baca/`) memperbesar gambar yang lebarnya di bawah 1080 px ke lebar 1080 px dengan Lanczos sebelum praproses aplikasi, untuk meniru gambar terusan yang dibuka layar penuh di galeri Samsung A55 lalu di-screenshot. Perbesaran tidak menambah detail, jadi CER dan waktu baca pada gambar-gambar itu hanya perkiraan, kemungkinan lebih buruk dari screenshot HP asli. Kolom `diperbesar` di CSV hasil menandai gambar yang diperbesar. Transkripsi acuan dibuat dari gambar aslinya (bukan hasil praproses) oleh Claude dan hanya diperiksa acak oleh manusia. Bagian yang meragukan, tertutup, atau terpotong ditulis `[?]` dan dikeluarkan dari perhitungan CER (wildcard). 16 dari 18 gambar diperbesar dari resolusi rendah, sehingga CER absolut lebih buruk dari pemakaian nyata, tetapi perbandingan antarkandidat tetap adil karena semuanya membaca gambar yang sama. Gambar 15 tidak berisi teks, jadi tidak punya CER; untuk gambar itu hanya dicatat jumlah teks yang dihasilkan kandidat.
  - **Sesi 5.2, hasil pengukuran pembacaan teks (selesai):**
    - **Kondisi:** laptop Lenovo, Ryzen 7 8840HS, RAM 16 GB, Windows 11, tersambung charger dengan mode daya Best performance, CPU saja (iGPU Radeon 780M tidak dipakai). Python 3.12.4. Versi alat: RapidOCR 3.9.2 dengan onnxruntime 1.30.0 (`.venv-ukur`); PaddleOCR 3.7.0 dengan PaddlePaddle 3.3.1 (`.venv-ukur-paddle`, dipisah karena bentrok numpy dan opencv); Pillow 12.3.0. Waktu per gambar adalah median dari 3 kali baca, setelah satu pemanasan yang dibuang. Praproses meniru aplikasi (sisi terpanjang maksimal 2000 px, JPEG kualitas 90) dengan perbesaran awal seperti dicatat di butir bahan ukur.
    - **Metrik:** `cer_isi` (utama): jarak edit karakter terhadap seluruh acuan; karakter baris UI media sosial tidak dihitung, `[?]` menjadi wildcard, dan sisipan yang tidak cocok dengan isi maupun UI dihitung salah. `cer_penuh` memperlakukan karakter UI seperti isi. `ui_terbaca` adalah proporsi karakter UI yang muncul di hasil. Karangan adalah jumlah karakter sisipan; di gambar 15 (tanpa teks) semuanya karangan. Gambar 08 punya banyak wildcard, jadi ringkasan juga ditampilkan tanpa gambar itu.
    - **Ringkasan, semua gambar** (17 gambar yang punya teks; gambar 15 hanya untuk karangan):

      | kandidat | detik rata-rata | detik median | cer_isi | cer_penuh | ui_terbaca | karangan di gambar 15 |
      |---|---|---|---|---|---|---|
      | RapidOCR bawaan | 0,88 | 0,89 | 0,089 | 0,097 | 0,96 | 0 |
      | RapidOCR Latin | 1,05 | 1,03 | 0,093 | 0,098 | 0,98 | 0 |
      | PaddleOCR | 34,57 | 24,94 | 0,089 | 0,094 | 0,97 | 5 |

    - **Ringkasan, tanpa gambar 08** (16 gambar):

      | kandidat | detik rata-rata | detik median | cer_isi | cer_penuh | ui_terbaca | karangan di gambar 15 |
      |---|---|---|---|---|---|---|
      | RapidOCR bawaan | 0,84 | 0,84 | 0,060 | 0,067 | 0,96 | 0 |
      | RapidOCR Latin | 1,02 | 1,01 | 0,065 | 0,067 | 0,98 | 0 |
      | PaddleOCR | 35,21 | 24,99 | 0,061 | 0,064 | 0,97 | 5 |

    - **Catatan kualitatif:** ketiga kandidat sama baik pada teks yang jelas (selisih `cer_isi` di bawah 0,01), dan teks UI hampir selalu terbaca. Kesalahan terbesar ada di gambar beresolusi rendah dengan teks bertumpuk (gambar 08 dan 18, `cer_isi` sekitar 0,55 di semua kandidat) dan pada teks kecil berwarna putih di atas foto. Pemeriksaan kata acuan yang tidak dibaca oleh satu kandidat pun menyisakan sebelas kata di tiga gambar: sembilan di gambar 18 (teks kecil di atas foto, terlihat jelas), satu pada lencana kecil di gambar 07 (terlihat jelas), dan satu pecahan kata di samping wildcard di gambar 06. Tidak ada acuan yang diganti `[?]`. Karena ketiganya satu keluarga model (PP-OCR), kata yang gagal dibaca semuanya tidak dianggap tebakan. PaddleOCR menghasilkan karangan di gambar tanpa teks, RapidOCR tidak.
    - **PaddleOCR gugur:** rata-rata 34,6 detik per gambar, jauh di atas batas 15 detik untuk seluruh pipeline, dan tidak lebih akurat. oneDNN harus dimatikan karena melempar `NotImplementedError` di PaddlePaddle 3.3 untuk Windows CPU, sehingga tidak ada jalan untuk mempercepatnya.
    - **RapidOCR Latin tidak dipilih:** sedikit lebih lambat (1,05 lawan 0,88 detik) dan `cer_isi` sedikit lebih buruk (0,093 lawan 0,089).
    - **Keputusan:** pipeline memakai RapidOCR bawaan (0,88 detik per gambar, `cer_isi` 0,089 untuk semua gambar dan 0,060 tanpa gambar 08), sehingga pembacaan teks memakai kurang dari 10% dari sasaran 10 detik. Gambar tidak dikirim ke pihak ketiga pada langkah ini.
    - **Qwen-VL lokal tidak diukur:** rencana pengukuran lewat Ollama tidak dijalankan karena proyek beralih ke kemungkinan memakai API LLM untuk tahap berikutnya. Pemilihan model atau penyedia API ditunda dan masuk ke keputusan terbuka.
    - **Pekerjaan sesi berikutnya:** memasang RapidOCR ke `server/app/pipeline/baca.py` (dependensi server dan praproses gambar di server). Alat ukur tidak dipakai server.
  - **Sesi 5.2b (pemasangan RapidOCR ke server), yang dikerjakan:**
    - Pembaca teks sungguhan terpasang di `server/app/pipeline/baca.py`: RapidOCR 3.9.2 dengan konfigurasi dan urutan baris sama seperti kandidat `rapidocr` di alat ukur, tanpa pembesaran gambar. Versi `rapidocr`, `onnxruntime`, `numpy`, dan `opencv-python` di `requirements.txt` dikunci sama dengan `.venv-ukur`.
    - Mesin dimuat dan dipanaskan sekali saat server menyala (pesan siap beserta lama pemuatan tercetak). Pembacaan berjalan di satu thread pekerja, sehingga satu per satu dan tidak memblokir event loop. Pembatalan klien diperiksa setelah pembacaan selesai.
    - `teks_tidak_terbaca` sungguhan: jumlah karakter huruf-angka di bawah `CEKHOAKS_AMBANG_TEKS` (bawaan 20; gambar 15 menghasilkan 0, teks sah terpendek di data uji 93) menghasilkan galat 422. Ambang final ditetapkan di Sesi 5.6.
    - `PAKSA_TINGKAT=teks_tidak_terbaca` tetap memaksa galat tanpa OCR; nilai paksa lain tetap membaca teks sungguhan tetapi melewati ambang. Jeda buatan bawaan menjadi 0. Versi server 0.5.0; kontrak API tetap 0.4.
    - Modul lain (bersih, klaim, cocok, ciri, tingkat, template) masih dummy, jadi klaim, ciri, dan tingkat tidak berkaitan dengan teks yang dibaca. Kartu hasil di aplikasi tidak menampilkan `teks_terbaca`.
  - **Daftar uji Sesi 5.2b** (perintah lengkap ada di catatan sesi; semuanya lulus):
    - [x] `pytest`: 71 lulus; dengan `-m "not rapidocr"`: 66 lulus, 5 dilewati.
    - [x] `app.cek`: `01.jpg` menghasilkan `teks_terbaca` yang sesuai isi gambar; `15.png` menghasilkan galat `teks_tidak_terbaca` dengan kode keluar 1.
    - [x] Pemuatan pembaca teks saat server menyala: 1,5 sampai 2,0 detik (pesan siap tercetak).
    - [x] Uji koneksi dari HP lewat hotspot HP: berhasil, versi server 0.5.0. Analisis diuji lewat USB (`adb reverse`); Wi-Fi rumah atau kampus tidak diuji ulang di sesi ini.
    - [x] Giliran tingkat tanpa `PAKSA_TINGKAT` (kuat → hati-hati → tidak ditemukan), kartu teks tidak terbaca pada area tanpa tulisan, Batal di tengah analisis, keempat nilai `PAKSA_TINGKAT`, dan kartu galat saat server mati: semua sesuai.
    - [x] Waktu pembacaan di server: 0,35 sampai 0,73 detik per gambar.
  - **Temuan untuk Sesi 5.6:** satu area yang dimaksudkan tanpa tulisan terbaca 25 karakter huruf-angka, sehingga lolos ambang 20 dan tidak menghasilkan `teks_tidak_terbaca`. Ambang 20 ditetapkan dari 18 gambar uji (gambar tanpa teks: 0 karakter), jadi perlu ditinjau ulang dengan data area tanpa tulisan yang lebih beragam (misalnya latar bertekstur, ikon, dan foto) beserta skor keyakinan per baris (`BarisTeks.skor`) sebagai pertimbangan tambahan.
  - **Sesi 5.3 (database cek fakta dan pencarian kemiripan), status: selesai, menunggu pengujian manual developer.** Alat ada di `server/alat/cek_fakta/` (README di sana berisi semua perintah). Belum terpasang ke `/analisis`; itu dikerjakan di Sesi 5.5. Pengumpulan dari turnbackhoax.id selesai 2026-10-09 (daftar artikel di situs habis). Semua angka di bawah diukur pada database akhir **21.342 artikel**.
    - **Sumber data:**
      - Kaggle `aginanjar` (TurnBackHoax 2015-09 sampai 2024-10-30, 15.720 baris), `ireddragonicy` (klarifikasi Komdigi 2024-05 sampai 2026-10-06, 4.104 baris), dan `linkgish` (bagian TurnBackHoax, 10.381 baris, 99,97% sama dengan aginanjar; kolom `Narasi`-nya dipakai untuk melengkapi narasi). Berita CNN, Kompas, dan Tempo di `linkgish` tidak masuk database, hanya menjadi kalimat kueri negatif. Lisensi ketiganya belum diketahui (lihat `docs/REFERENSI.md`).
      - Pengumpulan dari turnbackhoax.id (`robots.txt` mengizinkan, tanpa sitemap, daftar lewat `/articles?page=N`). Situs lain dilewati dengan alasan di `docs/REFERENSI.md`.
    - **Temuan penting:** URL TurnBackHoax format lama (`/2024/10/30/slug/`) di Kaggle menghasilkan 404 (diuji pada contoh, dan diulang pada tiga artikel 2018 sampai 2020). Slug sama dengan format baru (`/articles/ID-slug`), sehingga hasil pengumpulan menggantikan URL lama untuk artikel yang ada di situs. Pengumpulan penuh berjalan 683 menit (sekitar 11,4 jam; 13.889 permintaan, 590 MB setelah dekompresi) dan menghasilkan 15.585 artikel (per tahun: 0000=1, 2015=40, 2016=173, 2017=407, 2018=1.003, 2019=588, 2020=1.007, 2021=1.889, 2022=1.695, 2023=2.388, 2024=3.734, 2025=1.536, 2026=1.124). Empat artikel sempat dilewati (404 atau tak terbaca); dua tetap tak terbaca (ID 10982 dan 10983, tersimpan sebagai rekaman galat dan tidak masuk database) dan dua sisanya berhasil pada percobaan berikutnya.
    - **Skema artikel** (`artikel.jsonl`): `id, judul, narasi, label_asli, label, sumber, url, tanggal (ISO), asal_data`, ditambah `asal_lain` (sumber duplikat yang digabung) dan `url_format_lama`. `label` memakai himpunan `salah`, `penipuan`, `belum_terbukti`, `benar`, `klarifikasi`, `satir`, `lainnya`; judul berlabel BERITA, EDUKASI, TOP 5, ACARA, dan sejenisnya tidak masuk database. Label diambil dari awalan judul, termasuk bentuk tidak baku: `HOAX:` atau `HASUT:` tanpa kurung, kurung yang tidak lengkap (`[SALAH ...`, `SALAH] ...`), semuanya `salah`; `(FAKTA)` menjadi `benar`. `PARODI`, `SATIR`, `SATIRE`, dan `KOMEDI` (muncul di artikel situs, bukan di Kaggle) menjadi `satir`. `ISU`, `FRAMING`, `KOREKSI`, `CekFakta`, dan judul tanpa label tetap `lainnya`. Aturan penggunaan label di tingkat indikasi ada di butir "Aturan untuk Sesi 5.5" di bawah. `url` wajib terisi (baris tanpa URL dibuang; tidak ada kasusnya di data ini), `tanggal` boleh kosong.
    - **Pembersihan hasil pengumpulan** (`bersihkan.py`, dengan cadangan otomatis): yang dibuang hanya baris yang bukan JSON utuh, tanpa url atau judul, dan duplikat URL; baris tanpa narasi atau tanpa tanggal tetap dipakai. Pada 15.585 baris tidak ada yang dibuang (203 tanpa narasi, 2 rekaman galat). Satu artikel (ID 13707) bertanggal `0000-00-00` karena `tanggal_iso` menerima angka apa pun; kini tanggal divalidasi dan yang tidak sah menjadi `null` (artikel itu tetap mendapat tanggal dari duplikat Kaggle).
    - **Penggabungan:** duplikat dikenali dari URL, slug TurnBackHoax, "Link Counter" Komdigi, dan judul ternormalisasi dengan tanggal berdekatan (selisih maksimal 7 hari). Prioritas: hasil pengumpulan situs, lalu Kaggle TurnBackHoax, lalu Komdigi. **Hasil akhir: 21.342 artikel.** Per sumber (pemenang saat duplikat): situs 15.383, Kaggle aginanjar 3.073, Komdigi 2.885, linkgish 1. Per label: salah 18.936, penipuan 1.458, klarifikasi 496, benar 325, lainnya 56, belum_terbukti 42, satir 29. Per tahun: 2015=70, 2016=321, 2017=669, 2018=1.289, 2019=1.319, 2020=2.366, 2021=1.919, 2022=1.711, 2023=2.389, 2024=4.583, 2025=2.682, 2026=2.024. 754 baris bukan cek fakta dibuang. Narasi terisi untuk 15.289 dari 15.383 baris situs, 2.604 dari 3.073 baris Kaggle, dan seluruh Komdigi; baris tanpa narasi di-embed dari judul saja.
    - **Pemetaan label tambahan:** 345 baris awalnya berlabel `lainnya`, 306 di antaranya karena judul situs tidak punya awalan label (artikel lama 2015 sampai 2019). Halaman situs punya "Hasil Periksa Fakta" yang dipakai sebagai cadangan, hanya untuk judul tanpa label atau berlabel `ISU`: Salah atau False menjadi `salah`; Klarifikasi, Clarification, Benar, atau True menjadi `klarifikasi` (pada artikel klarifikasi, "Benar" berarti klarifikasinya benar, bukan klaimnya, sehingga tidak dipetakan ke `benar`); Berita, Edukasi, dan Dalam Proses tetap `lainnya`. Ejaan miring juga dipetakan: DISINFOMASI, DISINFORMAS, DISINFORMATION, dan "Konten yang dimanipulasi" menjadi `salah`, SCAM menjadi `penipuan`, INFORMASI tetap `lainnya`. Akibatnya 289 label berubah (243 ke `salah`, 45 ke `klarifikasi`, 1 ke `penipuan`) dan `lainnya` turun ke 56. Jumlah, urutan, judul, dan narasi artikel tidak berubah (dibandingkan baris demi baris), jadi vektor tetap berlaku. Artikel Kaggle tidak punya hasil periksa, sehingga 21 baris Kaggle berlabel `lainnya` tetap `lainnya`.
    - **Kecocokan vektor dan database:** metadata vektor kini menyimpan `teks_sha1`, sidik jari dari id dan teks yang di-embed (`passage: judul. narasi`) menurut urutan, bukan dari seluruh `artikel.jsonl`. Mengubah label, URL, atau field lain tidak membatalkan vektor; mengubah id, judul, narasi, atau urutan membatalkannya dan `cari.py` menolak dengan pesan jelas. Keempat vektor yang ada dimigrasikan tanpa embedding ulang setelah sidik jari lama terbukti cocok.
    - **Sisa URL format lama: 3.074 baris** (3.073 Kaggle aginanjar dan 1 linkgish), terkonsentrasi di 2018 sampai 2020 (2019: 757, 2020: 1.384). Penyebab: daftar `/articles` di situs tidak memuat artikel lama (situs punya 982 artikel 2020, sedangkan data Kaggle jauh lebih banyak). Hanya 25 baris yang awal slug-nya cocok dan 44 yang judulnya sama dengan artikel situs, jadi pencocokan lewat slug atau judul tidak akan banyak membantu. Tidak ada permintaan tambahan ke situs untuk menelusurinya (keputusan developer).
    - **Bahan Sesi 5.5 (tautan format lama):** artikel berpenanda `url_format_lama` tetap ditampilkan (judul, label, sumber, tanggal), tetapi tombolnya membuka pencarian web dengan judul artikel, bukan tautan langsung. Pilihan akhir diputuskan di Sesi 5.5.
    - **Teks yang di-embed:** `passage: judul (tanpa awalan label). narasi`; kueri berawalan `query: `; panjang maksimal 256 token. Model dijalankan lewat onnxruntime dengan tokenizer Hugging Face `tokenizers` (tanpa PyTorch); rata-rata pooling dan normalisasi L2 dilakukan sendiri. Vektor float32 di NumPy, pencarian cosine brute-force.
    - **Data uji:** teks OCR screenshot 09 sampai 15 (gambar 15 tanpa teks), 50 kueri parafrase gaya pesan berantai (ditulis Claude dari 50 artikel acak, seed tetap), dan 30 kueri negatif (20 kalimat berita CNN, Kompas, dan Tempo yang topiknya sebagian besar politik sehingga sulit, ditambah 10 kalimat sehari-hari). Parafrase ditulis oleh Claude, bukan orang lain, sehingga mungkin lebih mudah daripada pesan berantai asli.
    - **Perbandingan model** (laptop Lenovo Ryzen 7 8840HS, CPU saja, database akhir 21.342 artikel; hasil sebelumnya pada 19.168 artikel disimpan di `uji/hasil_sebelum_5_3_akhir/`):

      | model | recall@1 | recall@5 | OCR benar (peringkat 1) | skor top-1 cocok (median) | skor negatif (median / p90 / maks) | bangun | per kueri (median) | model | vektor | RAM tambahan (puncak saat bangun) |
      |---|---|---|---|---|---|---|---|---|---|---|
      | e5-base fp32 | 0,68 | 0,94 | 6 dari 6 | 0,876 | 0,837 / 0,874 / 0,892 | 27,2 menit | 24 ms | 1,11 GB | 66 MB | 1,49 GB (1,92 GB) |
      | e5-base int8 | 0,74 | 0,92 | 6 dari 6 | 0,861 | 0,828 / 0,856 / 0,881 | 10,4 menit | 14 ms | 279 MB | 66 MB | 0,67 GB |
      | e5-small fp32 | 0,70 | 0,90 | 6 dari 6 | 0,903 | 0,870 / 0,890 / 0,903 | 7,2 menit | 11 ms | 470 MB | 33 MB | 0,81 GB |
      | e5-small int8 | 0,70 | 0,90 | 6 dari 6 | 0,903 | 0,870 / 0,894 / 0,909 | 4,2 menit | 7 ms | 118 MB | 33 MB | 0,47 GB |

    - **Cara membaca hasil:**
      - Dengan hanya 50 kueri, selisih beberapa poin persen setara satu atau dua kueri dan tidak bermakna. Pada database akhir, recall@1 keempat model berada di 0,68 sampai 0,74 dan recall@5 di 0,90 sampai 0,94, dengan urutan yang berbeda dari pengukuran sebelumnya (base int8 kini 0,74 di atas base fp32 0,68); selisih itu masih dalam kisaran derau. Satu-satunya selisih yang konsisten di kedua pengukuran adalah recall@5 base fp32 (0,94) lebih tinggi daripada small (0,88 sampai 0,90).
      - Pada pengukuran sebelumnya, lima dari sembilan kegagalan recall@1 e5-base mengembalikan artikel lain yang membantah klaim yang sama (penilaian Claude, belum diperiksa manusia). Kegagalan pada database akhir tidak diperiksa ulang satu per satu; recall berdasarkan klaim kemungkinan masih lebih tinggi daripada recall berdasarkan artikel.
      - **Screenshot 09 sampai 15:** keenam gambar bertulisan menemukan artikel sumbernya di peringkat 1 pada keempat model (sebelumnya hanya gambar 11 dan 13, karena artikel Sep 2026 untuk gambar lain baru masuk lewat pengumpulan). Skor di e5-base fp32: 09=0,868, 10=0,893, 11=0,909, 12=0,881, 13=0,888, 14=0,855; gambar 15 tanpa teks. Gambar 09 dan 14 berada di bawah ambang awal 0,88, jadi ambang tunggal akan melewatkan artikel yang benar.
      - **Skor e5 terkompresi dan rentangnya tumpang tindih.** Pada e5-base fp32, skor top-1 parafrase (n=50) dan kueri negatif (n=30) yang mencapai ambang: 0,85 meloloskan 43 dari 50 parafrase tetapi juga 10 dari 30 negatif; 0,87 meloloskan 22 dan 4; 0,88 meloloskan 17 dan 1; 0,89 meloloskan 8 dan 1; 0,90 meloloskan 2 dan 0. Ambang tunggal pada skor tidak cukup; Sesi 5.6 perlu mempertimbangkan sinyal tambahan, misalnya selisih skor dengan peringkat berikutnya, tumpang tindih kata kunci, dan pemeriksaan label.
    - **Usulan keputusan (belum final):** model **e5-base fp32**. Alasan: recall@5 tertinggi (0,94) dan pemisahan skor yang baik; biayanya masih wajar untuk laptop 16 GB (24 ms per kueri, sekitar 1,5 GB RAM, bangun ulang 27 menit untuk 21 ribu artikel), dan jauh di bawah target 10 detik per permintaan. Catatan: pada database akhir selisih antarmodel mengecil dan base int8 (14 ms, 0,67 GB, bangun 10 menit) hampir setara pada 50 kueri, sehingga varian yang lebih ringan layak dipertimbangkan lagi di Sesi 5.6 kalau data uji yang lebih besar menunjukkan hasil serupa. Pemasangan ringan (onnxruntime ditambah `tokenizers`) tidak memakai PyTorch sama sekali.
    - **Keputusan developer:** e5-base fp32 dipakai; e5-small tetap cadangan.
    - **Ambang awal `skor_kemiripan` untuk e5-base fp32:** 0,88 sebagai "cocok" (meloloskan 17 dari 50 parafrase dan 1 dari 30 negatif) dan 0,85 sampai 0,88 sebagai "mirip, perlu hati-hati" (di 0,85 meloloskan 43 dari 50 parafrase dan 10 dari 30 negatif). Nilai ini hanya titik awal; ditetapkan di Sesi 5.6 dengan data uji 120-150 kueri.
    - **Bahan untuk Sesi 5.6:** skor e5 saja tidak cukup untuk memutuskan cocok atau tidak. Sinyal tambahan yang akan dicoba: (1) selisih skor dengan peringkat berikutnya, (2) tumpang tindih kata kunci antara teks dan judul atau narasi artikel, dan (3) verifikasi kandidat oleh LLM kalau API LLM jadi dipakai (keputusan itu masih terbuka). Setiap sinyal diukur pada data uji yang sama dengan sebaran skor di atas.
    - **Aturan untuk Sesi 5.5:** hanya artikel berlabel `salah` dan `penipuan` yang boleh menaikkan tingkat ke `kuat`. Artikel berlabel `benar`, `klarifikasi`, `belum_terbukti`, `satir`, dan `lainnya` hanya ditampilkan sebagai rujukan di `cek_fakta[]` dengan label apa adanya. Pengaruh label `satir` ke tingkat (misalnya apakah klaim satir cukup diberi catatan saja) diputuskan di Sesi 5.5.
    - **Untuk Sesi 5.4:** label `satir` membutuhkan teks penjelasan template sendiri (satir bukan kebohongan yang dimaksudkan menipu, jadi penjelasannya harus berbeda dari `salah`). Teks itu tanpa kata ganti orang kedua dan tidak dibuat oleh LLM.
    - **Label di kontrak API (`docs/API.md`, tidak diubah di sesi ini):** `cek_fakta[].label` bertipe string bebas (`str` di `server/app/skema.py`, `String` di `KontrakApi.kt`), dan dokumen hanya memberi contoh "misalnya salah, hoaks, menyesatkan", sehingga nilai `satir` tidak melanggar kontrak. **Disetujui developer:** pembaruan daftar nilai label di `docs/API.md` masuk **Sesi 5.5**, dan teks label per nilai beserta teks cadangan untuk nilai tak dikenal masuk **Tahap 6**. Rinciannya: (1) contoh di API.md memuat `hoaks` dan `menyesatkan` yang tidak ada di himpunan label alat ini, jadi API.md perlu mendaftar nilai yang sungguh dikirim server (`salah`, `penipuan`, `belum_terbukti`, `benar`, `klarifikasi`, `satir`, `lainnya`); (2) aplikasi menampilkan label dari `strings.xml` berdasarkan nilainya, jadi Tahap 6 perlu teks untuk tiap nilai dan satu teks cadangan untuk nilai yang tidak dikenal. Baris yang hanya punya URL format lama (`url_format_lama`) kemungkinan 404; cara menampilkannya diputuskan di sesi yang sama.
    - **Keterbatasan:** parafrase ditulis oleh Claude; 50 kueri membuat selisih kecil tidak bermakna dan ukuran kueri negatif (30) kecil; hanya sebagian kegagalan pernah diperiksa manual (pada pengukuran sebelumnya); kueri negatif berita sengaja berat (topik politik tumpang tindih dengan hoaks); narasi untuk baris tanpa narasi hanya berasal dari judul; 3.074 artikel (14%) hanya punya tautan format lama yang mati; artikel 2018 sampai 2020 hanya sebagian ada di situs sehingga label dan tanggalnya bergantung pada Kaggle; pemetaan label dari "Hasil Periksa Fakta" tidak diperiksa satu per satu untuk 289 baris yang berubah; lisensi dataset Kaggle belum diperiksa developer; turnbackhoax.id menyatakan semua materinya milik MAFINDO dan izin tertulis belum diminta (lihat `docs/REFERENSI.md`).
  - **Sesi 5.4a (pengukuran API LLM untuk analisis teks), status: selesai, keputusan sudah diambil developer (lihat "Keputusan Sesi 5.4a" di bawah).** Alat ada di `server/alat/ukur_llm/` (README di sana berisi semua perintah). Sesi ini hanya mengukur; belum ada yang dipasang ke `server/app/`. Data mentah dan CSV ada di `server/data_lokal/hasil_llm/` (tidak masuk repo). Ketentuan kuota dan data tiap penyedia ada di `docs/REFERENSI.md`.
    - **Prinsip yang diukur:** gambar tidak dikirim; hanya teks OCR yang data pribadinya disamarkan (nomor telepon, email, `@akun`; tautan dibiarkan). LLM tidak menentukan tingkat dan tidak menyatakan benar atau salah; tugasnya mengekstrak `klaim_utama` dan menandai kandidat ciri beserta kutipan bukti yang diverifikasi server terhadap teks OCR. `pernah_dibantah` tidak ditawarkan ke LLM (ditentukan pencarian database), jadi LLM memilih dari 7 id (Sesi 5.5 menambah `permintaan_data_rahasia`, sehingga menjadi 8 id).
    - **Kandidat:** Gemini `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`; Groq `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`. Mistral dilewati karena kuncinya kosong. Nama model diperiksa lewat API pada 2026-10-09. `gemini-2.5-flash-lite` muncul di daftar model tetapi API menolaknya ("tidak lagi tersedia untuk pengguna baru"), jadi diganti `gemini-3.1-flash-lite`. Daftar model API tidak menjamin sebuah model bisa dipakai.
    - **Metodologi:** endpoint `chat/completions` kompatibel OpenAI untuk semua penyedia, temperature 0, keluaran JSON bersekema (`json_schema`; diterima semua model), validasi sendiri, ulang sekali kalau tidak valid. 17 teks OCR (gambar 15 kosong tidak dikirim) ditambah 6 ulangan stabilitas (gambar 01, 04, 09, 11, 14, 17) = 23 permintaan per model. Syarat minimum ditetapkan sebelum melihat hasil: valid minimal 95%, tidak ada id di luar daftar, tidak ada klaim yang memuat kata penilaian, median di bawah 4 detik. Kata penilaian (benar, salah, hoaks, hoax, fakta, bohong, palsu, dusta, menyesatkan, terbukti, keliru, penipuan, disinformasi) hanya ditandai kalau ada di klaim tetapi tidak ada di teks masukan (OCR sering menempelkan kata, misalnya "TERDETEKSIPALSU", jadi di teks masukan cukup dicek sebagai potongan). Persen valid dihitung dari permintaan yang menghasilkan isi; permintaan yang gagal karena kuota atau 503 dilaporkan terpisah.
    - **Pengaturan berpikir dan format per model** (parameter dicoba dari yang paling minimal, turun kalau API menolak): `gemini-3.5-flash` `reasoning_effort=none`; `gemini-3.5-flash-lite` `none` ditolak, dipakai `minimal`; `gemini-3.1-flash-lite` `none` diterima tetapi waktu tetap panjang (median 12 detik); `gpt-oss-120b` `low`; `qwen3.8-27b` `none`. Semua memakai `response_format=json_schema` strict. Groq kadang membalas 400 `json_validate_failed` secara acak untuk permintaan yang sama (sekali dari tiga percobaan pada probe gpt-oss gambar 05); klien mengirim ulang permintaan yang sama. Pada pengukuran pertama gpt-oss, klien salah mengira penyebabnya parameter berpikir dan mencabutnya di tengah jalan; kesalahan itu diperbaiki dan gpt-oss diukur ulang penuh dengan `low`.
    - **Hasil** (n = permintaan dengan isi; kutipan = ditemukan di teks / seluruh kutipan):

      | Model | n | Valid | Id luar daftar | Kejujuran kutipan | Klaim bernilai | Median | p95 | 429 | Lolos syarat |
      |---|---|---|---|---|---|---|---|---|---|
      | gemini-3.5-flash | 21 dari 23 | 100% | 0 | 41/44 (93,2%) | 0 | 1,9 dtk | 5,0 dtk | 13 | ya |
      | gemini-3.5-flash-lite | 23 | 100% | 0 | 56/58 (96,6%) | 0 | 1,2 dtk | 4,7 dtk | 0 | ya |
      | gemini-3.1-flash-lite | 23 | 100% | 0 | 60/63 (95,2%) | 1 | 12,1 dtk | 35,5 dtk | 0 | tidak (waktu; klaim memuat "penipuan") |
      | gpt-oss-120b | 23 | 100% | 0 | 42/45 (93,3%) | 0 | 1,0 dtk | 1,4 dtk | 0 | ya |
      | qwen3.8-27b | 23 | 100% | 0 | 69/71 (97,2%) | 2 | 0,5 dtk | 0,9 dtk | 0 | tidak (klaim gambar 11 memuat "fakta", dua kali) |

    - **Kuota Gemini yang ditemukan lewat pengukuran:** `gemini-3.5-flash` hanya 20 permintaan per hari per proyek di kuota gratis (pesan galat API: `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue: 20`; angka ini tidak ada di dokumentasi publik, hanya di AI Studio). Kuota habis di tengah pengukuran sehingga dua ulangan stabilitas (gambar 14 dan 17) tidak terukur; keduanya bisa dijalankan ulang setelah kuota pulih (perintah di README). Anggaran awal (23 sampai 46 permintaan) mengira kuota harian jauh di atas itu, dan itu salah untuk model ini. Kuota harian dua model Flash-Lite tidak diketahui; keduanya melayani lebih dari 26 permintaan tanpa 429.
    - **Kualitas `klaim_utama`** (tabel lengkap di `hasil_llm/laporan.md`): kelima model merangkum klaim dengan netral dan dekat dengan teks pada sebagian besar gambar. Masalah yang terlihat: (1) klaim kosong pada teks yang jelas punya klaim: gpt-oss pada gambar 07, 09, 13; qwen pada 06 dan 08; `gemini-3.5-flash-lite` pada 08 (gambar 04 kosong memang wajar, hanya obrolan salah nomor); (2) klaim berupa judul pendek tanpa predikat (gpt-oss gambar 14: "Korupsi 500 Triliun"); (3) klaim yang memuat pengesahan: qwen menulis "sebuah fakta yang diakui oleh Eropa dan NHS Inggris" pada gambar 11, padahal itu klaim pengunggah; ini persis jenis penilaian yang dilarang prinsip produk; (4) `gemini-3.5-flash` menambahkan "Wakil" pada gambar 14 padahal teks OCR hanya menulis "MenKeu".
    - **Manfaat untuk pencarian** (e5-base fp32, artikel sumber gambar 09-14): teks OCR mentah menempatkan artikel sumber di peringkat 1 pada 6 dari 6 gambar dengan skor peringkat 1 antara 0,855 dan 0,908. Memakai `klaim_utama` lebih buruk: artikel sumber peringkat 1 hanya pada 4/6 (`gemini-3.5-flash-lite`) dan 3/6 (empat model lain), skor peringkat 1 turun ke 0,83 sampai 0,90, dan selisih dengan peringkat 2 umumnya mengecil (gambar 11: dari 0,040 menjadi 0,000 sampai 0,030). Kasus terburuk: gambar 13 (peringkat 14 sampai 20 pada tiga model) dan gambar 11 (peringkat 2 sampai 4 pada tiga model). **Kesimpulan: `klaim_utama` dari LLM tidak dipakai sebagai kueri pengganti pencarian.** Teks OCR mentah tetap kueri utama; klaim paling jauh layak diuji sebagai tampilan di kartu hasil atau sinyal tambahan di Sesi 5.6. Sampelnya 6 gambar, semuanya dari artikel yang ada di database.
    - **Stabilitas** (6 teks diulang, temperature 0): `gemini-3.1-flash-lite` dan `qwen3.8-27b` identik pada 6/6 teks; `gpt-oss-120b` klaim sama 5/6 dan himpunan ciri sama 4/6; `gemini-3.5-flash-lite` klaim sama persis 3/6 (kemiripan kata rata-rata 0,78) dan himpunan ciri sama hanya 1/6; `gemini-3.5-flash` 2/4 dan 4/4 (dua teks tidak terukur). Temperature 0 tidak menjamin keluaran identik pada API terkelola.
    - **Ciri yang ditandai:** rata-rata 1,1 sampai 1,8 ciri per teks. `sumber_tidak_jelas` paling sering (5 sampai 12 dari 17 teks) dan buktinya paling lemah: ada model yang "mengutip" kalimat penjelasan sendiri ("Tidak menyebut sumber resmi atau instansi...") sebagai bukti. qwen mengutip "segera" dan "hari ini terakhir" yang berasal dari contoh di prompt, bukan dari teks (gambar 02). Pemeriksaan kutipan oleh server wajib dan menangkap keduanya.
    - **Usulan awal (sudah diputuskan lain oleh developer, lihat "Keputusan Sesi 5.4a"):** menurut kriteria yang ditetapkan sebelum melihat hasil, tiga model lolos syarat minimum: `gemini-3.5-flash`, `gemini-3.5-flash-lite`, dan `gpt-oss-120b`. Urutan berdasarkan kejujuran kutipan: `gemini-3.5-flash-lite` (96,6%), `gpt-oss-120b` (93,3%), `gemini-3.5-flash` (93,2%). `gemini-3.5-flash` tersingkir secara praktis karena kuota gratis 20 permintaan per hari. Usulan: **utama `gemini-3.5-flash-lite` (Google), cadangan `gpt-oss-120b` (Groq)**, penyedia berbeda. Selisih kejujuran kutipan 96,6% dan 93,3% hanya dua atau tiga kutipan dari sekitar 45 sampai 58, jadi tidak bermakna secara statistik. Hal yang perlu dipertimbangkan developer sebelum menyetujui:
      - **Privasi:** kuota gratis Gemini memperbolehkan Google memakai isi permintaan dan jawaban untuk meningkatkan produknya, dengan kemungkinan ditinjau manusia, dan syarat layanannya meminta data pribadi tidak dikirim ke layanan gratis. Groq menyatakan tidak menyimpan data inferensi secara bawaan (log untuk pemecahan masalah dan penyalahgunaan sampai 30 hari). Penyamaran hanya menutup nomor, email, dan akun; nama orang dan isi pesan tetap terkirim. Kalau privasi diutamakan, menukar urutan (utama `gpt-oss-120b`, cadangan Gemini) layak dipertimbangkan karena selisih kualitasnya kecil; keputusan ini milik developer.
      - **Stabilitas:** `gemini-3.5-flash-lite` paling tidak konsisten antarpanggilan (ciri sama 1/6). Dampaknya kecil selama ciri hanya menjadi petunjuk dan bukti diverifikasi server, tetapi dua analisis pada gambar yang sama bisa berbeda.
      - **Kuota:** kuota harian `gemini-3.5-flash-lite` tidak diketahui. Batas Groq gratis 1.000 permintaan dan 200 ribu token per hari per model (30 permintaan dan 8 ribu token per menit) cukup untuk demo.
      - **Mistral** tidak diukur.
    - **Keterbatasan:** (1) tidak ada label ciri yang benar untuk 18 screenshot, jadi kecenderungan model mengarang ciri hanya terukur lewat kejujuran kutipan; ciri yang kutipannya ada di teks tetap bisa keliru secara makna. (2) Sampel kecil: 17 teks, 6 ulangan, 44 sampai 71 kutipan per model; selisih beberapa persen tidak bermakna. (3) Teks tanpa ciri (informasi biasa) hanya diwakili beberapa gambar (04, 07, 16 sampai 18), jadi kecenderungan mengarang ciri pada teks biasa kurang teruji. (4) Kejujuran kutipan menghitung kutipan yang menyambung tautan lintas baris sebagai tidak ditemukan (OCR memecah `https://` dan nama domain ke dua baris); ini terjadi pada tautan gambar 05 untuk dua model. (5) Waktu diukur dari laptop developer pada satu hari (2026-10-09), dengan kuota gratis; latensi bisa berubah (`gemini-3.1-flash-lite` sempat mengembalikan 503 "high demand" sekali). (6) Batas kuota Gemini tidak terdokumentasi; hanya `gemini-3.5-flash` yang terbukti 20 per hari. (7) Satu ulangan per teks kecuali enam teks stabilitas. (8) Model lain (misalnya `gpt-oss-20b`, seri Gemini 3.6 sampai 3.8, Mistral) tidak diukur.
    - **Keputusan Sesi 5.4a (developer):**
      - **Penyedia utama `openai/gpt-oss-120b` di Groq; cadangan `gemini-3.5-flash-lite` di Google.** Cadangan Gemini hanya dipakai kalau Groq gagal. Alasan: privasi (pengguna akan mengirim potongan obrolan pribadi, sedangkan kuota gratis Gemini mengizinkan isi permintaan dipakai dan ditinjau manusia, sementara Groq tidak menyimpan data inferensi secara bawaan), stabilitas ciri yang lebih baik (himpunan ciri sama 4/6 dibanding 1/6), kecepatan (median 1,0 dibanding 1,2 detik, p95 1,4 dibanding 4,7 detik), dan kuota harian yang jelas. Selisih kualitas kecil (kejujuran kutipan 93,3% dibanding 96,6%).
      - `gemini-3.5-flash` tidak dipakai (kuota 20 permintaan per hari), sehingga dua ulangan stabilitasnya yang belum terukur tidak perlu diselesaikan.
      - **Pencarian cek fakta tetap memakai teks OCR**, bukan `klaim_utama`. `klaim_utama` hanya ditampilkan.
    - **Catatan untuk sesi pemasangan LLM ke server (setelah Sesi 5.4a):**
      - (a) Kalau `klaim_utama` kosong padahal teks berisi pernyataan (gpt-oss mengosongkannya pada gambar 07, 09, dan 13 di pengukuran), ulangi sekali dengan instruksi yang lebih tegas, lalu pakai cadangan heuristik dari server.
      - (b) Periksa kesetiaan `klaim_utama`: sebagian besar kata isinya harus ada di teks OCR; kalau tidak, pakai cadangan heuristik. Ambang "sebagian besar" ditetapkan dengan data uji (pengukuran menemukan kata tambahan seperti "Wakil" pada `gemini-3.5-flash` dan pengesahan "sebuah fakta" pada qwen).
      - (c) Verifikasi kutipan ciri terhadap teks OCR tetap dilakukan. Pengukuran menemukan kutipan yang diambil dari contoh di prompt, kalimat penjelasan model sendiri, dan tautan yang disambung lintas baris; yang terakhir perlu normalisasi saat verifikasi supaya tautan sah tidak ikut terbuang.
      - (d) Cadangan Gemini hanya dipakai kalau Groq gagal (galat, 429, atau batas waktu). Batas Groq gratis: 30 permintaan dan 8.000 token per menit, 1.000 permintaan dan 200.000 token per hari per model. Penyamaran data pribadi (`samarkan.py`) dipindah ke server dan dijalankan sebelum teks dikirim ke penyedia mana pun. Klien menangani 400 `json_validate_failed` acak dari Groq dengan mengirim ulang permintaan yang sama.
    - **Catatan untuk Tahap 6:** onboarding aplikasi harus memberi tahu pengguna bahwa teks yang terbaca dari area yang dipilih dikirim ke penyedia AI pihak ketiga setelah data pribadi (nomor telepon, email, nama akun) disamarkan, dan bahwa gambarnya tidak dikirim. Nama dan isi pesan tidak ikut disamarkan, jadi pemberitahuan tidak boleh menyiratkan semua data pribadi tertutup. Teks pemberitahuan ditulis di `strings.xml` tanpa kata ganti orang kedua.
  - **Sesi 5.5 (penyatuan pipeline di `/analisis`), status: kode selesai, menunggu uji manual di HP.** Kontrak 0.5, server 0.6.0. Giliran hasil dummy dihapus; `PAKSA_TINGKAT` tetap sebagai cadangan demo.
    - **Alur:** baca (RapidOCR) → bersih → gabung tautan terpecah (`tautan.py`) → ambang `teks_tidak_terbaca` dari teks bersih (20 karakter huruf-angka) → paralel: pencarian cek fakta (teks bersih) dan LLM (teks yang sudah disamarkan), ditambah ciri regex → penggabungan ciri → tingkat → klaim utama → template.
    - **Pencarian** (`pipeline/cocok.py`): e5-base fp32 lewat onnxruntime dan tokenizers, tanpa PyTorch. Dimuat sekali saat server menyala (sekitar 4 detik, RAM tambahan sekitar 1,4 GB). Sakelar `CEKHOAKS_CEKFAKTA=mati`. `cek_fakta[]` hanya memuat artikel berskor sedikitnya 0,85 yang relevan, paling banyak 3.
    - **Relevansi:** bagian bobot IDF kata isi judul artikel yang ada di teks. Minimum 0,40, kecuali artikel peringkat satu dengan skor sedikitnya 0,88. Alasannya skor e5 saja tidak memisahkan artikel sah dari artikel yang kebetulan mirip (catatan Sesi 5.3).
    - **Tingkat:** lihat §9. Bukti `pernah_dibantah` adalah potongan teks layar yang paling mirip dengan artikel.
    - **Ciri:** sembilan id terkunci. `permintaan_data_rahasia` (nama tampil "Permintaan kode, data rahasia, atau uang") ditambahkan di sesi ini sebagai ciri kedelapan yang bisa ditandai; LLM ditawari delapan id (tanpa `pernah_dibantah`). Aturan gabung dan pengaman struktural di §8. Template `link_mencurigakan` punya varian per jenis tautan (pemendek, situs gratis, umum). Urutan bukti: sama dari LLM dan regex, regex kuat, LLM saja, regex lemah; bukti identik dideduplikasi.
    - **Rantai LLM** (`pipeline/llm.py`, lewat urllib di kolam thread): Groq `openai/gpt-oss-120b` (`reasoning_effort` low) → Gemini `gemini-3.5-flash-lite` (minimal) → tanpa LLM. Batas waktu 4, 6, dan total 9 detik (dijaga `asyncio.wait_for`). `json_validate_failed` dicoba ulang sekali. 429 dengan waktu tunggu paling lama 3 detik (dan anggaran cukup) ditunggu lalu Groq dicoba sekali lagi; kegagalan lain (429 panjang, 5xx, batas waktu, galat jaringan, JSON rusak, balasan terpotong) langsung pindah penyedia. Klaim kosong tidak dicoba ulang. `max_tokens` 1.000 (completion terukur paling banyak 438). Sakelar `CEKHOAKS_LLM=mati` dan `CEKHOAKS_LLM_CADANGAN=mati` (hanya Groq; teks pasti tidak ke Google).
    - **Temuan penting (13 Oktober 2026):** Groq tidak pernah terpakai pada putaran pertama karena `urllib` mengirim `User-Agent: Python-urllib/3.x` dan Cloudflare di depan Groq membalas 403 (`cf_1010`); Gemini tidak mempermasalahkannya, sehingga kegagalannya tersembunyi. Dibuktikan dengan diagnosa (UA lain 200) dan jumlah panggilan di dasbor Groq. Sekarang setiap permintaan membawa `User-Agent: CekHoaks/<versi>`, dan jejak percobaan (penyedia, status, kode galat, token, durasi) tercatat di log, `app.cek`, dan alat tabel sebagai diagnostik permanen.
    - **Penyamaran** (`samarkan.py`): `[NOMOR]`, `[EMAIL]`, `[AKUN]`, ditambah baris deret akun. `kutipan_ke_asli` memetakan kutipan LLM kembali ke teks asli. Nama orang dan isi pesan tidak disamarkan. Log hanya memuat penyedia, status, kode galat, angka token, dan durasi.
    - **Klaim utama:** berurutan (1) klaim LLM bila kesetiaan sedikitnya 0,5 (rasio kata isi yang ada di teks), tanpa kata penilaian baru, dan tanpa kata ganti orang kedua; (2) bukti `pernah_dibantah` (sedikitnya 4 kata, tanpa kata ganti kedua atau orang pertama, kata sambung di ujung dibuang); (3) heuristik ekstraktif (skor minimum 3,0, atau 4,0 bila klaim LLM tidak kosong tetapi ditolak; kalimat berkata ganti kedua, orang pertama, atau sapaan tidak dipertimbangkan; bonus hanya dari ciri berkeyakinan tinggi); (4) kosong.
    - **Kontrak 0.5:** `url_format_lama` per artikel, `pemeriksaan_terbatas` (`"cek_fakta"` dan/atau `"ai"`; kosong berarti semuanya berjalan; selalu kosong dalam mode paksa), sembilan id ciri. `KontrakApi.kt` diperbarui (`ignoreUnknownKeys = true`).
    - **Alat:** `server/alat/uji_analisis/tahap_b.py` menjalankan 18 gambar dengan atau tanpa LLM (`--tanpa-llm`), dengan jeda dan penghormatan Retry-After, lalu menulis tabel, perbandingan, konfirmasi 03/06/08/07, token, dan daftar bukti yang dibuang. `diagnosa_llm.py` menguji penyedia dengan teks contoh.
    - **Hasil terukur pada 18 gambar uji** (17 terbaca; gambar 15 `teks_tidak_terbaca`): Groq melayani seluruh 17 permintaan tanpa 429 dengan jeda 10 detik; token rata-rata sekitar 1.100 per permintaan (maksimum 1.528); tahap LLM median sekitar 1,0 detik (p95 sekitar 1,5 detik). Tingkat identik dengan Tahap A (tanpa LLM) pada seluruh 17 gambar yang terbaca. Pada Gemini, gambar 07 (infografis edukasi Polres) naik ke `hati_hati` karena satu ciri `judul_clickbait` dari LLM saja; pada Groq tetap `tidak_ditemukan`, dan aturan ciri sedang tunggal menjadi pengaman. Setelah revisi prompt dan pengaman (`tahap_b_groq3`): konfirmasi 03/06/08/07 sesuai, kutipan ditolak 0, klaim 09/13/18 terisi, dan semua bukti yang dibuang layak dibuang. Perbandingan dengan Gemini (`tahap_b`): ciri LLM-saja yang keliru jauh lebih sedikit pada Groq (misalnya `sumber_tidak_jelas` 10 dari 17 gambar menjadi 4 sebelum aturan baru).
    - **Daftar uji manual Sesi 5.5** ada di laporan sesi dan dilengkapi setelah uji HP.
  - **Daftar uji Sesi 5.1** (perintah lengkap di `server/README.md`):
    - [ ] `pytest` lulus (54 test).
    - [ ] `app.cek` pada satu gambar mencetak JSON berformat respons API; dengan `PAKSA_TINGKAT=teks_tidak_terbaca` mencetak galat seragam dan kode keluar 1.
    - [ ] Server dengan `PAKSA_TINGKAT=aman` menolak jalan dengan pesan jelas dan kode keluar bukan nol; setelah variabelnya dihapus, server menyala normal.
    - [ ] Regresi di HP lewat Wi-Fi sama dengan Tahap 4: kirim gambar (giliran kuat → hati_hati → tidak_ditemukan), Batal di tengah analisis (log server `dibatalkan klien`), setiap nilai `PAKSA_TINGKAT`, dan kartu galat saat server mati.
    - [ ] Log server menampilkan satu baris durasi tahap per permintaan, tanpa teks hasil bacaan.
- **Tahap 7 (catatan dari uji tahap 4):** skema `http://` ditambahkan otomatis, tetapi port tidak, jadi "192.168.0.101" menjadi `http://192.168.0.101` (port 80) dan gagal terhubung. Perbaikan: kolom URL diberi placeholder `http://192.168.x.x:8000`, dan kalau alamat `http://` tidak menyebut port, tambahkan `:8000` secara otomatis.
- **Tahap 8 (persiapan showcase):**
  - APK di HP harus build debug, karena HTTP tanpa TLS (cleartext) hanya diizinkan di varian itu.
  - Profil jaringan laptop harus Private (`Set-NetConnectionProfile` lewat PowerShell Administrator). Kalau tidak, HP tidak bisa menghubungi server lewat Wi-Fi atau hotspot.
  - Alamat IP laptop di hotspot HP berubah setiap kali tersambung ulang (contoh: 10.248.150.58 lalu 10.190.18.58). Setiap kali server dijalankan, cek alamat yang dicetak dan perbarui di aplikasi.
  - `adb reverse` hilang setiap kali kabel dicabut atau HP di-restart.
- **Umum:** sistem atau aplikasi tertentu (misalnya halaman pengaturan izin dan aplikasi perbankan) dapat menyembunyikan overlay. Ini perilaku normal.

### Catatan terbuka

Daftar ini dikumpulkan dari sesi 5.1-5.6 supaya tidak hilang antar sesi. Hapus butir yang sudah dikerjakan dan catat keputusannya di bagian tahap masing-masing.

#### Setelah presentasi (dari Sesi 5.6)

- **Ambang teks.** Sudah diputuskan 20 (§11, Keputusan Sesi 5.6). Yang masih terbuka: membedakan teks pendek tanpa makna dari pesan pendek yang bermakna, misalnya dengan skor keyakinan OCR per baris, bukan hanya dengan jumlah karakter.
- **Satu hati_hati pada negatif** di dev (pengumuman) dan di uji (promosi sah): artikel mirip dengan relevansi sekitar 0,5. Butuh data lebih banyak sebelum `relevansi_minimum` dinaikkan.
- **Toleransi OCR selisih 2 huruf** juga mencocokkan varian imbuhan, bukan hanya salah eja. Aman di dev karena skornya di bawah 0,85, tetapi pengaman untuk negatif belum teruji kuat.
- **Recall tanpa artikel sumber rendah** (positif_db uji 8/16, satir 0/3): tingkat hanya bisa naik dari database; satir tanpa artikel butuh ciri baru, bukan ambang.
- **Kesetiaan klaim:** klaim yang membalik polaritas bisa lolos bila kata yang sama muncul tanpa negasi di bagian lain teks; dua salah tolak ringan (singkatan diperluas, parafrasa angka).
- **Stabilitas ciri LLM:** temperature 0 tidak menjamin hasil sama (2 dari 25 gambar dev berbeda ciri akhirnya).
- **Privasi repo publik:** tes memakai nama pejabat sungguhan dalam judul fiktif bertema korupsi, dan generator data memakai nama `@akun` fiktif yang mungkin ada di media sosial. Ganti dengan nama rekaan yang jelas.
- **Butir lama yang belum dinilai ulang:** kata sapaan pada filter klaim heuristik, ukur ulang prompt Sesi 5.5 di `ukur_llm`, `sumber_tidak_jelas` hanya lewat regex, dan pembuangan ciri sedang tunggal.

#### Tahap 6 (UI)

- **Varian keterangan tingkat dari server tidak ada di kontrak.** Pertimbangkan field baru di kontrak mendatang (0.6); setelah itu tambahkan pemetaan label dan cadangan di Android.
- **Uji HP (16 Oktober 2026, Galaxy A55, tema gelap dan terang) lulus.** Onboarding, semua fixture, font 1,3, alur nyata dengan `PAKSA_TINGKAT` kuat, hati_hati, dan tidak_ditemukan (semua kombinasi penilaian), server tidak terjangkau dan "Buka pengaturan", B3 (kunci HP, notifikasi, kotak catatan), serta tiga permintaan dengan LLM Groq sungguhan. Status Tahap 6 di `CLAUDE.md` diperbarui setelah developer menyatakan tahap selesai.
- **Belum dibangun dari prototipe:** statistik, riwayat, dashboard, dan belajar hoaks (keputusan di "Keputusan Sesi 6.1").

#### Tahap 8 (showcase)

- Banner server sudah menyembunyikan adaptor virtual.
- Hotspot HP bisa memberi alamat `10.x`, jadi Wi-Fi kampus tetap perlu diuji sendiri.
- Laptop butuh internet untuk LLM; tanpa internet, `pemeriksaan_terbatas` berisi `"ai"` (uji dengan memutus internet, bukan hanya `CEKHOAKS_LLM=mati`).
- Jalankan `kumpul_tbh.py` mode pembaruan menjelang showcase.
- **Batas token Groq saat beberapa pengunjung berdekatan.** Kuota gratis: 8.000 token per menit per model, sekitar 1.100 token per permintaan, jadi sekitar 7 permintaan per menit (kuota harian 200.000 token, sekitar 180 permintaan). Permintaan yang kena 429 pindah ke cadangan atau kehilangan pemeriksaan AI. Pilihan untuk demo (keputusan di developer):
  - Cadangan Gemini tetap aktif (bawaan): kualitas ciri LLM tetap ada, tetapi teks (setelah penyamaran) bisa sampai ke Google, yang pada kuota gratis boleh memakai dan meninjau isi permintaan.
  - `CEKHOAKS_LLM_CADANGAN=mati`: teks pasti tidak ke Google, tetapi pemeriksaan AI bisa dilewati saat Groq penuh (`pemeriksaan_terbatas` berisi `"ai"`); regex dan cek fakta tetap berjalan.
  - Model Groq kedua (misalnya `qwen/qwen3.8-27b`, terukur di Sesi 5.4a) sebagai cadangan sebelum Gemini: kuota terpisah per model, jadi kapasitas ganda tanpa mengirim teks ke Google. Butuh persetujuan dan pengukuran ulang.
  - `CEKHOAKS_LLM=mati` atau `PAKSA_TINGKAT` sebagai cadangan terakhir (tanpa internet).
  - Atur giliran pengunjung (satu demi satu) sebagai langkah paling murah.

## 14. Di luar cakupan MVP (roadmap)

- iOS melalui share sheet.
- Video: transkripsi audio dengan Whisper, lalu dianalisis sebagai teks.
- Pencocokan gambar dengan database hoaks memakai CLIP.
- Panduan reverse image search yang lebih lengkap.
- Dashboard institusi untuk sekolah dan kampus.
- Deteksi gambar editan atau buatan AI tidak dijanjikan, karena detektor yang ada belum cukup andal; topik ini cukup diangkat sebagai materi edukasi di mode Latih.
