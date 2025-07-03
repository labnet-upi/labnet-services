#!/bin/bash
set -e

# Load environment variables from .env.production if it exists
if [ -f ".env.production" ]; then
  export $(grep -v '^#' .env.production | xargs)
fi

echo "🚀 Menjalankan FastAPI (production mode tanpa Gunicorn)..."
exec uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
