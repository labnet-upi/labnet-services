#!/bin/bash
set -e

if [ -f ".env.production" ]; then
  export $(grep -v '^#' .env.production | xargs)
fi

echo "🚀 Menjalankan FastAPI (production mode)..."
gunicorn -k uvicorn.workers.UvicornWorker "$APP_MODULE" --bind "$HOST:$PORT"
