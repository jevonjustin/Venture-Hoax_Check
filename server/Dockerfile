# Server Veritas untuk Hugging Face Docker Spaces (Sesi 8.1). Juga bisa dibangun lokal dari folder server.
# Data pencarian tidak ada di image: diunduh saat menyala dari dataset CEKHOAKS_HF_DATASET (app/data_hf.py),
# atau di-mount lalu ditunjuk lewat CEKHOAKS_CEKFAKTA_FOLDER dan CEKHOAKS_MODEL_FOLDER.
# Python sama dengan .venv server (3.12.4).
FROM python:3.12.4-slim

# opencv-python (dependensi RapidOCR) membutuhkan libGL dan glib.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Spaces menjalankan container dengan uid 1000 (dokumentasi Docker Spaces).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    CEKHOAKS_HOST=0.0.0.0 \
    CEKHOAKS_PORT=7860 \
    CEKHOAKS_HF_FOLDER=/home/user/data_hf
WORKDIR $HOME/app

COPY --chown=user requirements.txt requirements-space.txt ./
RUN pip install --user -r requirements-space.txt

# RapidOCR mengunduh model OCR ke folder paketnya saat pertama dibuat. Dilakukan sekali saat build supaya
# container tidak mengunduhnya setiap kali menyala.
RUN python -c "from rapidocr import RapidOCR; RapidOCR(params={'Global.log_level': 'warning'})"

COPY --chown=user app ./app

EXPOSE 7860
# Satu proses, satu worker uvicorn (python -m app). Host dan port dari CEKHOAKS_HOST dan CEKHOAKS_PORT.
CMD ["python", "-m", "app"]
