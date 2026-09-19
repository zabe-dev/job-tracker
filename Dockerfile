FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOBTRACKER_HOST=0.0.0.0 \
    JOBTRACKER_PORT=8000 \
    JOBTRACKER_DB_PATH=/data/jobtracker.db \
    CODEX_HOME=/data/codex \
    PATH=/root/.local/bin:/root/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl poppler-utils \
    && curl -fsSL https://chatgpt.com/codex/install.sh | sh \
    && command -v codex \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN mkdir -p /data/codex
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/state', timeout=3)"

CMD ["python3", "server.py"]
