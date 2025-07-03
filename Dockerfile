# === BASE IMAGE ===
FROM python:3.11-slim AS base

# Set workdir
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install pip deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . ./
# COPY .env* ./
# RUN mkdir -p scripts
COPY run_*.sh ./

# Default env vars
ENV APP_MODULE=app.main:app
ENV HOST=0.0.0.0
ENV PORT=8000

# === DEVELOPMENT IMAGE ===
FROM base AS development

CMD ["bash", "./run_dev.sh"]

# === PRODUCTION IMAGE ===
FROM base AS production

CMD ["bash", "./run_prod.sh"]
