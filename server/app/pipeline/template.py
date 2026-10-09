"""Tahap 7: menyusun nama dan penjelasan dari template.

Semua teks di sini ditulis sendiri (bukan buatan LLM), tampil di aplikasi, dan mengikuti aturan produk:
Bahasa Indonesia semi-formal, tanpa kata ganti orang kedua, tanpa angka persen, dan tanpa vonis. Sistem hanya
mengatribusikan kesimpulan ke artikel cek fakta; ia tidak pernah menyatakan informasi di layar benar atau salah.
tests/test_template.py memindai semua teks di modul ini.
"""

from ..skema import Ciri, Tingkat
from .tipe import CiriTerdeteksi

# Nama yang tampil di aplikasi. Id-nya bagian dari kontrak API (skema.ID_CIRI_TERKUNCI).
NAMA = {
    "ajakan_menyebarkan": "Ajakan menyebarkan",
    "desakan_waktu": "Desakan waktu",
    "kapital_tanda_seru": "Huruf kapital dan tanda seru berlebihan",
    "link_mencurigakan": "Tautan mencurigakan",
    "sumber_tidak_jelas": "Sumber tidak jelas",
    "judul_clickbait": "Judul memancing klik",
    "bahasa_provokatif": "Bahasa yang memancing emosi",
    "pernah_dibantah": "Pernah dibantah media cek fakta",
}

PENJELASAN = {
    "ajakan_menyebarkan": (
        "Pesan yang mendesak untuk segera disebarkan sering dibuat agar orang ikut meneruskannya "
        "sebelum sempat memeriksa isinya. Informasi dari sumber yang jelas biasanya tidak bergantung "
        "pada rantai penerusan pesan."
    ),
    "desakan_waktu": (
        "Kalimat seperti \"sebelum dihapus\" atau \"hari ini terakhir\" membuat pembaca terburu-buru. "
        "Informasi resmi biasanya tetap bisa dicek kapan saja, jadi desakan seperti ini patut diwaspadai."
    ),
    "kapital_tanda_seru": (
        "Huruf kapital dan tanda seru yang berlebihan sering dipakai untuk memancing emosi, "
        "bukan untuk menyampaikan data. Gaya penulisan seperti ini perlu disikapi dengan hati-hati."
    ),
    "link_mencurigakan": (
        "Alamat tautan seperti ini belum tentu menunjukkan tujuan akhirnya. Pemendek tautan, misalnya, "
        "menyembunyikan alamat asli sehingga tujuannya tidak terlihat sebelum dibuka. Pemendek juga dipakai "
        "instansi resmi, jadi hal ini bukan tanda bahaya dengan sendirinya. Yang perlu dipastikan adalah "
        "siapa yang membagikan tautan itu dan ke mana tautan tersebut mengarah."
    ),
    "sumber_tidak_jelas": (
        "Tidak tampak nama lembaga, tanggal, atau tautan yang bisa dicek, atau sumbernya hanya disebut samar "
        "seperti \"katanya\" atau \"info dari grup\". Informasi yang bisa dipertanggungjawabkan biasanya "
        "menyebut sumbernya dengan jelas."
    ),
    "judul_clickbait": (
        "Judul atau kalimat pembuka yang dibuat untuk memancing rasa penasaran tanpa menyebut inti informasinya "
        "sering dipakai agar pesan dibuka dan disebarkan. Isi lengkapnya perlu dibaca dan dicek ke sumber lain."
    ),
    "bahasa_provokatif": (
        "Bahasa yang memancing amarah, rasa takut, atau kebencian dapat membuat pembaca bereaksi sebelum sempat "
        "berpikir. Pesan seperti ini patut dibaca dengan tenang dan dicek ke sumber lain."
    ),
    "pernah_dibantah": (
        "Klaim yang mirip sudah pernah diperiksa dan dinyatakan salah oleh media cek fakta."
    ),
}

