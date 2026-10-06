"""Server Cek Hoaks: lapisan HTTP.

Menerima potongan gambar dari aplikasi, menyerahkannya ke pipeline (app/pipeline), dan mengembalikan
hasilnya sesuai kontrak di docs/API.md. Pipeline masih dummy (Sesi 5.1): belum ada model maupun OCR.

Privasi: gambar hanya dibaca di memori. Body permintaan dibaca sendiri dan di-parse dengan
parser multipart tingkat rendah, karena UploadFile bawaan Starlette menyimpan unggahan di atas
1 MB ke file sementara di disk. Log hanya mencatat ukuran, dimensi, dan durasi.
"""

import logging
import socket
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.exceptions import HTTPException as StarletteHTTPException

from .galat import DibatalkanKlien, GalatApi, respons_galat as _respons_galat
from . import konfigurasi
from .konfigurasi import NILAI_PAKSA, pengaturan
from .pipeline import orkestrator
from .pipeline.tipe import Konteks
from .skema import HasilAnalisis, ResponsGalat, StatusServer

VERSI = "0.4.0"
# Ruang tambahan untuk header dan pembatas multipart di sekitar gambar.
RUANG_MULTIPART_BYTE = 64 * 1024

# Anak logger "uvicorn.error" supaya tercetak dengan format uvicorn tanpa konfigurasi tambahan.
log = logging.getLogger("uvicorn.error").getChild("cekhoaks")


# --- Alamat jaringan ---


def alamat_ipv4_lokal() -> list[str]:
    """Semua IPv4 laptop selain loopback dan link-local (169.254.x.x)."""
    alamat: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            alamat.add(info[4][0])
    except socket.gaierror:
        pass
    # Cadangan: IP yang dipakai untuk rute keluar. UDP connect tidak mengirim paket apa pun.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            alamat.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in alamat if not a.startswith(("127.", "169.254.", "0.")))


