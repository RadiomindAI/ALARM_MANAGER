# 1. Build Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# 2. Build Backend
FROM python:3.11-slim
WORKDIR /app

# Installa dipendenze di sistema necessarie per pandas/parquet
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia i file del backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/

# Copia il frontend compilato dallo stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Cartelle Dati e Uploads persistenti (Render Disk)
RUN mkdir -p /app/backend/data /app/backend/uploads

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
