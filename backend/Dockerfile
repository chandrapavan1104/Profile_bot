# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build tools (needed by some Python packages)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY docs ./docs

# Environment variables
ENV VECTOR_STORE_PATH=/tmp/data_store \
    DOCUMENTS_PATH=gs://profile_bot_docs \
    VECTOR_STORE_GCS_URI=gs://profile-bot-chroma \
    PORT=8080

# Create vector store dir
RUN mkdir -p /tmp/data_store

# Switch to non-root user for security
RUN addgroup --system app && adduser --system --ingroup app appuser
RUN chown -R appuser:app /tmp/data_store
USER appuser

EXPOSE 8080

# ✅ Run uvicorn directly (no shell)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
