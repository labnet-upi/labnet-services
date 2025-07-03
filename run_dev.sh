#!/bin/bash
set -e

# Load .env jika ada
if [ -f ".env.development" ]; then
  export $(grep -v '^#' .env.development | xargs)
fi

echo "🚀 Menjalankan FastAPI (development mode)..."
uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" --reload --reload-dir app
