FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY workers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY workers/ ./
COPY shared/ ./shared/

ENV PYTHONPATH=/app

# Default command overridden per-service in docker-compose.yml
CMD ["python", "-m", "worker_audio"]
