# Alat uji analisis (Sesi 5.5)

Menjalankan pipeline `/analisis` yang sama dengan server pada 18 screenshot di `server\data_lokal\screenshot_uji\`, lalu menulis tabel ringkasan ke `server\data_lokal\hasil_analisis\` beserta perbandingan dengan putaran sebelumnya. Gambar hanya dibaca dari disk. Berkas hasil memuat teks gambar dan klaim, jadi tetap lokal (folder itu masuk `.gitignore`). Semua perintah dijalankan dari folder `server`.

| Berkas | Fungsi |
|---|---|
| `tahap_b.py` | Alat utama: pipeline lengkap, dengan atau tanpa LLM |
| `diagnosa_llm.py` | Menguji penyedia LLM dengan teks contoh (status HTTP, kode galat, durasi). Memanggil API |
| `tahap_a.py` | Putaran awal tanpa LLM (acuan `tahap_a.md`); fungsi bantunya dipakai `tahap_b.py` |

## Satu perintah, 18 gambar

```powershell
cd C:\Users\User\AndroidStudioProjects\CekHoaks\server

# Tanpa LLM: tidak memanggil API, tanpa jaringan
.venv\Scripts\python.exe alat\uji_analisis\tahap_b.py --tanpa-llm --nama tanpa_llm

# Dengan LLM (MEMANGGIL API Groq, cadangan Gemini dimatikan), dibandingkan dengan putaran tanpa LLM
.venv\Scripts\python.exe alat\uji_analisis\tahap_b.py --nama dengan_llm --acuan tanpa_llm.md
```

| Opsi | Bawaan | Fungsi |
|---|---|---|
| `--nama` | `tahap_b` | Nama berkas hasil (`<nama>.md`) |
| `--acuan` | `tahap_a.md` | Berkas pembanding di folder yang sama |
| `--tanpa-llm` | mati | Tidak memanggil API LLM |
| `--jeda` | `10` (0 bila `--tanpa-llm`) | Jeda antar gambar (detik). Kuota gratis Groq 8.000 token per menit, sekitar 1.100 token per gambar |
| `--cadangan` | mati | Mengizinkan Gemini sebagai cadangan. Bawaannya mati supaya hasil seluruhnya Groq dan teks tidak ke Google |
| `--ulang-429` | `3` | Berapa kali satu gambar diulang setelah Groq kena 429 (menunggu sesuai Retry-After) |

## Isi tabel

- Ringkasan: tingkat, penyedia, sumber klaim, kutipan LLM yang ditolak, token (rata-rata dan maksimum), durasi (median dan p95).
- **Konfirmasi:** 03, 06, 08 tetap `hati_hati` dengan `permintaan_data_rahasia` tinggi, dan 07 tetap `tidak_ditemukan` tanpa ciri.
- Tabel per gambar: tingkat dan varian, klaim, rantai percobaan penyedia, ciri, token, sumber klaim.
- Bukti dan ciri yang dibuang oleh pengaman struktural, aturan `sumber_tidak_jelas`, dan aturan ciri sedang tunggal.
- Perbandingan dengan berkas acuan: perubahan tingkat, ciri, dan klaim.
- Rincian per gambar: klaim LLM beserta kesetiaannya, ciri beserta bukti, dan artikel kandidat.
