#!/bin/bash

# Jalankan dari root proyek
ENV_DIR="venv"
APP_MODULE="main:app"

# Cek apakah virtual environment tersedia
if [ ! -d "$ENV_DIR" ]; then
  echo "Virtual environment '$ENV_DIR' tidak ditemukan."
  echo "Jalankan: python3 -m venv $ENV_DIR"
  exit 1
fi

# Aktifkan venv
source "$ENV_DIR/bin/activate"

# (Opsional) load .env file
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Jalankan server dengan reload (khusus development)
echo "Menjalankan FastAPI (development mode)..."
uvicorn "$APP_MODULE" --reload
