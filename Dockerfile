FROM python:3.11-slim

# Install system dependencies (ffmpeg is required by Whisper for audio decoding)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Run Celery worker command by default
CMD ["celery", "-A", "m4_app.main.celery_app", "worker", "--loglevel=info"]
