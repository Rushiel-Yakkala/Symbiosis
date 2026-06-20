# Module 4: Standalone Whisper Transcription Pipeline

This guide outlines how to configure, run, and verify the standalone **Module 4 (M4: AI / Transcription)** pipeline.

---

## 1. Prerequisites

Make sure the following system tools are installed:
* **Docker** & **Docker Compose** (to run local Redis and MinIO storage).
* **Python 3.8+**
* **FFmpeg** (required by Whisper for audio processing). Ensure it's in your system's PATH.

---

## 2. Local Setup Steps

### Step A: Initialize Virtual Environment & Dependencies
1. Open a terminal in this directory: `c:\Users\VIGNAN\Symbiosis`.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Step B: Launch Services (Docker)
Launch local instances of Redis (broker) and MinIO (object storage):
```bash
docker compose up -d
```
* **Redis** runs on `localhost:6379`.
* **MinIO Console** runs on `http://localhost:9001` (Username: `admin`, Password: `password123`).

### Step C: Configure Environments
Create a file named `.env` in the root of `c:\Users\VIGNAN\Symbiosis` with the following contents:
```env
MINIO_URL=http://localhost:9000
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password123
CELERY_BROKER_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
BUCKET_NAME=video-synopsis-audio
```

---

## 3. Running & Verifying the Pipeline

You can verify the setup in three ways (from easiest/quickest to full integration):

### Option 1: Mock Unit Tests (Does not require Docker/Services)
Verify S3, Whisper, and task logic locally with mocked network requests:
```bash
python -m unittest test_m4.py -v
```

### Option 2: Mocked Flow Run (Does not require Docker/Services)
Executes the Celery task synchronously in eager mode, mocking out only the S3/MinIO client and Whisper library:
```bash
python run_mocked_flow.py
```

### Option 3: Live Integration Test (Requires Docker/Services running)
This runs the full asynchronous flow against your live MinIO/Redis containers.
1. Start the Celery worker in one terminal (make sure your `.venv` is active):
   ```bash
   celery -A m4_app.main.celery_app worker --loglevel=info
   ```
2. Trigger the live test in a second terminal:
   ```bash
   python test_trigger.py
   ```

#### What `test_trigger.py` does:
1. Generates a valid silent WAV file (`sample.wav`).
2. Uploads the WAV file to the `video-synopsis-audio` bucket inside local MinIO.
3. Sends a `process_transcription` Celery task.
4. The worker downloads the WAV file, transcribes it with OpenAI Whisper (small model), and uploads the transcript `.txt` file back to MinIO.
5. The worker deletes the original WAV file from MinIO.
6. The test script verifies that `transcripts/test_audio_001.txt` exists and `audio/test_audio_001.wav` has been successfully deleted from MinIO.

---

## 4. Standalone File Reference

* **[`m4_app/config/settings.py`](file:///c:/Users/VIGNAN/Symbiosis/m4_app/config/settings.py)**: Manages local settings and environment variables.
* **[`m4_app/services/s3_service.py`](file:///c:/Users/VIGNAN/Symbiosis/m4_app/services/s3_service.py)**: Helper library for interacting with MinIO/S3 (downloads WAV, uploads transcripts, deletes objects).
* **[`m4_app/services/whisper_service.py`](file:///c:/Users/VIGNAN/Symbiosis/m4_app/services/whisper_service.py)**: Lazily loads the Whisper `small` model and runs transcription.
* **[`m4_app/tasks/transcription_tasks.py`](file:///c:/Users/VIGNAN/Symbiosis/m4_app/tasks/transcription_tasks.py)**: The Celery task orchestrator.
