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

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=5002

# Expose port
EXPOSE 5002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5002/api/health || exit 1

# Run the application with gunicorn for production
# Using gevent for async non-blocking I/O - best for API/database operations
CMD gunicorn --bind 0.0.0.0:$PORT --workers 4 --worker-class gevent --timeout 300 --graceful-timeout 30 app_v2:app