# Penjelasan artikel cek fakta menurut label. {sumber} dan {judul_klausa} diisi aman oleh `penjelasan_label`.
# Kesimpulan selalu diatribusikan ke artikel; label benar dan klarifikasi tidak menyiratkan isi layar benar.
LABEL = {
    "salah": (
        "Artikel cek fakta dari {sumber}{judul_klausa} menyatakan bahwa klaim yang mirip dengan ini salah. "
        "Isi layar perlu dibandingkan dengan artikel tersebut."
    ),
    "penipuan": (
        "Artikel dari {sumber}{judul_klausa} menggolongkan klaim yang mirip dengan ini sebagai penipuan. "
        "Data pribadi, kode verifikasi, dan uang sebaiknya tidak dikirim sebelum asal pesan dipastikan."
    ),
    "klarifikasi": (
        "Artikel dari {sumber}{judul_klausa} memuat klarifikasi tentang klaim yang mirip. "
        "Artikel itu membahas klaim serupa dan belum tentu sama dengan isi layar, "
        "jadi isi layar tetap perlu dicocokkan dengan artikelnya."
    ),
    "benar": (
        "Artikel dari {sumber}{judul_klausa} membahas klaim yang mirip dan memberinya label benar. "
        "Label itu hanya berlaku bagi klaim di dalam artikel, bukan untuk isi layar, "
        "sehingga tetap perlu dicek terhadap artikelnya."
    ),
    "lainnya": (
        "Artikel dari {sumber}{judul_klausa} membahas klaim yang mirip. "
        "Kesimpulan artikel perlu dibaca langsung untuk mengetahui hasil pemeriksaannya."
    ),
    "belum_terbukti": (
        "Artikel dari {sumber}{judul_klausa} menyebut klaim yang mirip belum terbukti. "
        "Status itu tidak menunjukkan klaimnya salah maupun benar; rincian pemeriksaannya ada di artikel."
    ),
    "satir": (
        "Konten yang mirip pernah diidentifikasi oleh {sumber}{judul_klausa} sebagai satir atau parodi, "
        "yaitu tulisan yang sengaja dibuat berlebihan atau bercanda dan tidak dimaksudkan sebagai berita."
    ),
}

# Dipakai untuk label yang tidak dikenal.
LABEL_CADANGAN = (
    "Artikel dari {sumber}{judul_klausa} membahas klaim yang mirip. "
    "Kesimpulan artikel perlu dibaca langsung."
)

SUMBER_CADANGAN = "sebuah media cek fakta"

# (judul, keterangan) per tingkat. Tidak ada angka persen, dan tidak ada vonis.
TINGKAT = {
    Tingkat.KUAT: (
        "Indikasi Kuat Hoaks",
        "Klaim pada gambar mirip dengan klaim yang dinyatakan salah oleh artikel cek fakta. "
        "Ini indikasi, bukan putusan akhir; artikel rujukan sebaiknya dibaca langsung.",
    ),
    Tingkat.HATI_HATI: (
        "Perlu Hati-hati",
        "Belum ada artikel cek fakta yang cocok, tetapi ditemukan beberapa ciri yang sering muncul pada "
        "informasi menyesatkan. Informasi sebaiknya dicek ke sumber resmi sebelum dipercaya atau disebarkan.",
    ),
    Tingkat.TIDAK_DITEMUKAN: (
        "Tidak Ditemukan Indikasi Hoaks",
        "Tidak ada artikel cek fakta yang cocok dan tidak ditemukan ciri yang menonjol. "
        "Ini bukan jaminan bahwa informasinya benar; sumbernya tetap perlu dicek.",
    ),
}


def semua_teks() -> list[str]:
    """Seluruh teks template (untuk dipindai tes kata terlarang)."""
    teks = list(NAMA.values()) + list(PENJELASAN.values()) + list(LABEL.values()) + [LABEL_CADANGAN, SUMBER_CADANGAN]
    for judul, keterangan in TINGKAT.values():
        teks += [judul, keterangan]
    return teks


def penjelasan_label(label: str | None, sumber: str | None = None, judul: str | None = None) -> str:
    """Penjelasan untuk satu artikel cek fakta. Sumber atau judul yang kosong ditangani dengan aman."""
    sumber = (sumber or "").strip() or SUMBER_CADANGAN
    judul = (judul or "").strip()
    judul_klausa = f" berjudul \"{judul}\"" if judul else ""
    kerangka = LABEL.get((label or "").strip().lower(), LABEL_CADANGAN)
    return kerangka.format(sumber=sumber, judul_klausa=judul_klausa)


def judul_tingkat(tingkat: Tingkat) -> str:
    return TINGKAT[tingkat][0]


def keterangan_tingkat(tingkat: Tingkat) -> str:
    return TINGKAT[tingkat][1]


def susun_penjelasan(ciri: list[CiriTerdeteksi]) -> list[Ciri]:
    """Masukan: ciri terdeteksi. Keluaran: ciri lengkap dengan nama dan penjelasan, urutan tetap."""
    return [
        Ciri(id=c.id, nama=NAMA[c.id], bukti=c.bukti, penjelasan=PENJELASAN[c.id], keyakinan=c.keyakinan)
        for c in ciri
    ]
