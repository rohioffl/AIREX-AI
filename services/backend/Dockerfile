FROM python:3.12-slim AS base

RUN groupadd -r airex && useradd -r -g airex airex

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN chown -R airex:airex /app

USER airex

FROM base AS api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker

CMD ["arq", "app.core.worker.WorkerSettings"]
