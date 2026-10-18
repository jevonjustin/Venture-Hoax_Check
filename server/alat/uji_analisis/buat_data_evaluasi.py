"""Membuat data uji berlabel Sesi 5.6 di server/data_lokal/evaluasi/ (gambar, metadata.csv, uji_beku.sha256).

Dijalankan dari folder server:  .venv/Scripts/python alat/uji_analisis/buat_data_evaluasi.py

- Teks positif diambil dari server/data_lokal/cek_fakta/artikel.jsonl saat skrip jalan (tidak ada narasi dari
  database di kode ini). Teks negatif, template penipuan, dan satir ditulis sendiri di bawah.
- Gambar dirender dengan PIL (gelembung chat, unggahan media sosial, tangkapan berita), seed tetap.
- Tidak memanggil LLM, tidak memakai e5, tidak menyentuh berkas di data_lokal/cek_fakta/ (hanya membaca artikel.jsonl).
- Menolak menimpa folder yang sudah dibekukan (uji_beku.sha256 ada) kecuali memakai --paksa.
"""

import argparse
import csv
import hashlib
import io
import json
import random
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SERVER = Path(__file__).resolve().parents[2]
SEED = 20261017
KELUAR = SERVER / "data_lokal" / "evaluasi"
ARTIKEL = SERVER / "data_lokal" / "cek_fakta" / "artikel.jsonl"
SS_ASLI = SERVER / "data_lokal" / "screenshot_uji"
FONT_DIR = Path(r"C:\Windows\Fonts")
KOLOM = ["id", "berkas", "set", "label_harapan", "label_boleh", "kategori", "sumber", "sintetis", "id_artikel_sumber",
         "catatan"]
LEBAR = 1080
ID_NESTLE_CARI = ("nestle",)

# ---------------------------------------------------------------- screenshot asli (penilaian manusia)
# nomor berkas -> (label_harapan, label_boleh, alasan tanpa nama)
SS_LABEL = {
    "01": ("hati_hati", "hati_hati;tidak_ditemukan", "obrolan modus minta kode enam angka lewat SMS dengan dalih salah kirim nomor"),
    "02": ("hati_hati", "kuat;hati_hati;tidak_ditemukan", "pesan berantai tawaran kerja paruh waktu dengan gaji harian tidak masuk akal dan tautan WhatsApp"),
    "03": ("hati_hati", "hati_hati;tidak_ditemukan", "obrolan penipuan dana kembali dengan syarat setor denda di awal"),
    "04": ("tidak_ditemukan", "tidak_ditemukan;hati_hati", "obrolan awal dari nomor tak dikenal, salah sambung, belum ada permintaan atau klaim"),
    "05": ("hati_hati", "kuat;hati_hati;tidak_ditemukan", "peringatan palsu akun akan dinonaktifkan dengan tautan konfirmasi di domain gratis"),
    "06": ("hati_hati", "hati_hati;tidak_ditemukan", "obrolan penipuan pencairan dana dan dalih QRIS bermasalah, mendesak dan minta unlock"),
    "07": ("tidak_ditemukan", "tidak_ditemukan", "infografis edukasi kepolisian tentang pembajakan akun, langkah pengamanan, bukan klaim"),
    "08": ("hati_hati", "hati_hati;tidak_ditemukan;kuat", "obrolan modus pembajakan grup dengan dalih verifikasi dua langkah dan kode lewat SMS"),
    "09": ("kuat", "kuat;hati_hati", "poster lowongan kerja pabrik yang beredar sebagai penipuan, ada artikel pembantahnya"),
    "10": ("kuat", "kuat;hati_hati", "unggahan klaim peringkat kemiskinan negara yang sudah dibantah"),
    "11": ("kuat", "kuat;hati_hati", "unggahan klaim vaksin penyebab penyakit lain, bahasa provokatif, sudah dibantah"),
    "12": ("kuat", "kuat;hati_hati", "tangkapan video kebakaran hutan yang diklaim melintas negara, sudah dibantah"),
    "13": ("kuat", "kuat;hati_hati", "video air laut surut dikaitkan letusan gunung, sudah dibantah"),
    "14": ("kuat", "kuat;hati_hati", "tangkapan berita palsu korupsi pejabat keuangan bertanggal 2026, sudah dibantah"),
    "15": ("teks_tidak_terbaca", "teks_tidak_terbaca", "foto tokoh tanpa tulisan sama sekali"),
    "16": ("kuat", "kuat;hati_hati", "pesan berantai provokatif soal penutupan pesantren, sudah dibantah"),
    "17": ("kuat", "kuat;hati_hati", "unggahan klaim aturan tilang baru, sudah dibantah"),
    "18": ("kuat", "kuat;hati_hati", "video dengan klaim penangkapan massal kepala desa, sudah dibantah"),
}

