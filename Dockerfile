# PIVOT Trading System - Docker Image
# Fase 6: Dockerización completa

FROM python:3.11-slim

# Metadata
LABEL maintainer="PIVOT Team"
LABEL version="2.0"
LABEL description="Sistema de Trading y Backtesting PIVOT"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.0

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libffi-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar código fuente
COPY kernel/ ./kernel/
COPY core/ ./core/
COPY estrategias/ ./estrategias/
COPY activos/ ./activos/
COPY data/ ./data/
COPY docs/ ./docs/
COPY tests/ ./tests/
COPY cli.py .
COPY test_pivot_backtest.py .
COPY pytest.ini . 2>/dev/null || true

# Crear directorios para datos persistentes
RUN mkdir -p /app/data/storage /app/logs

# Exponer puertos
# 8000: API FastAPI
# 8765: WebSocket Server
EXPOSE 8000 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health', timeout=5)" || exit 1

# Usuario no-root para seguridad (opcional, comentar si hay problemas de permisos)
# RUN useradd -m pivot && chown -R pivot:pivot /app
# USER pivot

# Comando por defecto: iniciar API
CMD ["python", "-m", "uvicorn", "kernel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
