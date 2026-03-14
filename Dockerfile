# ── Stage 1: Build ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build-time system dependencies (PostgreSQL client libs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install only the runtime library needed by psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Render injects PORT at runtime; default to 10000 for local testing
ENV PORT=10000

EXPOSE ${PORT}

# Run the application — $PORT is expanded at runtime by the shell
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
