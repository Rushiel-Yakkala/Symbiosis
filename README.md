# Module 4: AI / Transcription Module (Standalone Setup)

This is the standalone implementation of **Module 4 (M4: AI / Transcription)** for the video synopsis pipeline. It handles transcribing raw audio files using **OpenAI Whisper (small model)**, uploading the resulting transcripts to **MinIO/S3**, and cleaning up the original audio files.

---

## Architecture Flow

The pipeline acts as a Celery worker that listens for ingestion triggers from M3 (Module 1 — YouTube Ingestion):

1. **Flow A — Captions Exist**: If `s3_transcript_uri` is provided in the ingestion result, M4 passes it through. No Whisper transcription needed — the transcript already lives in MinIO.
2. **Flow B — Audio Only (No Captions)**: If `s3_audio_uri` is provided:
   - Downloads the WAV audio file from MinIO
   - Transcribes it using OpenAI Whisper (small model, ~460MB, GPU-accelerated if available)
   - Uploads the transcript text to MinIO at `s3://video-synopsis-audio/transcripts/{video_id}.txt`
   - **Deletes the original audio** from MinIO at `s3://video-synopsis-audio/audio/{video_id}.wav`

> **No MongoDB is used.** All outputs are stored in MinIO/S3.

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
  │    │    ├── s3_service.py            # S3/MinIO: download, upload transcript, delete audio
  │    │    ├── db_service.py            # (Legacy — not used in current flow)
  │    │    └── whisper_service.py       # Whisper small model (GPU/CPU, lazily cached)
  │    ├── tasks/
  │    │    ├── __init__.py
  │    │    └── transcription_tasks.py   # Celery task: Whisper → upload → cleanup
  │    ├── __init__.py
  │    └── main.py                       # Celery application entry point
  ├── Dockerfile                         # Production image setup with FFmpeg
  ├── docker-compose.yml                 # Local dev setup (Redis, MinIO)
  ├── requirements.txt                   # Standard dependency list
  ├── test_m4.py                         # Unit test suite (mocked)
  ├── test_trigger.py                    # Live integration test against MinIO
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
Start the local message broker and object storage:
```bash
docker compose up -d
```
*This will spin up:*
- **Redis** on port `6379` (Broker)
- **MinIO** on ports `9000` (API) & `9001` (Console) with bucket `video-synopsis-audio` auto-created.

> **Note:** MongoDB is no longer required for M4.

### 3. Run the Celery Worker
Start the worker process:
```bash
celery -A m4_app.main.celery_app worker --loglevel=info
```

### 4. Trigger Ingestion Test
In another terminal (with venv activated), run the trigger script to generate a dummy WAV file, upload it to MinIO, and queue the M4 Celery task:
```bash
python test_trigger.py
```

---

## Offline Testing & Validation

If you do not have Docker installed, you can still test and verify the entire code pipeline using:

* **Mock Unit Tests**: Runs mock checks verifying download, upload, delete, and transcription logic:
  ```bash
  python -m unittest test_m4.py
  ```

* **Eager Execution Run**: Runs the real Celery task synchronously in eager mode, mocking out external storage connections:
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
CELERY_BROKER_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
BUCKET_NAME=video-synopsis-audio
```

---

## How M4 Connects with M3

See [M4CONNECTIVITY.md](M4CONNECTIVITY.md) for the full integration guide showing how M4 plugs into the M3 (video-synopsis-ai) pipeline.

**Quick summary:**
- M3 ingests a YouTube URL, downloads audio (if no captions), and uploads it to MinIO
- M4 picks up the ingestion result, transcribes the audio, uploads the transcript, and deletes the audio
- The final output is always a transcript `.txt` file in MinIO — never a raw audio file

---

## Production Deployment Checklist

1. **IAM Roles**: In AWS, clear out `MINIO_URL` and credential vars. The `boto3` client will automatically default to standard AWS endpoints and read container IAM policies.
2. **GPU Support**: If running on GPU VMs, ensure `cuda` is available. Whisper will automatically load the model onto GPU hardware.
3. **Resilience**: Task failures trigger automated Celery retries configured with exponential backoffs up to 5 minutes.
4. **Flower Monitoring**: Run Flower side-by-side with Celery for live task monitoring:
   ```bash
   pip install flower
   celery -A m4_app.main.celery_app flower
   ```
