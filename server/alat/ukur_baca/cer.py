"""Metrik pembacaan teks terhadap transkripsi acuan.

Penanda di transkripsi acuan:
- "[UI] " di awal baris: teks antarmuka media sosial.
- "[?]": bagian tidak terbaca atau tertutup; wildcard.
- "[?ragu: x]" tidak boleh ada di transkripsi akhir; baca_acuan melempar TranskripsiBelumFinal.

Hasil kandidat dijajarkan dengan seluruh transkripsi (isi + baris [UI]) memakai jarak edit
karakter. Aturan biaya per karakter acuan:

| jenis karakter acuan | cocok | salah / diganti | hilang |
|---|---|---|---|
| isi | 0 | 1 | 1 |
| UI (dan spasi antarbaris) | 0 | 0 | 0 |
| wildcard "[?]" | menyerap nol, satu, atau banyak karakter hasil tanpa biaya | | |

Karakter hasil yang tidak terjajar dengan apa pun (sisipan) bernilai 1 dan dicatat sebagai
karakter karangan.

- cer_isi    = biaya / jumlah karakter isi bukan-wildcard. Metrik utama.
- cer_penuh  = sama, tetapi karakter [UI] diperlakukan seperti isi (pembanding).
- ui_terbaca = proporsi karakter baris [UI] yang muncul di hasil (kecocokan potongan terdekat).
- karakter_karangan = jumlah sisipan pada penjajaran cer_isi.

Normalisasi (acuan dan hasil): NFKC, huruf kecil, spasi dan baris baru dilipat jadi satu spasi.
Menjalankan berkas ini langsung (python cer.py) mengeksekusi uji kecil di bagian bawah.
"""

import re
import unicodedata
from dataclasses import dataclass

_AWALAN_UI = "[UI] "
_W = ""  # pengganti "[?]" selama penjajaran
_SKALA = 1 << 20  # biaya dan jumlah sisipan dikodekan dalam satu bilangan bulat: biaya * _SKALA + sisipan

JENIS_ISI, JENIS_UI, JENIS_WILDCARD = "i", "u", "w"


class TranskripsiBelumFinal(ValueError):
    """Transkripsi acuan masih memuat penanda [?ragu: ...]."""


def normalisasi(teks: str) -> str:
    teks = unicodedata.normalize("NFKC", teks).lower()
    return re.sub(r"\s+", " ", teks).strip()


@dataclass(frozen=True)
class Acuan:
    karakter: tuple  # pasangan (karakter, jenis)
    baris_ui: tuple  # teks tiap baris UI, tanpa wildcard dipisah menjadi potongan

    @property
    def jumlah_isi(self) -> int:
        return sum(1 for _, j in self.karakter if j == JENIS_ISI)

    @property
    def jumlah_ui(self) -> int:
        return sum(len(p) for p in self.baris_ui)


def baca_acuan(teks: str, nama: str = "transkripsi") -> Acuan:
    """Membangun acuan dari teks transkripsi. Melempar TranskripsiBelumFinal jika ada [?ragu."""
    if "[?ragu" in teks:
        nomor = [str(i) for i, b in enumerate(teks.splitlines(), 1) if "[?ragu" in b]
        raise TranskripsiBelumFinal(
            f"{nama} masih memuat [?ragu: ...] di baris {', '.join(nomor)}. "
            "Selesaikan dulu: tulis teksnya kalau terbaca jelas, atau ganti dengan [?]."
        )
    karakter, baris_ui = [], []
    for baris in teks.splitlines():
        ui = baris.startswith(_AWALAN_UI)
        isi = baris[len(_AWALAN_UI):] if ui else baris
        isi = normalisasi(isi.replace("[?]", _W))
        isi = re.sub(r"\s*" + _W + r"\s*", _W, isi)  # spasi di sekitar wildcard ikut diserap
        if not isi:
            continue
        if karakter:
            karakter.append((" ", JENIS_UI))  # pemisah antarbaris tidak dihitung
        for c in isi:
            karakter.append((c, JENIS_WILDCARD if c == _W else (JENIS_UI if ui else JENIS_ISI)))
        if ui:
            baris_ui.append(tuple(p for p in isi.split(_W) if p.strip()))
    return Acuan(tuple(karakter), tuple(p for baris in baris_ui for p in baris))


def _penjajaran(karakter, hipotesis: str) -> tuple[int, int]:
    """Mengembalikan (biaya, sisipan) dari penjajaran dengan biaya terendah (seri: sisipan paling sedikit)."""
    n = len(hipotesis)
    sebelumnya = [j * (_SKALA + 1) for j in range(n + 1)]  # semua karakter hasil = sisipan
    for c, jenis in karakter:
        if jenis == JENIS_WILDCARD:
            sekarang = [sebelumnya[0]]
            for j in range(1, n + 1):
                sekarang.append(min(sebelumnya[j], sekarang[j - 1]))
        else:
            hilang = _SKALA if jenis == JENIS_ISI else 0
            sekarang = [sebelumnya[0] + hilang]
            for j in range(1, n + 1):
                salah = _SKALA if (jenis == JENIS_ISI and c != hipotesis[j - 1]) else 0
                sekarang.append(min(sebelumnya[j] + hilang, sekarang[j - 1] + _SKALA + 1, sebelumnya[j - 1] + salah))
        sebelumnya = sekarang
    total = sebelumnya[-1]
    return total // _SKALA, total % _SKALA


