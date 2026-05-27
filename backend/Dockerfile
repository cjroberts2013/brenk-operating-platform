# Brenk Operating Platform — Backend Dockerfile
# Used for both the web service and the worker process on Fly.io.
# The CMD here is the web default; the worker app overrides via its
# fly.worker.toml processes config.

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System deps:
#   build-essential + libpq-dev — building psycopg2 from source if a
#     wheel isn't available for the runtime arch. We use the -binary
#     variant in pyproject, so this is belt-and-suspenders.
#   tini — proper signal handling for the entrypoint so SIGTERM
#     reaches uvicorn / procrastinate on Fly machine restarts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first, in a separate layer, so source-only
# changes don't bust the dep cache on subsequent builds.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

# Application source.
COPY . .

EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
