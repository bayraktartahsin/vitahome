FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# README.md is referenced by pyproject metadata — copy it or the build fails.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "app.gateway.main"]
