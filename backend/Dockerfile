FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Build the deep-learning forecasting stack (torch) too when INCLUDE_ML=1.
# Default off: torch is large; without it the app falls back to statistical
# forecasting automatically.
ARG INCLUDE_ML=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY requirements-ml.txt .
RUN if [ "$INCLUDE_ML" = "1" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --chown=app:app . .

# WORKDIR /app is root-owned by default; the non-root app user needs write
# access for the SQLite file and runtime dirs (reports, VAPID keys).
RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)" || exit 1

# Start uvicorn FIRST so the service passes Render's health check, and run
# the (potentially slow) national dataset seed concurrently in the background.
# The seed is idempotent; until it finishes the API simply serves fewer rows.
CMD ["sh", "-c", "python -m app.database.local_init > /tmp/seed.log 2>&1 & exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
