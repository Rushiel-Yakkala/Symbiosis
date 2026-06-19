# Module 4: AI / Transcription Module (Standalone Setup)

This is the standalone implementation of **Module 4 (M4: AI / Transcription)** for the video synopsis pipeline. It handles downloading YouTube captions or transcribing raw audio files using **OpenAI Whisper** and saving structured results to **MongoDB**.

---

## Architecture Flow

The pipeline acts as a Celery worker that listens for ingestion triggers:
1. **Existing Captions**: If `s3_transcript_uri` is provided, it downloads the direct text captions.
2. **Audio Transcription**: If `s3_audio_uri` is provided, it downloads the WAV audio and uses OpenAI Whisper to transcribe the audio into text (running on GPU if available, falling back to CPU).
3. **Database Insertion**: Structured documents are upserted into MongoDB containing transcript text, source identifiers, creation timestamps, and video metadata.

---

## File Structure

```text
/m4_standalone
  ├── m4_app/
  │    ├── config/
  │    │    ├── __init__.py
  │    │    └── settings.py              # Env var loading and configurations
  │    ├── services/
  │    │    ├── __init__.py
  │    │    ├── s3_service.py            # Boto3 client pointing to S3 or local MinIO
  │    │    ├── db_service.py            # MongoDB Client and schema configuration
  │    │    └── whisper_service.py       # Lazily cached Whisper model (GPU/CPU)
  │    ├── tasks/
  │    │    ├── __init__.py
  │    │    └── transcription_tasks.py   # Celery task logic with exponential retries
  │    ├── __init__.py
  │    └── main.py                       # Celery application entry point
  ├── Dockerfile                         # Production image setup with FFmpeg
  ├── docker-compose.yml                 # Local dev setup (Redis, MongoDB, MinIO)
  ├── requirements.txt                   # Standard dependency list
  ├── test_m4.py                         # Mock-based unit test suite
  ├── test_trigger.py                    # Live trigger integration test script
  └── run_mocked_flow.py                 # Eager execution mock pipeline run
```

---

## Prerequisites

- **Python 3.8+**
- **FFmpeg**: Required by Whisper to process audio streams.
  - *Windows*: Download via Chocolatey (`choco install ffmpeg`) or from the official website and add it to your System PATH.
  - *macOS*: Install via Homebrew (`brew install ffmpeg`).
  - *Linux*: Install via Apt (`apt-get install ffmpeg`).
- **Docker & Docker Compose** (Optional: for running live local containers).

---

## Getting Started

### 1. Local Virtual Environment Setup
Initialize a Python virtual environment and install the package dependencies:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Infrastructure Setup (Docker)
Start the local message broker, database, and object storage:
```bash
docker compose up -d
```
*This will spin up:*
- **Redis** on port `6379` (Broker)
- **MongoDB** on port `27017` (Database)
- **MinIO** on ports `9000` (API) & `9001` (Console) with bucket `video-synopsis-audio` auto-created.

### 3. Run the Celery Worker
Start the worker process:
```bash
celery -A m4_app.main.celery_app worker --loglevel=info
```

### 4. Trigger Ingestion Test
In another terminal (with venv activated), run the trigger script to generate a dummy WAV file, upload it to MinIO, and queue the Celery task:
```bash
python test_trigger.py
```

---

## Offline Testing & Validation

If you do not have Docker installed, you can still test and verify the entire code pipeline using:

* **Mock Unit Tests**: Runs mock checks verifying download, database formatting, and transcription logic:
  ```bash
  python -m unittest test_m4.py
  ```

* **Eager Execution Run**: Runs the real Celery task synchronously in eager mode, mocking out external database/storage connections:
  ```bash
  python run_mocked_flow.py
  ```

---

## Configuration Variables (`.env`)

You can create a `.env` file in the root of the project to customize settings:
```ini
MINIO_URL=http://localhost:9000
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password123
MONGO_URI=mongodb://localhost:27017
CELERY_BROKER_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
BUCKET_NAME=video-synopsis-audio
```

---

## Production Deployment Checklist

1. **IAM Roles**: In AWS, clear out `MINIO_URL` and credential vars. The `boto3` client will automatically default to standard AWS endpoints and read container IAM policies.
2. **GPU Support**: If running on GPU VMs, ensure `cuda` is available. Whisper will automatically load the model onto GPU hardware.
3. **Resilience**: Task failures triggers automated Celery retries configured with exponential backoffs up to 5 minutes.
4. **Flower Monitoring**: Run Flower side-by-side with Celery for live task monitoring:
   ```bash
   pip install flower
   celery -A m4_app.main.celery_app flower
   ```
