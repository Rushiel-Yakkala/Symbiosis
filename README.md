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

### 1. Python Environment
- **Python 3.8+** is required.

### 2. FFmpeg Installation
Whisper requires **FFmpeg** to process and decode audio files. Ensure it is installed and added to your system path:
- **Windows**: Install using Winget (`winget install Gyan.FFmpeg`) or Chocolatey (`choco install ffmpeg`), or download from [ffmpeg.org](https://ffmpeg.org/download.html) and manually add the `bin` directory to your System `PATH`.
- **macOS**: Install using Homebrew (`brew install ffmpeg`).
- **Linux**: Install via apt (`sudo apt-get install -y ffmpeg`).

---

## PART A: Standalone Execution (No Docker)

Follow these steps if you do not have Docker installed or want to run and test the module natively on your machine.

### Step 1: Virtual Environment Setup
Initialize a clean Python virtual environment and install the required dependencies:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> [!TIP]
> First run of OpenAI Whisper will automatically download the required model weights (defaults to the `small` model, ~460MB).

---

### Option A1: Zero-Dependency Offline Execution (Recommended)
If you want to run the code pipeline immediately without installing or running queue or object storage services (like Redis or MinIO/S3), you can run the mock validation suites:

#### 1. Run Unit Tests
Verifies S3, Whisper, and task logic locally with mocked network requests:
```bash
python -m unittest test_m4.py
```

#### 2. Run Eager Pipeline flow
Executes the Celery task synchronously inside your active Python thread using eager mode (`task_always_eager=True`), simulating the download of an audio file, transcribing it using Whisper, and storing the output transcript:
```bash
python run_mocked_flow.py
```

---

### Option A2: Local Native Execution (Using Local Services)
If you want to run the real Celery worker and trigger live integration tasks without using Docker:

#### 1. Setup Local Services
You will need running instances of the following services:
- **Redis Server** (Default port `6379`) - Used as the message broker.
- **MinIO Server** (Default port `9000`/`9001`) or an active **AWS S3** bucket.

Configure these connection URIs in your `.env` file at the root of the project:
```ini
MINIO_URL=http://localhost:9000
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password123
CELERY_BROKER_URL=redis://localhost:6379/0
AWS_REGION=us-east-1
BUCKET_NAME=video-synopsis-audio
```

#### 2. Start the Celery Worker
Activate your virtual environment and start the worker daemon:
```bash
celery -A m4_app.main.celery_app worker --loglevel=info
```

#### 3. Trigger Ingestion and Transcription
In a separate terminal window (with virtual environment activated), execute the trigger test script to upload a sample wav file to local storage, queue the transcription job, and wait for the response:
```bash
python test_trigger.py
```

---

## PART B: Importing & Integrating with Docker

Use these instructions when you are importing the M4 standalone module back into the main **Video Synopsis** pipeline and need to run it inside containerized environments.

### 1. Docker Version Compatibility
Ensure your local host or deployment server meets the following specifications:
- **Docker Engine**: Version `20.10.0` or higher
- **Docker Compose**: Version `2.0.0` or higher (integrated as `docker compose`, not legacy `docker-compose`)

### 2. Building the Worker Image
To build the Docker image for the standalone transcription worker:
```bash
docker build -t m4-transcription-worker:latest .
```

### 3. Deploying via Docker Compose
To spin up all local development infrastructure (Redis and MinIO) inside Docker:
```bash
# Start all supporting services in background
docker compose up -d
```

### 4. Running the Celery Worker Container
Once the services are active, you can spin up the worker container:
```bash
# Start the worker container referencing local network
docker run --name m4_worker --network m4_standalone_default -e CELERY_BROKER_URL=redis://redis:6379/0 m4-transcription-worker:latest
```

---

## Configuration Variables Reference

Customize your environment variables in `.env`:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `MINIO_URL` | `http://localhost:9000` | Endpoint URL for MinIO (leave blank for real AWS S3) |
| `MINIO_ROOT_USER` | `admin` | Access key ID for MinIO / S3 |
| `MINIO_ROOT_PASSWORD` | `password123` | Secret access key for MinIO / S3 |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis broker and backend connection URI |
| `AWS_REGION` | `us-east-1` | Target S3 bucket AWS Region |
| `BUCKET_NAME` | `video-synopsis-audio` | Destination bucket name for files |

---

## How M4 Connects with M3

See [M4CONNECTIVITY.md](M4CONNECTIVITY.md) for the full integration guide showing how M4 plugs into the M3 (video-synopsis-ai) pipeline.

**Quick summary:**
- M3 ingests a YouTube URL, downloads audio (if no captions), and uploads it to MinIO
- M4 picks up the ingestion result, transcribes the audio, uploads the transcript, and deletes the audio
- The final output is always a transcript `.txt` file in MinIO — never a raw audio file

---

## Production Checklist & Optimization

1. **IAM Roles**: When deploying to AWS ECS or EKS, remove `MINIO_URL` and credential keys from `.env`. The `boto3` client will automatically default to standard AWS S3 endpoints and read the container IAM roles.
2. **GPU Acceleration**: If deploying on GPU-enabled virtual machines (e.g. AWS `g4dn` instances), ensure PyTorch CUDA is installed inside the image. Whisper will automatically load the model onto the GPU.
3. **Task Monitoring**: Run Flower side-by-side with your worker to inspect active queues and task progress:
   ```bash
   pip install flower
   celery -A m4_app.main.celery_app flower
   ```
