FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

COPY apps/api /app/apps/api
COPY demo /app/demo
COPY scripts/render-predeploy-api.sh /app/scripts/render-predeploy-api.sh
ENV PYTHONPATH=/app/apps/api:/app

RUN pip install --no-cache-dir -e /app/apps/api

WORKDIR /app/apps/api
ENV PORT=8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
