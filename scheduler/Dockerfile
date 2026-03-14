FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY scheduler/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scheduler/ ./scheduler/
COPY shared/ ./shared/

ENV PYTHONPATH=/app

CMD ["python", "-m", "scheduler.main"]
