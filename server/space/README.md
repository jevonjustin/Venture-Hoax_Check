---
title: Veritas
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
short_description: Server analisis indikasi hoaks untuk aplikasi Veritas
pinned: false
---

# Server Veritas

Server analisis untuk aplikasi Android Veritas (proyek mata kuliah Venture Creation). Aplikasi mengirim potongan layar, lalu server membaca teksnya (RapidOCR), mencari artikel cek fakta yang mirip (multilingual-e5-base pada database TurnBackHoax/MAFINDO dan klarifikasi Komdigi), memeriksa ciri-ciri hoaks, dan memakai model bahasa (Groq, cadangan Gemini) untuk mengusulkan klaim dan ciri. Hasilnya pemandu, bukan vonis benar atau salah.

Space ini tidak punya halaman web. Endpoint:

- `GET /health`: status dan versi server.
- `POST /analisis`: field multipart `gambar` (JPEG/PNG, paling besar 8 MB).

Kontrak lengkap: `docs/API.md` di repositori GitHub `jevonjustin/Venture-Hoax_Check`.

## Privasi

- Gambar hanya dibaca di memori dan tidak disimpan.
- Teks dikirim ke penyedia model bahasa setelah nomor telepon, email, dan `@akun` disamarkan.
- Log hanya memuat ukuran, dimensi, tingkat, dan durasi, tanpa teks hasil bacaan.

## Konfigurasi Space

| Nama | Jenis | Isi |
|---|---|---|
| `CEKHOAKS_HF_DATASET` | Variable | Dataset berisi database cek fakta dan model e5, diunduh saat menyala |
| `CEKHOAKS_HOST`, `CEKHOAKS_PORT` | Variable | `0.0.0.0` dan `7860` |
| `HF_TOKEN` | Secret | Token baca-saja untuk dataset di atas |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Secret | Kunci penyedia model bahasa |
