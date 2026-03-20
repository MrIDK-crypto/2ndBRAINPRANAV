# Backend Dockerfile for AWS ECS Fargate
FROM python:3.12-slim

# Cache buster - change this value to force rebuild: v2
ARG CACHE_BUST=2

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model with curl (more reliable retries) then install locally
# Filename must match wheel naming convention for pip to accept it
RUN curl -L --retry 5 --retry-delay 3 -o /tmp/en_core_web_sm-3.7.0-py3-none-any.whl \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0-py3-none-any.whl && \
    pip install /tmp/en_core_web_sm-3.7.0-py3-none-any.whl && \
    rm /tmp/en_core_web_sm-3.7.0-py3-none-any.whl

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/data/protocol_corpus /app/data/protocol_corpus/repos /app/data/protocol_models

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=5002

# Expose port
EXPOSE 5002

# Health check - allow 120s for startup (DB init, model sync, gunicorn workers)
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:5002/api/health || exit 1

# Run the application with entrypoint (seeds DB then starts gunicorn)
CMD ["/app/entrypoint.sh"]
# Trigger rebuild Fri Mar 20 12:40:34 PDT 2026
