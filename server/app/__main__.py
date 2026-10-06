"""Menjalankan server: python -m app"""

import sys

from . import konfigurasi


def main() -> int:
    if konfigurasi.kesalahan:
        print(f"Server tidak dijalankan. Pengaturan tidak sah:\n  {konfigurasi.kesalahan}", file=sys.stderr)
        return 1
    pengaturan = konfigurasi.pengaturan

    import uvicorn

    uvicorn.run("app.main:app", host=pengaturan.host, port=pengaturan.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
