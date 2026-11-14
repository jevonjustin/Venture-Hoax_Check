"""Menjalankan server: python -m app"""

import sys

from . import konfigurasi


FORMAT_JAM = "%H:%M:%S"


def konfigurasi_log() -> dict:
    """Konfigurasi log uvicorn bawaan dengan jam (HH:MM:SS) di awal setiap baris, supaya kejadian di HP bisa
    dicocokkan dengan log server. Isi baris tidak berubah (tetap tanpa teks hasil bacaan)."""
    import copy

    from uvicorn.config import LOGGING_CONFIG

    cfg = copy.deepcopy(LOGGING_CONFIG)
    for nama in ("default", "access"):
        cfg["formatters"][nama]["fmt"] = "%(asctime)s " + cfg["formatters"][nama]["fmt"]
        cfg["formatters"][nama]["datefmt"] = FORMAT_JAM
    return cfg


def main() -> int:
    if konfigurasi.kesalahan:
        print(f"Server tidak dijalankan. Pengaturan tidak sah:\n  {konfigurasi.kesalahan}", file=sys.stderr)
        return 1
    pengaturan = konfigurasi.pengaturan

    import uvicorn

    uvicorn.run("app.main:app", host=pengaturan.host, port=pengaturan.port, log_config=konfigurasi_log())
    return 0


if __name__ == "__main__":
    sys.exit(main())
