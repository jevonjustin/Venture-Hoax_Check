# Alat ukur API LLM (Sesi 5.4a)

Mengukur kandidat API LLM untuk langkah analisis teks: mengekstrak `klaim_utama` dan menandai kandidat ciri beserta kutipan bukti dari teks OCR. Alat ini hanya untuk pengukuran. Server (`server/app/`) tidak memakainya. Hasil, usulan penyedia, dan keterbatasan ada di `docs/RANCANGAN_PROYEK.md` (bagian Sesi 5.4a). Ketentuan kuota dan penggunaan data tiap penyedia ada di `docs/REFERENSI.md`.

## Prinsip

- Yang dikirim ke API hanya teks OCR yang sudah disamarkan (`samarkan.py`: nomor telepon, email, dan nama akun `@...`; tautan dibiarkan). Tidak ada gambar yang dikirim.
- Kunci API dibaca dari `server\.env` (tidak ikut repo; templatnya `server\.env.contoh`) hanya di dalam proses. Kunci tidak ditulis ke log, hasil, atau pesan galat. Penyedia dengan kunci kosong dilewati tanpa galat.
- LLM tidak menentukan tingkat indikasi dan tidak boleh menyatakan informasi benar atau salah. `pernah_dibantah` tidak ditawarkan ke LLM karena ditentukan server lewat pencarian database cek fakta.
- Semua penyedia dipanggil lewat endpoint `chat/completions` yang kompatibel dengan OpenAI. Temperature 0. Parameter berpikir dan format keluaran dicoba dari yang paling ketat; kalau API menolak (400), turun ke pilihan berikutnya dan penolakannya dicatat di `pengaturan.json`.

## Berkas

| Berkas | Isi |
|---|---|
| `konfigurasi.py` | Daftar kandidat, endpoint, jeda, dan urutan pilihan parameter |
| `samarkan.py` | Penyamaran data pribadi |
| `prompt.py` | Prompt sistem, penjelasan ciri, skema JSON, dan daftar kata penilaian. Id ciri dibaca dari `server/app/skema.py` |
| `klien.py` | Klien tunggal: validasi, ulang sekali kalau tidak valid, penanganan 429 |
| `metrik.py` | Validasi dan metrik (fungsi murni) |
| `ukur.py` | Perintah `anggaran`, `jalankan`, `ringkas` |
| `tests/` | Uji otomatis tanpa jaringan |

Data hasil ada di `server\data_lokal\hasil_llm\` (masuk `.gitignore`): `<model>\mentah.jsonl` (keluaran mentah per permintaan), `<model>\pengaturan.json`, `metrik.csv`, `pencarian.csv`, `klaim_utama.csv`, dan `laporan.md`.

## Menjalankan

Semua perintah dari folder `server\alat\ukur_llm`, memakai `.venv-cekfakta` (tidak perlu paket tambahan).

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server\alat\ukur_llm

# Anggaran permintaan dan token per model (tanpa jaringan)
..\..\.venv-cekfakta\Scripts\python ukur.py anggaran

# Mengukur satu model (nama: gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite, gpt-oss-120b, qwen3.8-27b)
..\..\.venv-cekfakta\Scripts\python ukur.py jalankan --model gpt-oss-120b

# Uji kecil pada dua gambar
..\..\.venv-cekfakta\Scripts\python ukur.py jalankan --model gpt-oss-120b --hanya 09,10

# Mengulang dari awal untuk satu model: hapus hasilnya dulu
Remove-Item ..\..\data_lokal\hasil_llm\gpt-oss-120b -Recurse

# Metrik, tabel klaim, pencarian, dan stabilitas semua model yang punya hasil
..\..\.venv-cekfakta\Scripts\python ukur.py ringkas

# Uji otomatis
..\..\.venv-cekfakta\Scripts\python -m pytest tests -q
```

Kuota gratis Gemini per hari terbatas (`gemini-3.5-flash` terbukti 20 permintaan per hari per proyek). Kalau pengukuran terhenti karena 429, jalankan perintah yang sama setelah kuota pulih; hanya permintaan tanpa isi yang dikirim ulang.

`jalankan` bisa dihentikan dan dilanjutkan: permintaan yang sudah punya keluaran dilewati (tambahkan `--ulangi` untuk mengirim ulang).

## Definisi metrik

- **Valid:** JSON sesuai skema persis (`klaim_utama` string, `ciri` daftar `{id, kutipan[]}`), dan semua id ada di daftar yang ditawarkan. Keluaran tidak valid diulang sekali; angka valid dihitung dari keluaran akhir, hanya untuk permintaan yang menghasilkan isi. Permintaan tanpa isi (kuota habis, 503, jaringan) dilaporkan terpisah dan bukan kegagalan format.
- **Kejujuran kutipan:** kutipan yang ditemukan di teks masukan (yang sudah disamarkan) setelah normalisasi spasi dan huruf besar-kecil, dibagi seluruh kutipan pada keluaran valid.
- **Klaim bernilai:** `klaim_utama` memuat kata penilaian (benar, salah, hoaks, hoax, fakta, bohong, palsu, dusta, menyesatkan, terbukti, keliru, penipuan, disinformasi) yang tidak ada di teks masukan.
- **Waktu:** lama panggilan HTTP yang menghasilkan keluaran akhir, tanpa jeda tunggu 429.
- **Pencarian:** peringkat artikel sumber (gambar 09 sampai 14) pada top 50 e5-base fp32, memakai teks OCR mentah dibandingkan dengan `klaim_utama`.
- **Stabilitas:** enam teks (01, 04, 09, 11, 14, 17) dikirim dua kali.
