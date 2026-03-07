FROM ghcr.io/berriai/litellm:main-v1.60.0

WORKDIR /app

COPY services/litellm/config.yaml /app/config.yaml

EXPOSE 4000

CMD ["--config", "/app/config.yaml", "--port", "4000", "--host", "0.0.0.0"]
