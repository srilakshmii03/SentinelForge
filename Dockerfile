# Frontend build
FROM node:22-alpine AS frontend-build
WORKDIR /ui

COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

COPY frontend ./
RUN npm run build


# Backend/runtime
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY evaluation ./evaluation
COPY sample-data ./sample-data

COPY --from=frontend-build /ui/dist ./frontend/dist

COPY README.md AI_USAGE.md .env.example ./

RUN useradd -m -u 10001 appuser && \
    mkdir -p /app/data /app/workspaces && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]