# ---------------------------------------------------------------- teks buatan sendiri
BERITA = [  # (judul, isi)
    ("Jalan Lingkar Selatan Mulai Dibuka Bertahap", "Pemerintah kota membuka sebagian ruas Jalan Lingkar Selatan untuk kendaraan roda empat mulai pekan ini. Pengerjaan sisa ruas ditargetkan rampung akhir tahun. Petugas lalu lintas akan berjaga pada jam sibuk untuk mengatur arus kendaraan."),
    ("Harga Cabai Berangsur Turun Setelah Panen Raya", "Harga cabai rawit di sejumlah pasar tradisional turun dalam dua pekan terakhir seiring panen raya di daerah sentra. Pedagang menyebut pasokan melimpah, sementara pembeli mengaku lebih leluasa belanja kebutuhan dapur."),
    ("Perpustakaan Daerah Tambah Jam Layanan Akhir Pekan", "Perpustakaan daerah memperpanjang jam layanan pada Sabtu dan Minggu hingga pukul 20.00. Kepala perpustakaan menyebut jumlah pengunjung pelajar meningkat sejak ruang baca anak direnovasi. Layanan peminjaman buku digital juga tetap dibuka."),
    ("Hujan Deras Sebabkan Genangan di Beberapa Titik Kota", "Hujan deras yang mengguyur sejak sore menyebabkan genangan setinggi mata kaki di beberapa titik. Petugas kebersihan membersihkan sampah yang menyumbat saluran air. Genangan surut dalam dua jam setelah hujan reda."),
    ("Turnamen Bulu Tangkis Antarsekolah Digelar Pekan Depan", "Dinas pendidikan menggelar turnamen bulu tangkis antarsekolah menengah pertama pekan depan di gedung olahraga kota. Sebanyak 32 sekolah ikut serta. Pertandingan final dijadwalkan Sabtu sore dan terbuka untuk umum."),
    ("Petani Mulai Gunakan Aplikasi Pemantau Cuaca", "Sejumlah kelompok tani di kabupaten ini mulai memakai aplikasi pemantau cuaca untuk menentukan waktu tanam. Penyuluh pertanian menyebut cara ini membantu mengurangi gagal tanam akibat curah hujan yang tidak menentu."),
    ("Stasiun Kota Siapkan Tambahan Perjalanan Libur Panjang", "Pengelola stasiun menyiapkan tambahan perjalanan kereta untuk libur panjang akhir pekan. Penumpang diimbau membeli tiket lebih awal melalui loket resmi atau aplikasi pemesanan dan datang minimal satu jam sebelum keberangkatan."),
    ("Rumah Sakit Umum Buka Poliklinik Sore", "Rumah sakit umum daerah membuka poliklinik sore untuk melayani pasien yang bekerja pada pagi hari. Pendaftaran dapat dilakukan secara daring atau langsung di loket. Layanan dimulai pukul 16.00 hingga 20.00."),
    ("Festival Kuliner Lokal Hadirkan Seratus Gerai", "Festival kuliner lokal yang digelar di alun-alun menghadirkan seratus gerai makanan dan minuman. Panitia menyebut acara berlangsung tiga hari dan diisi pertunjukan musik daerah setiap malam. Masuk festival tidak dipungut biaya."),
    ("Debit Sungai Naik, Warga Diminta Tetap Waspada", "Petugas pemantau tinggi muka air menyebut debit sungai naik setelah hujan di wilayah hulu. Belum ada warga yang mengungsi. Warga bantaran sungai diminta memantau informasi dari kelurahan dan menyiapkan dokumen penting."),
    ("Sekolah Dasar Terapkan Hari Tanpa Kantong Plastik", "Sebuah sekolah dasar menerapkan hari tanpa kantong plastik setiap Jumat. Siswa membawa bekal dari rumah dengan wadah yang dapat dipakai ulang. Guru mengatakan kebiasaan ini mulai diikuti sekolah lain di sekitarnya."),
    ("Pemkot Perbaiki Lampu Penerangan Jalan di Lima Kecamatan", "Pemerintah kota memperbaiki lampu penerangan jalan umum di lima kecamatan. Perbaikan dikerjakan malam hari agar tidak mengganggu lalu lintas. Warga dapat melaporkan lampu padam melalui nomor layanan pengaduan kota."),
]
EDUKASI = [
    "Tips mengenali hoaks: periksa dulu sumber informasinya. Jika tidak ada nama media atau tanggal yang jelas, jangan langsung percaya. Cari berita yang sama di situs resmi sebelum membagikannya ke grup keluarga.",
    "Waspada penipuan OTP. Kode OTP bersifat rahasia dan hanya untuk Anda. Jangan bagikan kode OTP kepada siapa pun, termasuk pihak yang mengaku petugas bank atau kurir. Petugas resmi tidak pernah meminta kode tersebut.",
    "Literasi digital: sebelum menyebarkan pesan berantai, tanyakan tiga hal. Siapa yang menulis? Kapan ditulis? Apakah ada bukti dari sumber lain? Pesan yang memancing emosi dan menyuruh segera disebarkan patut dicurigai sebagai hoaks.",
    "Ciri-ciri hoaks yang sering muncul: judul bernada heboh, memakai huruf kapital berlebihan, tidak mencantumkan sumber, dan mengajak untuk menyebarkan. Biasakan membaca isi berita sampai habis, bukan hanya judulnya.",
    "Cara memeriksa foto yang dicurigai: lakukan pencarian gambar terbalik untuk melihat kapan foto pertama kali muncul. Foto lama sering dipakai ulang seolah-olah peristiwa baru. Jangan bagikan sebelum yakin.",
    "Tautan mencurigakan jangan diklik. Periksa alamat situsnya dengan teliti, karena penipu sering memakai nama mirip situs resmi. Jangan memasukkan kata sandi atau data kartu pada tautan dari pesan yang tidak dikenal.",
    "Mari bijak bermedia sosial. Jika menerima kabar yang belum jelas kebenarannya, tahan dulu jari Anda. Tanyakan ke orang yang paham atau cek di situs pemeriksa fakta. Satu bagikan yang keliru bisa merugikan banyak orang.",
    "Penipuan berkedok lowongan kerja biasanya meminta biaya pendaftaran atau transfer di awal. Perusahaan resmi tidak memungut biaya perekrutan. Pastikan lowongan dari situs atau akun resmi perusahaan sebelum mengirim data diri.",
    "Hoaks kesehatan berbahaya karena dapat membuat orang menunda berobat. Rujuk informasi kesehatan dari tenaga medis dan situs kementerian kesehatan, dan jangan mudah percaya pada resep ajaib yang dibagikan lewat pesan berantai.",
    "Kenali pola penipuan telepon: pelaku menciptakan rasa panik dan meminta transfer segera. Tenangkan diri, tutup telepon, lalu hubungi nomor resmi layanan pelanggan. Jangan pernah membagikan PIN atau kode verifikasi.",
]
PENGUMUMAN = [
    "PENGUMUMAN. Kepada seluruh wali murid kelas 6, pembagian rapor semester ganjil dilaksanakan hari Sabtu pukul 08.00 sampai 11.00 di ruang kelas masing-masing. Mohon hadir tepat waktu dan membawa kartu identitas wali murid.",
    "Pemberitahuan dari pengurus RT 05. Kerja bakti membersihkan saluran air akan dilaksanakan hari Minggu pukul 07.00. Warga diharapkan membawa cangkul atau sapu. Konsumsi disediakan oleh ibu-ibu PKK.",
    "Informasi pemadaman listrik. Akan ada pemadaman listrik terencana pada hari Rabu pukul 09.00 sampai 14.00 di sebagian wilayah kecamatan untuk pemeliharaan jaringan. Mohon maaf atas ketidaknyamanannya.",
    "Pengumuman kantor kelurahan: layanan pembuatan dan perpanjangan KTP ditutup pada hari Jumat karena ada kegiatan internal. Layanan dibuka kembali hari Senin pukul 08.00. Informasi lebih lanjut hubungi loket pelayanan.",
    "Puskesmas mengadakan imunisasi gratis untuk balita pada hari Selasa pukul 08.00 sampai 11.00. Orang tua diharapkan membawa buku KIA. Imunisasi diberikan tanpa dipungut biaya.",
    "Dari panitia lomba 17 Agustus lingkungan: pendaftaran lomba anak dibuka sampai hari Kamis. Daftar langsung ke sekretariat di pos ronda. Jadwal lomba akan diumumkan di grup warga.",
    "Pengumuman perpanjangan masa pembayaran pajak kendaraan bermotor tahunan sampai akhir bulan. Pembayaran dapat dilakukan di kantor layanan bersama atau melalui kanal resmi pemerintah daerah.",
    "Disampaikan kepada seluruh karyawan, rapat evaluasi bulanan dilaksanakan Kamis pukul 13.30 di ruang rapat lantai dua. Mohon membawa laporan kerja masing-masing dan hadir tepat waktu.",
    "Pemberitahuan: masjid lingkungan akan mengadakan pengajian rutin pada malam Jumat setelah salat Isya. Jamaah dipersilakan hadir. Mohon menjaga ketertiban parkir kendaraan di depan masjid.",
    "Dinas kebersihan memberitahukan perubahan jadwal pengangkutan sampah. Mulai bulan depan, pengangkutan dilakukan pada hari Senin, Rabu, dan Sabtu pukul 06.00. Sampah mohon dikeluarkan sebelum jam tersebut.",
]
OBROLAN = [  # daftar pesan (sisi, teks)
    [("in", "Mas, besok jadi jemput adik di sekolah ya?"), ("out", "Jadi bu, jam 11 saya sudah di sana"), ("in", "Makasih ya mas, nanti ibu transfer uang bensinnya"), ("out", "Nggak usah bu, santai saja")],
    [("in", "Pulsa ibu habis nih, tolong isiin yang 20 ribu ya nak, nanti ibu ganti pas ketemu"), ("out", "Siap bu, sudah aku isiin. Cek ya"), ("in", "Udah masuk, makasih nak. Hati-hati di jalan")],
    [("in", "Bro, jadi nonton futsal malam ini?"), ("out", "Jadi, kumpul di lapangan jam 8"), ("in", "Oke, aku bawa bola sama minum. Kamu transfer dulu patungan sewa lapangannya ya"), ("out", "Sudah ku transfer tadi, cek aja")],
    [("in", "Bu, arisan bulan ini di rumah siapa ya?"), ("out", "Di rumah Bu Ani, hari Minggu jam 4 sore"), ("in", "Siap bu, saya bawa kue. Uang arisan nanti saya setor langsung ya"), ("out", "Iya bu, ditunggu")],
    [("in", "Mas, paketnya sudah sampai di rumah, tadi diterima ibu"), ("out", "Oke makasih ya, isinya aman?"), ("in", "Aman mas, tidak ada yang rusak. Besok mas mampir ya")],
    [("out", "Pak, rapat RT kapan jadinya?"), ("in", "Malam Jumat habis Isya di rumah pak RT"), ("out", "Siap pak, saya hadir. Iuran bulan ini saya titip ke ibu ya"), ("in", "Boleh, nanti saya catat")],
    [("in", "Kak, tugas kelompok udah kamu kirim ke grup belum?"), ("out", "Udah dari tadi pagi kak, cek aja di grup"), ("in", "Oh iya udah ada. Makasih ya, nanti aku rapikan dulu sebelum dikumpul")],
    [("in", "Nak, jangan lupa bayar listrik ya, token tinggal sedikit"), ("out", "Iya bu, nanti sore aku beli tokennya di minimarket"), ("in", "Ibu kirim uangnya lewat transfer ya, sebentar"), ("out", "Oke bu, terima kasih")],
    [("in", "Mas Dion, mobilnya sudah selesai diservis, bisa diambil sore ini"), ("out", "Baik mas, saya ambil habis jam kantor. Totalnya berapa ya?"), ("in", "Sekitar 450 ribu mas, bisa transfer atau bayar langsung")],
    [("in", "Bu guru, anak saya besok izin tidak masuk karena demam"), ("out", "Baik bu, semoga cepat sembuh. Nanti tugasnya saya kirim lewat grup"), ("in", "Terima kasih bu guru")],
]
PROMOSI = [
    "Promo akhir pekan di Toko Sumber Rejeki! Diskon 20% untuk semua perlengkapan dapur, berlaku Sabtu dan Minggu. Belanja minimal Rp100.000 gratis tas belanja. Kunjungi toko kami atau pesan lewat kasir.",
    "Nikmati cashback 10% untuk pembayaran kartu debit di gerai mitra selama bulan ini. Syarat dan ketentuan berlaku. Informasi lengkap tersedia di kantor cabang dan situs resmi bank. Kami tidak pernah meminta OTP atau PIN.",
    "Toko Buku Cahaya mengadakan obral buku sekolah. Diskon sampai 30% untuk buku pelajaran dan alat tulis menjelang tahun ajaran baru. Promo berlaku selama persediaan masih ada, langsung datang ke toko.",
    "Warung Bu Tini buka cabang baru! Beli dua porsi nasi uduk, gratis satu es teh. Promo berlaku selama satu minggu pertama pembukaan, setiap hari pukul 06.00 sampai 14.00. Ditunggu kedatangannya.",
    "Beli tiket kereta lewat aplikasi resmi dan dapatkan potongan harga 15% untuk perjalanan di hari kerja. Promo berlaku untuk pembelian sampai akhir bulan. Syarat dan ketentuan tertera di dalam aplikasi.",
    "Bengkel Maju Jaya: ganti oli gratis jasa pasang untuk pembelian oli dua liter. Promo selama bulan ini. Servis berkala juga diskon 10%. Reservasi bisa lewat telepon bengkel atau datang langsung.",
    "Sedang ada pameran furnitur di aula kota. Diskon sampai 40% untuk meja, kursi, dan lemari buatan pengrajin lokal. Pameran berlangsung tiga hari mulai pukul 10.00 sampai 18.00. Masuk gratis.",
    "Klinik gigi kami memberi potongan 25% untuk pembersihan karang gigi bagi pelajar dengan menunjukkan kartu pelajar. Promo berlaku hari Senin sampai Kamis. Pendaftaran langsung di meja resepsionis.",
]
PENIPUAN_TEMPLAT = [
    "PERHATIAN! Kami dari layanan nasabah bank. Akun Anda terdeteksi aktivitas mencurigakan dan akan diblokir hari ini. Untuk mencegahnya, segera kirimkan kode OTP yang baru saja masuk ke nomor Anda kepada petugas kami. Jika tidak, saldo tidak dapat diselamatkan.",
    "Paket Anda gagal dikirim karena alamat kurang lengkap. Silakan unduh aplikasi resmi kurir di file berikut: Foto_Paket.apk untuk melihat resi dan konfirmasi alamat. Paket akan dikembalikan jika tidak dikonfirmasi dalam 24 jam.",
    "SELAMAT! Nomor Anda terpilih sebagai pemenang undian berhadiah satu unit mobil dari program ulang tahun. Untuk klaim hadiah, hubungi panitia di nomor WhatsApp berikut dan transfer biaya administrasi Rp500.000 terlebih dahulu.",
    "Butuh dana cepat? Pinjaman online cair 5 juta tanpa jaminan, proses 5 menit, tanpa survei. Cukup unggah KTP dan foto selfie lalu transfer biaya asuransi Rp250.000. Data aman dan bunga ringan. Daftar sekarang lewat tautan ini.",
    "DIBUTUHKAN karyawan admin online, kerja dari rumah, gaji Rp8.000.000 per bulan tanpa pengalaman. Hanya modal HP. Kirim data diri dan bayar biaya seragam serta pelatihan Rp300.000 ke rekening panitia rekrutmen. Kuota terbatas, daftar hari ini.",
    "Mah, ini aku pakai nomor baru. HP yang lama rusak kena air. Tolong isiin pulsa dulu ya, nanti aku ganti. Penting banget, aku lagi butuh. Kirim ke nomor ini dan jangan bilang ke siapa-siapa dulu ya mah.",
    "Pemberitahuan: akun mobile banking Anda akan ditutup permanen karena belum melakukan pembaruan data. Klik tautan berikut untuk memperbarui data kartu dan PIN Anda dalam waktu satu jam. Abaikan pesan ini berarti Anda menyetujui penutupan akun.",
    "Undangan pernikahan digital. Kepada Yth. Bapak/Ibu, kami mengundang Anda pada acara pernikahan kami. Silakan unduh undangan resmi lewat berkas Undangan_Nikah.apk dan buka aplikasinya untuk melihat lokasi acara.",
    "Info dari PLN: token listrik Anda mendapat subsidi khusus bulan ini. Untuk menerima potongan 50%, masukkan nomor meter dan kode verifikasi yang dikirim lewat SMS pada tautan berikut. Batas waktu hanya hari ini.",
]
SATIR_TEMPLAT = [
    "BERITA TERKINI: Kucing tetangga resmi dilantik menjadi Ketua RT setelah menang telak dalam pemilihan. Dalam pidato pertamanya, sang kucing berjanji menambah jatah ikan asin untuk seluruh warga dan melarang anjing lewat depan rumah. Warga bersorak. Berita ini fiktif, hanya hiburan.",
    "Satir: Pemerintah umumkan hari Senin dihapus dari kalender demi kesehatan mental seluruh rakyat. Mulai pekan depan, setelah Minggu langsung Selasa. Pengamat menyebut kebijakan ini disambut gembira kecuali oleh hari Selasa yang merasa keberatan.",
    "PARODI: Peneliti temukan bahwa sinyal Wi-Fi paling kencang ada di rumah tetangga yang kata sandinya tidak diketahui. Penelitian menyimpulkan bahwa jarak ke sumber sinyal berbanding terbalik dengan keinginan untuk menumpang. Hanya bercanda.",
    "Humor: Seorang pria mengaku sudah olahraga seminggu penuh, yaitu dengan membuka aplikasi olahraga setiap pagi. Berat badannya belum berubah tetapi penyimpanan HP-nya penuh dengan video senam. Tulisan ini murni satir untuk hiburan.",
]
SINONIM = {
    "beredar": "tersebar", "diklaim": "disebut-sebut", "video": "rekaman", "menampilkan": "memperlihatkan", "foto": "gambar",
    "pesan": "kabar", "unggahan": "postingan", "mengatakan": "menyebut", "menyebutkan": "menuturkan", "pemerintah": "pihak berwenang",
    "warga": "masyarakat", "kabar": "informasi", "akan": "bakal", "sudah": "telah", "banyak": "sejumlah", "mulai": "segera",
    "resmi": "sah", "terbaru": "paling baru", "peristiwa": "kejadian", "viral": "ramai dibicarakan",
}
PREFIKS_BERANTAI = ["INFO PENTING", "HARAP DIBACA", "PERINGATAN KERAS", "BREAKING"]
EMOJI_BERANTAI = ["\U0001F6A8", "\U0001F4E2", "\u26A0\uFE0F", "\U0001F525"]
SUFIKS_BERANTAI = ["SEBARKAN SEBELUM TERLAMBAT!!", "SEBARKAN KE SEMUA GRUP!", "Mohon dibagikan ke keluarga dan teman \U0001F64F", "TOLONG SEBARKAN DEMI KEBAIKAN BERSAMA!!"]
PORTAL = ["Warta Nusa Online", "Kabar Harian ID", "Suara Kota Daring", "Info Terkini Nusantara", "Berita Pagi.co"]
AKUN = [("Info Warga Sekitar", "@infowarga_id"), ("Kabar Hari Ini", "@kabarharini"), ("Pojok Berita", "@pojokberita"), ("Seputar Kota", "@seputarkota"), ("Infografis Nusantara", "@infografis_nus")]
KONTAK = ["Mama", "Grup Keluarga", "Bu RT", "Mas Dion", "Kak Rani", "Grup Alumni", "Pak Guru", "Tetangga"]
HURUF = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf", "verdana.ttf"]
HURUF_TEBAL = {"segoeui.ttf": "segoeuib.ttf", "arial.ttf": "arialbd.ttf", "calibri.ttf": "calibrib.ttf", "tahoma.ttf": "tahomabd.ttf", "verdana.ttf": "verdanab.ttf"}
TAMBAH_UKURAN = {"calibri.ttf": 5, "verdana.ttf": -3, "tahoma.ttf": 0, "arial.ttf": 0, "segoeui.ttf": 0}
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


