# Alat ukur ciri dan klaim heuristik (Sesi 5.4)

Menjalankan detektor regex (`app/pipeline/ciri.py`) dan klaim heuristik (`app/pipeline/klaim.py`) pada 17 teks OCR dari Sesi 5.4a, lalu membandingkannya dengan keluaran gpt-oss-120b yang sudah tersimpan. Tidak ada panggilan API. Alat ini hanya untuk pengukuran; server tidak memakainya.

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server
.venv\Scripts\python alat\ukur_ciri\ukur.py
```

Venv: `server\.venv`. Masukan: `data_lokal\hasil_llm\gpt-oss-120b\mentah.jsonl`, `data_lokal\hasil_llm\klaim_utama.csv`, dan `data_lokal\hasil_bersih\NN.json` (jalankan `alat\ukur_bersih\langkah_a.py` dulu untuk klaim heuristik). Keluaran: `data_lokal\hasil_ciri\laporan.md`.

Isi laporan:

1. Ciri per gambar: hasil regex (dengan kekuatan pola) dan ciri yang ditandai LLM.
2. Rekap per ciri: berapa kali regex kuat, regex lemah, LLM, dan yang sama-sama menemukan.
3. Hasil penggabungan untuk LLM berhasil (memakai kutipan tersimpan, diverifikasi terhadap teks) dan LLM gagal (`None`), serta jumlah kutipan LLM yang tidak ditemukan di teks.
4. Klaim utama heuristik berdampingan dengan klaim LLM, termasuk gambar yang klaim LLM-nya kosong.

Keterbatasan:

- Ini perbandingan dengan LLM, bukan akurasi: tidak ada label ciri yang benar untuk 18 screenshot uji.
- Pengukuran salah tandai pada teks berlabel (dataset Ghazi) belum ada. Dataset itu belum diunduh, dan tiga dataset Kaggle yang ada di `dataset_mentah\` hanya berisi artikel cek fakta, bukan teks berlabel bukan hoaks. Kalau dataset Ghazi sudah ada, bagian itu ditambahkan setelah format kolomnya diperiksa.
- Teks yang dipakai untuk ciri adalah teks yang dulu dikirim ke LLM (data pribadi disamarkan, belum dibersihkan dari teks UI). Teks yang dipakai untuk klaim heuristik adalah teks bersih dari `hasil_bersih`.