def _jarak_potongan_terdekat(pola: str, teks: str) -> int:
    """Jarak edit terkecil antara pola dan sembarang potongan teks (algoritma Sellers)."""
    sebelumnya = [0] * (len(teks) + 1)
    for i, a in enumerate(pola, 1):
        sekarang = [i]
        for j, b in enumerate(teks, 1):
            sekarang.append(min(sebelumnya[j] + 1, sekarang[j - 1] + 1, sebelumnya[j - 1] + (a != b)))
        sebelumnya = sekarang
    return min(sebelumnya)


def ui_terbaca(acuan: Acuan, hasil: str) -> float | None:
    if acuan.jumlah_ui == 0:
        return None
    h = normalisasi(hasil)
    muncul = sum(max(0, len(p) - _jarak_potongan_terdekat(p, h)) for p in acuan.baris_ui)
    return muncul / acuan.jumlah_ui


@dataclass(frozen=True)
class Metrik:
    cer_isi: float | None
    cer_penuh: float | None
    ui_terbaca: float | None
    karakter_karangan: int
    karakter_hasil: int


def hitung(acuan: Acuan, hasil: str) -> Metrik:
    h = normalisasi(hasil)
    biaya_isi, sisipan = _penjajaran(acuan.karakter, h)
    cer_isi = biaya_isi / acuan.jumlah_isi if acuan.jumlah_isi else None

    semua_isi = tuple((c, JENIS_ISI if j == JENIS_UI else j) for c, j in acuan.karakter)
    pembagi_penuh = sum(1 for _, j in semua_isi if j == JENIS_ISI)
    cer_penuh = _penjajaran(semua_isi, h)[0] / pembagi_penuh if pembagi_penuh else None

    return Metrik(cer_isi, cer_penuh, ui_terbaca(acuan, hasil), sisipan, len(h))


# ---------------------------------------------------------------------------
# Uji kecil: python cer.py
# ---------------------------------------------------------------------------

def _uji() -> None:
    teks = "[UI] 12.30\nHalo dunia ini isi\n[UI] Ketuk untuk info\nBaris [?] kedua\n"
    a = baca_acuan(teks)

    dengan_ui = "12.30 Halo dunia ini isi Ketuk untuk info Baris x kedua"
    tanpa_ui = "Halo dunia ini isi Baris x kedua"
    m1, m2 = hitung(a, dengan_ui), hitung(a, tanpa_ui)
    assert m1.cer_isi == m2.cer_isi == 0.0, (m1, m2)
    assert m1.karakter_karangan == m2.karakter_karangan == 0
    assert m1.ui_terbaca == 1.0 and m2.ui_terbaca < 0.3, (m1.ui_terbaca, m2.ui_terbaca)

    # Isi yang sama dengan satu salah baca: cer_isi sama dengan atau tanpa UI.
    dengan_ui2 = "12.30 Halo dunia ini isl Ketuk untuk info Baris x kedua"
    tanpa_ui2 = "Halo dunia ini isl Baris x kedua"
    s1, s2 = hitung(a, dengan_ui2), hitung(a, tanpa_ui2)
    assert s1.cer_isi == s2.cer_isi and s1.cer_isi > 0, (s1, s2)

    # UI yang salah dibaca tidak dihitung sebagai kesalahan isi.
    assert hitung(a, "12.3o Halo dunia ini isi Ketuk unluk info Baris x kedua").cer_isi == 0.0

    # Wildcard menyerap karakter hasil berapa pun jumlahnya.
    assert hitung(a, "Halo dunia ini isi Baris apa saja yang ada kedua").cer_isi == 0.0

    # Sisipan di luar isi, UI, dan wildcard dihitung salah dan dicatat sebagai karangan.
    polos = baca_acuan("Halo dunia ini isi\nBaris kedua\n")
    k = hitung(polos, "Halo dunia ini isi Baris kedua tambahan karangan")
    assert k.karakter_karangan == len(" tambahan karangan") and k.cer_isi > 0, k
    assert hitung(polos, "Halo dunia ini isi Baris kedua").karakter_karangan == 0

    # Gambar tanpa teks: tidak ada CER, semua hasil adalah karangan.
    kosong = hitung(baca_acuan(""), "ada teks palsu")
    assert kosong.cer_isi is None and kosong.karakter_karangan == len("ada teks palsu")

    # [?ragu menghentikan program dengan galat jelas.
    try:
        baca_acuan("a [?ragu: b]", "x.txt")
    except TranskripsiBelumFinal as e:
        assert "x.txt" in str(e) and "baris 1" in str(e)
    else:
        raise AssertionError("seharusnya melempar TranskripsiBelumFinal")

    print("Uji cer.py lulus.")


if __name__ == "__main__":
    _uji()


