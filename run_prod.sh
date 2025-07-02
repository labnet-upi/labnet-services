#!/bin/bash

ENV_DIR="venv"
APP_MODULE="main:app"
HOST="0.0.0.0"
PORT=8000

# Cek apakah virtual environment tersedia
if [ ! -d "$ENV_DIR" ]; then
  echo "Virtual environment '$ENV_DIR' tidak ditemukan."
  exit 1
fi

# Aktifkan venv
source "$ENV_DIR/bin/activate"

# Load .env jika ada
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Jalankan dengan Gunicorn dan Uvicorn worker
echo "Menjalankan FastAPI (production mode)..."
gunicorn -k uvicorn.workers.UvicornWorker "$APP_MODULE" --bind "$HOST:$PORT" --workers 4 --daemon