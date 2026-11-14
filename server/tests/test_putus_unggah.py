"""Klien terputus saat mengunggah body /analisis (Sesi 8.2, temuan uji HP lewat data seluler) dan jam di log server.

Unggahan diputus dengan memanggil aplikasi ASGI langsung: `receive` mengirim sebagian body lalu `http.disconnect`.
"""

import asyncio
import logging

import httpx

from app import __main__ as utama
from app import beban, main
from app.konfigurasi import pengaturan

BATAS = "batas-uji"
AWAL_BODY = (
    f"--{BATAS}\r\nContent-Disposition: form-data; name=\"gambar\"; filename=\"p.jpg\"\r\n"
    "Content-Type: image/jpeg\r\n\r\n"
).encode() + b"\xff\xd8" + b"x" * 1000


def _scope() -> dict:
    return {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": "/analisis", "raw_path": b"/analisis", "query_string": b"", "root_path": "",
        "headers": [
            (b"host", b"uji"),
            (b"content-type", f"multipart/form-data; boundary={BATAS}".encode()),
            (b"content-length", b"200000"),
        ],
        "client": ("10.0.0.9", 5000), "server": ("uji", 80),
    }


async def _unggah_terputus() -> list[dict]:
    pesan = [
        {"type": "http.request", "body": AWAL_BODY, "more_body": True},
        {"type": "http.disconnect"},
    ]
    terkirim: list[dict] = []

    async def receive():
        if pesan:
            return pesan.pop(0)
        await asyncio.sleep(3600)

    async def send(m):
        terkirim.append(m)

    await main.app(_scope(), receive, send)
    return terkirim


def test_putus_saat_unggah_dicatat_satu_baris_tanpa_traceback_dan_slot_tetap_bebas(monkeypatch, caplog):
    pembatas = beban.PembatasBeban(1, 0.0)
    monkeypatch.setattr(beban, "pembatas", pembatas)
    monkeypatch.setattr(pengaturan, "jeda_min_detik", 0.0)
    monkeypatch.setattr(pengaturan, "jeda_maks_detik", 0.0)

    async def jalan():
        with caplog.at_level(logging.INFO, logger="uvicorn.error"):
            terkirim = await _unggah_terputus()
        status = [m["status"] for m in terkirim if m["type"] == "http.response.start"]
        assert status == [499]
        assert pembatas.berjalan == 0 and pembatas.menunggu == 0
        # Dengan satu slot dan antrean 0 detik, permintaan berikutnya hanya lolos bila slot benar-benar bebas.
        transport = httpx.ASGITransport(app=main.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://uji") as klien:
            from test_beban import GAMBAR

            r = await klien.post("/analisis", files={"gambar": ("p.jpg", GAMBAR, "image/jpeg")})
        assert r.status_code == 200

    asyncio.run(jalan())
    teks = caplog.text
    baris = [r for r in caplog.records if "terputus saat mengunggah" in r.getMessage()]
    assert len(baris) == 1
    assert f"{len(AWAL_BODY)} byte diterima" in baris[0].getMessage()
    assert baris[0].exc_info is None
    assert "Galat tak terduga" not in teks and "Traceback" not in teks


def test_log_server_diawali_jam():
    cfg = utama.konfigurasi_log()
    for nama in ("default", "access"):
        assert cfg["formatters"][nama]["fmt"].startswith("%(asctime)s ")
        assert cfg["formatters"][nama]["datefmt"] == "%H:%M:%S"
    rekaman = logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, "Permintaan x selesai", None, None)
    rekaman.created = 1763100000.0  # jam lokal apa pun, yang diperiksa hanya bentuknya
    formatter = logging.Formatter(cfg["formatters"]["default"]["fmt"].replace("%(levelprefix)s", "INFO:"),
                                  cfg["formatters"]["default"]["datefmt"])
    import re

    assert re.match(r"^\d{2}:\d{2}:\d{2} INFO: Permintaan x selesai$", formatter.format(rekaman))
