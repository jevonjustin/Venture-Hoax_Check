# Alat ukur pembersihan teks (Sesi 5.4)

Mengukur efek `server/app/pipeline/bersih.py` pada 18 screenshot uji. Alat ini hanya untuk pengukuran; server tidak memakainya. Dua langkah dipisah supaya venv tidak tercampur.

| Langkah | Venv | Isi |
|---|---|---|
| `langkah_a.py` | `server\.venv` | RapidOCR dan `bersih.py` pada 18 gambar. Menulis `data_lokal\hasil_bersih\NN.json` dan `laporan_a.md` (kata isi yang dipertahankan, baris yang dibuang per gambar dan per alasan). |
| `langkah_b.py` | `server\.venv-cekfakta` | Pencarian e5-base fp32 untuk gambar 09-14 dengan teks mentah dan teks bersih. Menulis `pencarian.csv` dan `laporan_b.md`. Jalankan setelah langkah A. |

Varian yang diukur: `bawaan` (aturan yang dipakai server) dan `bawaan+baca_juga` (menambah baris "Baca juga" dan "Lihat selengkapnya"; belum menjadi bawaan karena belum pernah muncul di data nyata).

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server
.venv\Scripts\python alat\ukur_bersih\langkah_a.py
.venv-cekfakta\Scripts\python alat\ukur_bersih\langkah_b.py
```

## Aturan bawaan pembersihan

Baris dibuang hanya kalau SELURUH isinya cocok pola UI: bilah status di pita atas, angka interaksi, tombol, menu situs (dan deret menu yang sejajar dengannya), penanda waktu relatif yang angkanya mulai dari 1, jam obrolan yang berdiri sendiri, tombol terjemahan dan label sponsor, baris tanpa huruf atau angka, serta banner sistem WhatsApp (termasuk yang terpecah beberapa baris).

Catatan perilaku yang disengaja:

- **Angka polos di pita atas.** Di pita atas (6% teratas gambar), baris yang seluruh tokennya token status dianggap bilah status, dan angka polos 1-3 digit tanpa tanda persen termasuk token status, karena sinyal dan baterai sering terbaca "4" atau "97". Akibatnya "3" dan "13" di gambar 08 (potongan nomor telepon di header) ikut terbuang. Itu diterima: aturan ini hanya berlaku di pita atas, dan transkripsi menandai keduanya sebagai UI. Di luar pita atas, angka polos tidak pernah dibuang.
- **Waktu relatif** tidak cocok dengan angka 0, jadi ikon yang terbaca "0J" tidak lagi dianggap "0 jam".
- **Jam obrolan** (`12.16`, `7:19PM`, dengan tanda centang atau penanda dibaca/diedit) dibuang di mana pun posisinya, tetapi hanya kalau seluruh baris adalah jam. `Pukul 12.16 saya tiba` tetap dipertahankan.
- **UI aplikasi pesan** ("Bukan kontak · Tidak ada grup yang sama", "Fitur keamanan", "Ketik pesan", "Message", dan placeholder kolom ketik sejenis) dibuang hanya kalau seluruh baris adalah teks itu. Kata "Pesan" saja sengaja tidak termasuk, karena terlalu umum.
- **Banner WhatsApp** dicocokkan pada gabungan baris, dan hanya baris yang seluruhnya berada di dalam banner yang dibuang. Baris yang menggabungkan banner dengan teks lain dipertahankan.

## Ukuran yang dipakai

Kata isi dan kata UI diambil dari `data_lokal\transkripsi\` (baris berawalan `[UI]` dihitung sebagai UI; potongan `[?]` diabaikan). Kata dihitung unik, huruf kecil, minimal 3 huruf. "Dipertahankan" adalah kata isi yang terbaca di teks bersih dibagi yang terbaca di teks mentah.

Keterbatasan:

- Hanya enam gambar yang punya artikel sumber, jadi hasilnya tidak cukup untuk menetapkan ambang skor (ambang final di Sesi 5.6).
- Kata isi yang tidak terbaca OCR tidak diukur di sini.
- Pencocokan kata hanya melihat apakah kata itu ada di teks. Kata isi yang di OCR salah baca tetapi kebetulan sama dengan kata di teks UI akan terhitung hilang ketika baris UI itu dibuang. Contoh: "bisnis" di gambar 01 (OCR membaca isi sebagai "bisniss"; kata "bisnis" di teks mentah hanya berasal dari banner "Chat ini dengan akun bisnis").
