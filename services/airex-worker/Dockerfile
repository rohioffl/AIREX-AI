FROM python:3.12-slim

RUN groupadd -r airex && useradd -r -g airex airex

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install airex-core first (from local path)
COPY services/airex-core/ ./airex-core/
RUN pip install --no-cache-dir -e ./airex-core/

# Install worker-specific dependencies
COPY services/airex-worker/requirements.txt ./requirements.txt
RUN grep -v "^-e " requirements.txt > requirements.docker.txt && \
    pip install --no-cache-dir -r requirements.docker.txt

# Copy worker code
COPY services/airex-worker/app/ ./app/

# Copy config directory (tenant configuration from airex-core)
COPY services/airex-core/config/ /app/airex-core/config/

RUN chown -R airex:airex /app

USER airex

CMD ["arq", "app.core.worker.WorkerSettings"]
