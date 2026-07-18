# Imagem de produção — RNF007 (Backend Python 3.12+).
FROM python:3.13-slim

WORKDIR /app

# psycopg[binary] já traz o driver compilado; build-essential não é necessário.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Migração roda a cada start — idempotente (alembic só aplica o que falta) e garante que o
# banco nunca fica desatualizado em relação à imagem que está rodando.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
