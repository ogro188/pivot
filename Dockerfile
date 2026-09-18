# PIVOT Trading System - Docker Image
# Multi-stage build for production

# ---- Build stage ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Instalar dependencias del sistema mínimas para build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --user -r requirements.txt

# ---- Runtime stage ----
FROM python:3.11-slim

LABEL maintainer="PIVOT Team"
LABEL version="2.0"
LABEL description="Sistema de Trading y Backtesting PIVOT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Solo runtime deps (sqlite3 ya está en python:3.11-slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes instalados desde builder
COPY --from=builder /root/.local /root/.local

# Copiar código fuente
COPY kernel/ ./kernel/
COPY core/ ./core/
COPY estrategias/ ./estrategias/
COPY activos/ ./activos/
COPY data/ ./data/
COPY docs/ ./docs/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY cli.py .
COPY test_pivot_backtest.py .
COPY pytest.ini .

# Crear usuario no-root
RUN useradd -m -u 1000 pivot && \
    mkdir -p /app/data/storage /app/logs && \
    chown -R pivot:pivot /app

USER pivot

# Exponer puertos
EXPOSE 8000 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=5)" || exit 1

# Comando por defecto: iniciar API
CMD ["python", "-m", "uvicorn", "kernel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