# ---------------------------------------------------------------- rendering
class Huruf:
    def __init__(self, nama: str, ukuran: int, tebal: bool = False):
        self.nama, self.ukuran, self.tebal = nama, ukuran, tebal
        berkas = HURUF_TEBAL[nama] if tebal else nama
        self.f = ImageFont.truetype(str(FONT_DIR / berkas), ukuran + TAMBAH_UKURAN[nama])
        self.emoji = ImageFont.truetype(str(FONT_DIR / "seguiemj.ttf"), ukuran)


def _emoji(c: str) -> bool:
    return ord(c) >= 0x1F000 or 0x2600 <= ord(c) <= 0x27BF or c == "\uFE0F"


def _runs(teks: str):
    hasil: list[tuple[bool, str]] = []
    for c in teks:
        e = _emoji(c)
        if hasil and hasil[-1][0] == e:
            hasil[-1] = (e, hasil[-1][1] + c)
        else:
            hasil.append((e, c))
    return hasil


def ukur(h: Huruf, teks: str) -> float:
    return sum((h.emoji if e else h.f).getlength(s) for e, s in _runs(teks))


def tulis(d: ImageDraw.ImageDraw, xy, teks: str, h: Huruf, warna) -> None:
    x, y = xy
    for e, s in _runs(teks):
        if e:
            d.text((x, y), s, font=h.emoji, embedded_color=True)
            x += h.emoji.getlength(s)
        else:
            d.text((x, y), s, font=h.f, fill=warna)
            x += h.f.getlength(s)


