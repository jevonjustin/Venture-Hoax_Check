"""Menjalankan server: python -m app"""

import uvicorn

from .main import PORT

if __name__ == "__main__":
    # 0.0.0.0: mendengarkan di semua antarmuka jaringan, supaya HP di jaringan yang sama bisa masuk.
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)
