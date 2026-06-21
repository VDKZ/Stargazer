# Minimal image to run the Stargazer API with uv.
FROM python:3.12-slim

# uv binary, straight from the official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first so this layer is cached unless the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code.
COPY app ./app

EXPOSE 8000

# Run uvicorn straight from the synced venv (deps already installed at build time).
# app.main is importable from /app (the working directory is on sys.path).
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