def bungkus(h: Huruf, teks: str, lebar: int) -> list[str]:
    baris: list[str] = []
    for para in teks.split("\n"):
        kini = ""
        for kata in para.split():
            coba = (kini + " " + kata).strip()
            if ukur(h, coba) <= lebar or not kini:
                kini = coba
            else:
                baris.append(kini)
                kini = kata
        baris.append(kini)
    return baris


def tinggi_baris(h: Huruf) -> int:
    return int((h.ukuran + TAMBAH_UKURAN[h.nama]) * 1.35)


def blok(d, x, y, teks, h, warna, lebar) -> int:
    for b in bungkus(h, teks, lebar):
        tulis(d, (x, y), b, h, warna)
        y += tinggi_baris(h)
    return y


def tinggi_blok(h, teks, lebar) -> int:
    return len(bungkus(h, teks, lebar)) * tinggi_baris(h)


def _kanvas(tinggi, warna):
    im = Image.new("RGB", (LEBAR, max(tinggi, 80)), warna)
    return im, ImageDraw.Draw(im)


def jam(rng) -> str:
    return f"{rng.randint(5, 23):02d}.{rng.randint(0, 59):02d}"


def render_chat(pesan, rng, diteruskan=False, header=True, lebar_gelembung=840, tampil_jam=True):
    gelap = rng.random() < 0.4
    nama = rng.choice(HURUF)
    ukuran = rng.randint(32, 40)
    h = Huruf(nama, ukuran)
    hk = Huruf(nama, 24)
    latar = (11, 20, 26) if gelap else (236, 229, 221)
    warna = {"in": ((32, 44, 51) if gelap else (255, 255, 255)), "out": ((0, 92, 75) if gelap else (220, 248, 198))}
    teks_w = (233, 237, 239) if gelap else (17, 27, 33)
    abu = (140, 160, 170) if gelap else (110, 120, 125)
    pad = 24
    # hitung tinggi
    bagian = []
    total = (96 if header else 20) + 24
    for sisi, t in pesan:
        isi = bungkus(h, t, lebar_gelembung - 2 * pad)
        w = max(ukur(h, b) for b in isi)
        tinggi = len(isi) * tinggi_baris(h) + 2 * pad + 20 + (36 if diteruskan and sisi == "in" and not bagian else 0)
        bagian.append((sisi, t, isi, w, tinggi))
        total += tinggi + 20
    im, d = _kanvas(total + 20, latar)
    y = 20
    if header:
        d.rectangle([0, 0, LEBAR, 96], fill=(31, 44, 52) if gelap else (7, 94, 84))
        d.ellipse([60, 20, 116, 76], fill=(150, 170, 180))
        tulis(d, (136, 24), rng.choice(KONTAK), Huruf(nama, 34, True), (255, 255, 255))
        y = 96 + 24
    for i, (sisi, t, isi, w, tinggi) in enumerate(bagian):
        lebar_g = int(max(w, ukur(hk, "00.00") + 90) + 2 * pad)
        x0 = 40 if sisi == "in" else LEBAR - 40 - lebar_g
        d.rounded_rectangle([x0, y, x0 + lebar_g, y + tinggi], radius=24, fill=warna[sisi])
        yy = y + pad
        if diteruskan and sisi == "in" and i == 0:
            tulis(d, (x0 + pad, yy), "Diteruskan", Huruf(nama, 26), abu)
            yy += 36
        for b in isi:
            tulis(d, (x0 + pad, yy), b, h, teks_w)
            yy += tinggi_baris(h)
        if tampil_jam:
            tulis(d, (x0 + lebar_g - pad - ukur(hk, "00.00"), y + tinggi - 38), jam(rng), hk, abu)
        y += tinggi + 20
    return im


