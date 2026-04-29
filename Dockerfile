FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=10000
ENV MARKET_SCOUT_ROOT=/app
ENV MARKET_SCOUT_WEB_ROOT=/app/web
ENV MARKET_SCOUT_CACHE_DIR=/tmp/market_scout_cache

WORKDIR /app

COPY pyproject.toml README.md ./
COPY market_scout ./market_scout
COPY web ./web
COPY data ./data

RUN pip install --no-cache-dir .

EXPOSE 10000

CMD ["python", "-B", "-m", "market_scout.web"]