def _cetak_alamat() -> None:
    baris = ["", "=" * 60, f"Server Cek Hoaks {VERSI} (pipeline dummy)", "Alamat yang bisa diketik di aplikasi:"]
    ip = alamat_ipv4_lokal()
    if ip:
        baris += [f"  http://{a}:{pengaturan.port}" for a in ip]
    else:
        baris.append("  (tidak ada IPv4 jaringan yang ditemukan)")
    baris.append(f"  http://127.0.0.1:{pengaturan.port}   <- lewat USB, setelah: adb reverse tcp:{pengaturan.port} tcp:{pengaturan.port}")
    if pengaturan.paksa_tingkat:
        baris.append(f"PAKSA_TINGKAT = {pengaturan.paksa_tingkat}")
    else:
        baris.append("Tingkat hasil: bergiliran (PAKSA_TINGKAT tidak diisi)")
    baris.append("=" * 60)
    print("\n".join(baris), flush=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if konfigurasi.kesalahan:  # server dijalankan langsung lewat uvicorn, tanpa python -m app
        raise konfigurasi.kesalahan
    _cetak_alamat()
    yield


app = FastAPI(title="Cek Hoaks", version=VERSI, lifespan=lifespan)


# --- Penanganan galat: semua respons non-2xx memakai format {"galat": {...}} ---


@app.exception_handler(GalatApi)
async def _tangani_galat_api(_: Request, e: GalatApi) -> JSONResponse:
    return _respons_galat(e.status, e.kode, e.pesan)


@app.exception_handler(RequestValidationError)
async def _tangani_validasi(_: Request, e: RequestValidationError) -> JSONResponse:
    return _respons_galat(422, "permintaan_tidak_valid", str(e.errors()))


@app.exception_handler(StarletteHTTPException)
async def _tangani_http(_: Request, e: StarletteHTTPException) -> JSONResponse:
    if e.status_code == 404:
        return _respons_galat(404, "tidak_ditemukan", "Rute tidak ada")
    if e.status_code == 405:
        return _respons_galat(405, "metode_salah", "Metode HTTP tidak didukung untuk rute ini")
    return _respons_galat(e.status_code, "galat_http", str(e.detail))


@app.exception_handler(Exception)
async def _tangani_tak_terduga(_: Request, e: Exception) -> JSONResponse:
    log.exception("Galat tak terduga")
    return _respons_galat(500, "galat_server", type(e).__name__)


# --- Pembacaan gambar di memori ---


async def _baca_body_terbatas(request: Request) -> bytes:
    panjang = request.headers.get("content-length")
    batas_body = pengaturan.batas_gambar_byte + RUANG_MULTIPART_BYTE
    if panjang and panjang.isdigit() and int(panjang) > batas_body:
        raise GalatApi(413, "terlalu_besar", f"Body {panjang} byte melebihi batas")
    body = bytearray()
    async for potongan in request.stream():
        body += potongan
        if len(body) > batas_body:
            raise GalatApi(413, "terlalu_besar", "Body melebihi batas")
    return bytes(body)


def _ambil_field_gambar(content_type: str, body: bytes) -> bytes | None:
    """Mengambil isi field "gambar" dari body multipart. None jika field tidak ada."""
    jenis, opsi = parse_options_header(content_type)
    if jenis != b"multipart/form-data" or b"boundary" not in opsi:
        raise GalatApi(422, "permintaan_tidak_valid", "Harus multipart/form-data")

    bagian: list[tuple[bytes, bytearray]] = []
    header = {"nama": bytearray(), "nilai": bytearray()}
    disposisi = bytearray()

    def mulai_bagian():
        disposisi.clear()
        bagian.append((b"", bytearray()))

    def data_bagian(data, awal, akhir):
        bagian[-1][1].extend(data[awal:akhir])

    def nama_header(data, awal, akhir):
        header["nama"].extend(data[awal:akhir])

    def nilai_header(data, awal, akhir):
        header["nilai"].extend(data[awal:akhir])

    def akhir_header():
        if bytes(header["nama"]).lower() == b"content-disposition":
            disposisi.extend(header["nilai"])
        header["nama"].clear()
        header["nilai"].clear()

    def header_selesai():
        _, opsi_disposisi = parse_options_header(bytes(disposisi))
        bagian[-1] = (opsi_disposisi.get(b"name", b""), bagian[-1][1])

    parser = MultipartParser(
        opsi[b"boundary"],
        callbacks={
            "on_part_begin": mulai_bagian,
            "on_part_data": data_bagian,
            "on_header_field": nama_header,
            "on_header_value": nilai_header,
            "on_header_end": akhir_header,
            "on_headers_finished": header_selesai,
        },
    )
    try:
        parser.write(body)
        parser.finalize()
    except MultipartParseError as e:
        raise GalatApi(422, "permintaan_tidak_valid", f"Multipart rusak: {e}") from e

    for nama, isi in bagian:
        if nama == b"gambar":
            return bytes(isi)
    return None


def _nilai_paksa(query: str | None) -> str | None:
    """Query ?paksa= mengalahkan PAKSA_TINGKAT. Nilai env sudah divalidasi saat server mulai."""
    if query is None:
        return pengaturan.paksa_tingkat
    if query not in NILAI_PAKSA:
        raise GalatApi(422, "permintaan_tidak_valid", f"Nilai paksa tidak dikenal: {query}")
    return query


# --- Rute ---


@app.get("/health", response_model=StatusServer)
async def health() -> StatusServer:
    return StatusServer(status="ok", versi=VERSI)


_SKEMA_UNGGAHAN = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["gambar"],
                    "properties": {"gambar": {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}


@app.post(
    "/analisis",
    response_model=HasilAnalisis,
    responses={code: {"model": ResponsGalat} for code in (400, 413, 415, 422, 500)},
    openapi_extra=_SKEMA_UNGGAHAN,
)
async def analisis(request: Request, paksa: str | None = None):
    mulai = time.perf_counter()
    id_permintaan = uuid.uuid4().hex
    nilai_paksa = _nilai_paksa(paksa)

    try:
        body = await _baca_body_terbatas(request)
        data = _ambil_field_gambar(request.headers.get("content-type", ""), body)
        del body
        if data is None:
            raise GalatApi(422, "permintaan_tidak_valid", 'Field "gambar" tidak ada')
    except GalatApi as e:
        log.info("Permintaan %s ditolak: %s", id_permintaan, e.kode)
        raise

    ctx = Konteks(
        id_permintaan=id_permintaan,
        jeda_detik=(pengaturan.jeda_min_detik, pengaturan.jeda_maks_detik),
        klien_putus=request.is_disconnected,
        paksa=nilai_paksa,
        mulai=mulai,
    )
    try:
        return await orkestrator.jalankan(data, ctx)
    except DibatalkanKlien:
        return Response(status_code=499)