def render_sosial(teks, rng):
    gelap = rng.random() < 0.4
    nama = rng.choice(HURUF)
    h = Huruf(nama, rng.randint(32, 40))
    latar = (21, 32, 43) if gelap else (255, 255, 255)
    t_w = (230, 236, 240) if gelap else (20, 23, 26)
    abu = (136, 153, 166) if gelap else (101, 119, 134)
    akun, handle = rng.choice(AKUN)
    lebar_t = LEBAR - 80
    tinggi = 150 + tinggi_blok(h, teks, lebar_t) + 40 + 100
    im, d = _kanvas(tinggi, latar)
    warna_avatar = rng.choice([(29, 155, 240), (244, 93, 34), (120, 86, 255), (0, 186, 124)])
    d.ellipse([40, 30, 116, 106], fill=warna_avatar)
    tulis(d, (136, 28), akun, Huruf(nama, 34, True), t_w)
    tulis(d, (136, 72), f"{handle} \u00B7 {rng.randint(1, 23)} jam", Huruf(nama, 28), abu)
    y = blok(d, 40, 140, teks, h, t_w, lebar_t) + 30
    d.line([40, y, LEBAR - 40, y], fill=abu, width=1)
    pk = Huruf(nama, 28)
    tulis(d, (40, y + 24), f"{rng.randint(1, 9)},{rng.randint(0, 9)} rb suka    {rng.randint(10, 900)} komentar    {rng.randint(10, 900)} dibagikan", pk, abu)
    return im


