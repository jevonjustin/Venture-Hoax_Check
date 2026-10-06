"""Tahap 3: mengambil klaim utama dari teks. (Dummy; parameter ctx hanya dipakai dummy.)"""

from .. import contoh
from .tipe import Konteks


def ekstrak_klaim(teks_bersih: str, ctx: Konteks) -> str | None:
    """Masukan: teks bersih. Keluaran: ringkasan satu kalimat, atau None jika tidak ada klaim jelas."""
    return contoh.CONTOH[ctx.skenario].klaim_utama
