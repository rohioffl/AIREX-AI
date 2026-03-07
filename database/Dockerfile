FROM python:3.12-slim

RUN groupadd -r airex && useradd -r -g airex airex

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir alembic sqlalchemy asyncpg psycopg2-binary

COPY backend/ /app
COPY database/ /database

ENV PYTHONPATH=/app

WORKDIR /database

USER airex

CMD ["alembic", "upgrade", "head"]