def render_berita(judul, isi, rng):
    nama = rng.choice(HURUF)
    portal = rng.choice(PORTAL)
    warna_bar = rng.choice([(200, 30, 40), (20, 80, 160), (30, 120, 70), (60, 60, 70)])
    hj = Huruf(nama, rng.randint(42, 46), True)
    hb = Huruf(nama, rng.randint(32, 38))
    hs = Huruf(nama, 28)
    lebar_t = LEBAR - 100
    tgl = f"{rng.choice(HARI)}, {rng.randint(1, 28)} {rng.choice(BULAN)} {rng.randint(2023, 2026)} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d} WIB"
    tinggi = 110 + 40 + tinggi_blok(hj, judul, lebar_t) + 70 + tinggi_blok(hb, isi, lebar_t) + 60
    im, d = _kanvas(tinggi, (255, 255, 255))
    d.rectangle([0, 0, LEBAR, 90], fill=warna_bar)
    tulis(d, (50, 22), portal, Huruf(nama, 40, True), (255, 255, 255))
    y = blok(d, 50, 130, judul, hj, (15, 15, 15), lebar_t) + 10
    tulis(d, (50, y), tgl, hs, (120, 120, 120))
    y += 60
    blok(d, 50, y, isi, hb, (35, 35, 35), lebar_t)
    return im


def render_polos(teks, rng):
    """Gelembung kecil tanpa header, untuk teks sangat pendek."""
    return render_chat([("in", teks)], rng, header=False, lebar_gelembung=900, tampil_jam=False)


def render_tanpa_teks(rng):
    """Pola tanpa tulisan: gradasi berderau dengan beberapa bentuk."""
    w, hh = LEBAR, 700
    im = Image.new("RGB", (w, hh))
    px = im.load()
    a = [rng.randint(40, 200) for _ in range(3)]
    b = [rng.randint(40, 200) for _ in range(3)]
    for y in range(hh):
        for x in range(0, w):
            t = (x / w + y / hh) / 2
            n = rng.randint(-12, 12)
            px[x, y] = tuple(max(0, min(255, int(a[k] * (1 - t) + b[k] * t) + n)) for k in range(3))
    d = ImageDraw.Draw(im)
    for _ in range(9):
        x, y = rng.randint(0, w - 200), rng.randint(0, hh - 200)
        r = rng.randint(60, 200)
        d.ellipse([x, y, x + r, y + r], fill=tuple(rng.randint(30, 230) for _ in range(3)))
    return im


def simpan_jpeg(im: Image.Image, jalur: Path, rng) -> int:
    q = rng.randint(70, 85)
    im.save(jalur, "JPEG", quality=q)
    return q


# ---------------------------------------------------------------- bahan dari database
def bersihkan_narasi(n: str) -> str:
    n = re.sub(r"https?://\S+", "", n or "")
    n = re.split(r"(?im)^\s*(penjelasan|kesimpulan|fakta|hasil cek|referensi|sumber)\b", n)[0]
    n = re.sub(r"(?im)^\s*\[?(narasi[^:\n]*)\]?\s*[:\n]", "", n, count=1)
    n = re.sub(r"[ \t]+", " ", n)
    n = re.sub(r"\n\s*\n+", "\n", n).strip()
    return n


def potong(n: str, maks: int = 420) -> str:
    if len(n) <= maks:
        return n
    kalimat = re.split(r"(?<=[.!?])\s+", n)
    hasil = ""
    for k in kalimat:
        if len(hasil) + len(k) + 1 > maks and hasil:
            break
        hasil = (hasil + " " + k).strip()
    return hasil[:maks]


def kalimat_dari(n: str) -> list[str]:
    return [k.strip() for k in re.split(r"(?<=[.!?])\s+|\n", n) if k.strip()]


def sinonimkan(teks: str) -> str:
    def ganti(m):
        k = m.group(0)
        s = SINONIM[k.lower()]
        return s.capitalize() if k[0].isupper() else s

    return re.sub(r"\b(" + "|".join(SINONIM) + r")\b", ganti, teks, flags=re.IGNORECASE)


def parafrase(teks: str, mode: int, rng) -> str:
    ks = kalimat_dari(teks)
    if mode == 0:  # sinonim + susunan ulang kalimat
        if len(ks) >= 3:
            ks = ks[-1:] + ks[:-1]
        elif len(ks) == 2:
            ks = ks[::-1]
        return sinonimkan(" ".join(ks))
    # gaya pesan berantai
    if not ks:
        return teks
    k = rng.randrange(len(PREFIKS_BERANTAI))
    kepala = f"{EMOJI_BERANTAI[k]} {PREFIKS_BERANTAI[k]} {EMOJI_BERANTAI[k]}"
    isi = sinonimkan(ks[0].upper() + (" " + " ".join(ks[1:]) if len(ks) > 1 else ""))
    return "\n".join([kepala, isi, rng.choice(SUFIKS_BERANTAI)])


def muat_artikel() -> list[dict]:
    with open(ARTIKEL, encoding="utf-8") as f:
        return [json.loads(b) for b in f if b.strip()]


