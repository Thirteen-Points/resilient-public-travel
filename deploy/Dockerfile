FROM python:3.12-slim

LABEL maintainer="ResilientRoute Team"
LABEL description="ResilientRoute backend - FastAPI + SQLite"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY data/ ./data/
COPY contracts/ ./contracts/
COPY scripts/ ./scripts/
COPY .env.example ./.env.example

# Create data directories
RUN mkdir -p backend/app/data/cache backend/app/data/snapshots data/sim

# Environment defaults (override with docker-compose or -e)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DEBUG=false
ENV OFFLINE_MODE=true
ENV AI_ENABLED=false
ENV DEPLOY_ENV=docker
ARG APP_BUILD_SHA=unknown
ENV APP_BUILD_SHA=${APP_BUILD_SHA}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
