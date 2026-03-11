FROM python:3.12-slim

RUN groupadd -r airex && useradd -r -g airex airex

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install airex-core first (from local path)
COPY services/airex-core/ ./airex-core/
RUN pip install --no-cache-dir -e ./airex-core/

# Install API-specific dependencies
COPY services/airex-api/requirements.txt ./requirements.txt
RUN grep -v "^-e " requirements.txt > requirements.docker.txt && \
    pip install --no-cache-dir -r requirements.docker.txt

# Copy API code
COPY services/airex-api/app/ ./app/

# Copy config directory (tenant configuration from airex-core)
COPY services/airex-core/config/ /app/airex-core/config/

RUN chown -R airex:airex /app

USER airex

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