def pilih_positif(artikel, rng, terpakai: set, n: int):
    kandidat = defaultdict(list)
    for a in artikel:
        if a.get("label") != "salah" or a["id"] in terpakai:
            continue
        isi = bersihkan_narasi(a.get("narasi") or "")
        if len(isi) < 180 or "http" in isi.lower():
            continue
        kandidat[str(a.get("tanggal") or "")[:4]].append(a["id"])
    tahun = sorted(kandidat)
    for t in tahun:
        kandidat[t].sort()
        rng.shuffle(kandidat[t])
    peta = {a["id"]: a for a in artikel}
    hasil = []
    i = 0
    while len(hasil) < n and any(kandidat.values()):
        t = tahun[i % len(tahun)]
        i += 1
        if kandidat[t]:
            hasil.append(peta[kandidat[t].pop()])
    return hasil


KELOMPOK_PENIPUAN = [
    r"\botp\b", r"kurir|paket|\.apk|\bapk\b", r"hadiah|undian", r"pinjol|pinjaman", r"lowongan|loker|rekrut",
    r"pulsa", r"blokir|diblokir",
]


def pilih_penipuan(artikel, rng, terpakai: set):
    penipuan = sorted((a for a in artikel if a.get("label") == "penipuan" and a["id"] not in terpakai), key=lambda a: a["id"])
    nestle = [a for a in penipuan if any(k in (a.get("judul") or "").lower() for k in ID_NESTLE_CARI)]
    hasil = []
    pakai = set()
    for a in nestle[:1]:
        hasil.append(a)
        pakai.add(a["id"])
    for pola in KELOMPOK_PENIPUAN:
        cand = [a for a in penipuan if a["id"] not in pakai and len(bersihkan_narasi(a.get("narasi") or "")) >= 120
                and "http" not in bersihkan_narasi(a.get("narasi") or "").lower()
                and re.search(pola, ((a.get("judul") or "") + " " + (a.get("narasi") or "")).lower())]
        if cand:
            a = rng.choice(cand)
            hasil.append(a)
            pakai.add(a["id"])
    return hasil


def pilih_satir(artikel, rng, terpakai: set, n: int):
    cand = sorted((a for a in artikel if a.get("label") == "satir" and a["id"] not in terpakai
                   and len(bersihkan_narasi(a.get("narasi") or "")) >= 150), key=lambda a: a["id"])
    rng.shuffle(cand)
    return cand[:n]


