FROM python:3.12-slim

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

CMD ["arq", "app.core.worker.WorkerSettings"]
