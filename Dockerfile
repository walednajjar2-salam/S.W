FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    SMM_DATA_DIR=/app/data \
    SMM_DATABASE_PATH=/app/data/panel.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data

COPY smm-panel/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY smm-panel/ ./

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'

CMD ["python", "run.py"]