# ---------------------------------------------------------------- perakitan
def bangun(paksa: bool) -> int:
    if (KELUAR / "uji_beku.sha256").exists() and not paksa:
        print("uji_beku.sha256 sudah ada: set uji sudah dibekukan. Pakai --paksa hanya bila memang sengaja membangun ulang.")
        return 1
    if not ARTIKEL.exists():
        print("artikel.jsonl tidak ditemukan")
        return 1
    # item: dict(kategori, jenis, isi, label, boleh, sumber, sintetis, idsumber, catatan, berkas_asal)
    rng_p = random.Random(SEED)
    artikel = muat_artikel()
    item: list[dict] = []

    # 1. screenshot asli
    for nomor, (lab, boleh, alasan) in sorted(SS_LABEL.items()):
        asal = next(SS_ASLI.glob(nomor + ".*"))
        item.append(dict(kategori="screenshot_asli", jenis="salin", isi=asal, label=lab, boleh=boleh,
                         sumber="screenshot_uji", sintetis="tidak", idsumber="", catatan=f"gambar {nomor}: {alasan}"))

    terpakai: set = set()
    # 2. penipuan (dibangun lebih dulu agar artikelnya tidak dipakai positif_db)
    pen = pilih_penipuan(artikel, rng_p, terpakai)
    for j, a in enumerate(pen):
        terpakai.add(a["id"])
        isi = potong(bersihkan_narasi(a["narasi"]))
        item.append(dict(kategori="penipuan", jenis="chat" if j % 2 == 0 else "sosial", isi=isi, label="kuat", boleh="kuat;hati_hati",
                         sumber=a.get("asal_data") or "artikel.jsonl", sintetis="ya", idsumber=a["id"], catatan="penipuan dari artikel, verbatim"))
    for j, t in enumerate(PENIPUAN_TEMPLAT):
        item.append(dict(kategori="penipuan", jenis="chat" if j % 3 != 2 else "sosial", isi=t, label="hati_hati",
                         boleh="hati_hati;tidak_ditemukan", sumber="buatan_sendiri", sintetis="ya", idsumber="", catatan="templat penipuan buatan sendiri"))
    # 3. satir
    sat = pilih_satir(artikel, rng_p, terpakai, 4)
    for a in sat:
        terpakai.add(a["id"])
        item.append(dict(kategori="satir", jenis="sosial", isi=potong(bersihkan_narasi(a["narasi"])), label="hati_hati",
                         boleh="hati_hati;tidak_ditemukan", sumber=a.get("asal_data") or "artikel.jsonl", sintetis="ya", idsumber=a["id"], catatan="satir dari artikel"))
    for j, t in enumerate(SATIR_TEMPLAT[: 8 - len(sat)]):
        item.append(dict(kategori="satir", jenis="berita" if j % 2 else "sosial", isi=t, label="hati_hati", boleh="hati_hati;tidak_ditemukan",
                         sumber="buatan_sendiri", sintetis="ya", idsumber="", catatan="satir buatan sendiri, jelas parodi"))
    # 4. positif_db
    pos = pilih_positif(artikel, rng_p, terpakai | {a["id"] for a in pen}, 40)
    for j, a in enumerate(pos):
        dasar = potong(bersihkan_narasi(a["narasi"]))
        if j % 2 == 0:
            isi, cat = dasar, "verbatim"
        else:
            mode = (j // 2) % 2
            isi, cat = parafrase(dasar, mode, random.Random(SEED + j)), ("parafrase sinonim dan susunan ulang" if mode == 0 else "parafrase gaya pesan berantai")
        item.append(dict(kategori="positif_db", jenis=("chat", "sosial", "berita")[j % 3], isi=isi, label="kuat", boleh="kuat;hati_hati",
                         sumber=a.get("asal_data") or "artikel.jsonl", sintetis="ya", idsumber=a["id"], catatan=f"tahun {str(a.get('tanggal'))[:4]}; {cat}"))
    # 5. negatif
    for judul, isi in BERITA:
        item.append(dict(kategori="berita", jenis="berita", isi=(judul, isi), label="tidak_ditemukan", boleh="tidak_ditemukan", sumber="buatan_sendiri", sintetis="ya", idsumber="", catatan="berita fiktif gaya portal"))
    for j, t in enumerate(EDUKASI):
        item.append(dict(kategori="edukasi", jenis="sosial" if j % 2 == 0 else "berita", isi=t, label="tidak_ditemukan", boleh="tidak_ditemukan", sumber="buatan_sendiri", sintetis="ya", idsumber="", catatan="edukasi literasi digital"))
    for j, t in enumerate(PENGUMUMAN):
        item.append(dict(kategori="pengumuman", jenis=("sosial", "berita", "chat")[j % 3], isi=t, label="tidak_ditemukan", boleh="tidak_ditemukan", sumber="buatan_sendiri", sintetis="ya", idsumber="", catatan="pengumuman resmi"))
    for m in OBROLAN:
        item.append(dict(kategori="obrolan", jenis="obrolan", isi=m, label="tidak_ditemukan", boleh="tidak_ditemukan", sumber="buatan_sendiri", sintetis="ya", idsumber="", catatan="obrolan sehari-hari"))
    for j, t in enumerate(PROMOSI):
        item.append(dict(kategori="promosi_sah", jenis="sosial" if j % 2 == 0 else "berita", isi=t, label="tidak_ditemukan", boleh="tidak_ditemukan", sumber="buatan_sendiri", sintetis="ya", idsumber="", catatan="promosi sah"))
    # 6. teks sangat pendek
    for t in ["Rapat RT malam ini", "Jangan lupa makan siang", "Diskon besar akhir pekan ini", "Kumpul di lapangan jam delapan", "Pengajian rutin malam Jumat besok"]:
        n = sum(c.isalnum() for c in t)
        lab, boleh = ("teks_tidak_terbaca", "teks_tidak_terbaca") if n < 25 else ("tidak_ditemukan", "tidak_ditemukan;teks_tidak_terbaca")
        item.append(dict(kategori="obrolan", jenis="polos", isi=t, label=lab, boleh=boleh, sumber="buatan_sendiri", sintetis="ya", idsumber="",
                         catatan=f"teks pendek {n} karakter huruf-angka; aturan label: kurang dari 25 = tidak terbaca", pendek=True))
    item.append(dict(kategori="obrolan", jenis="tanpa_teks", isi=None, label="teks_tidak_terbaca", boleh="teks_tidak_terbaca", sumber="buatan_sendiri", sintetis="ya",
                     idsumber="", catatan="pola gradasi tanpa tulisan, 0 karakter", pendek=True))

    # id dan pembagian set berstrata (kategori, sintetis; teks pendek terpisah)
    for i, it in enumerate(item, start=1):
        it["id"] = f"ev{i:03d}"
    grup = defaultdict(list)
    for it in item:
        grup[(it["kategori"], it["sintetis"], it["label"] if it.get("pendek") else "")].append(it)
    rng_s = random.Random(SEED + 1)
    for kunci in sorted(grup):
        g = sorted(grup[kunci], key=lambda x: x["id"])
        rng_s.shuffle(g)
        n_uji = int(len(g) * 0.4 + 0.5)
        if len(g) >= 2:
            n_uji = max(1, n_uji)
        for k, it in enumerate(g):
            it["set"] = "uji" if k < n_uji else "dev"

    # tulis
    if KELUAR.exists() and paksa:
        shutil.rmtree(KELUAR / "gambar", ignore_errors=True)
    (KELUAR / "gambar").mkdir(parents=True, exist_ok=True)
    rng_r = random.Random(SEED + 2)
    baris_csv: list[dict] = []
    for it in item:
        jenis = it["jenis"]
        if jenis == "salin":
            ekst = it["isi"].suffix.lower()
            nama = f"{it['id']}{ekst}"
            shutil.copyfile(it["isi"], KELUAR / "gambar" / nama)
        else:
            nama = f"{it['id']}.jpg"
            r = random.Random(rng_r.random())
            if jenis == "chat":
                im = render_chat([("in", it["isi"])], r, diteruskan=r.random() < 0.5)
            elif jenis == "obrolan":
                im = render_chat(it["isi"], r)
            elif jenis == "sosial":
                im = render_sosial(it["isi"], r)
            elif jenis == "polos":
                im = render_polos(it["isi"], r)
            elif jenis == "tanpa_teks":
                im = render_tanpa_teks(r)
            else:  # berita
                if isinstance(it["isi"], tuple):
                    judul, isi = it["isi"]
                else:
                    ks = kalimat_dari(it["isi"])
                    judul, isi = (ks[0], " ".join(ks[1:]) or ks[0]) if len(ks) > 1 else (ks[0], ks[0])
                im = render_berita(judul, isi, r)
            simpan_jpeg(im, KELUAR / "gambar" / nama, r)
        baris_csv.append(dict(id=it["id"], berkas=nama, set=it["set"], label_harapan=it["label"], label_boleh=it["boleh"], kategori=it["kategori"],
                              sumber=it["sumber"], sintetis=it["sintetis"], id_artikel_sumber=it["idsumber"], catatan=it["catatan"]))
    baris_csv.sort(key=lambda b: b["id"])
    with open(KELUAR / "metadata.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM, lineterminator="\n")
        w.writeheader()
        w.writerows(baris_csv)
    # segel set uji
    uji = [b for b in baris_csv if b["set"] == "uji"]
    teks_uji = ""
    for b in uji:
        s = io.StringIO()
        csv.DictWriter(s, fieldnames=KOLOM, lineterminator="\n").writerow(b)
        teks_uji += s.getvalue()
    baris_sha = [f"{hashlib.sha256((KELUAR / 'gambar' / b['berkas']).read_bytes()).hexdigest()}  gambar/{b['berkas']}" for b in uji]
    baris_sha.append(f"{hashlib.sha256(teks_uji.encode('utf-8')).hexdigest()}  metadata.csv#baris_uji")
    (KELUAR / "uji_beku.sha256").write_text("\n".join(baris_sha) + "\n", encoding="utf-8")
    ringkas = defaultdict(int)
    for b in baris_csv:
        ringkas[(b["kategori"], b["set"])] += 1
    print(f"gambar: {len(baris_csv)}, uji: {len(uji)}, dev: {len(baris_csv) - len(uji)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--paksa", action="store_true", help="bangun ulang walau uji_beku.sha256 sudah ada")
    return bangun(ap.parse_args().paksa)


if __name__ == "__main__":
    sys.exit(main())
