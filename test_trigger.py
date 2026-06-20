"""
M4 Live Integration Trigger — Tests the full pipeline against real MinIO.

Generates a silent WAV, uploads to MinIO, triggers the M4 Celery task,
then verifies that:
  1. Transcript .txt was uploaded to MinIO transcripts/ folder
  2. Audio .wav was deleted from MinIO audio/ folder
"""
import os
import wave
import struct
import boto3
from m4_app.tasks.transcription_tasks import process_transcription
from m4_app.config.settings import settings

def generate_silent_wav(filename: str, duration_sec: int = 1):
    """
    Generates a valid silent WAV file using the built-in wave module.
    This prevents Whisper from failing due to empty/corrupt audio files.
    """
    print(f"Generating silent WAV file: {filename}...")
    sample_rate = 16000
    num_samples = sample_rate * duration_sec

    with wave.open(filename, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        # Write 0s for silent samples
        for _ in range(num_samples):
            w.writeframes(struct.pack('<h', 0))
    print(f"WAV file generated successfully: {filename} ({os.path.getsize(filename)} bytes)")

def upload_to_minio(local_file: str, bucket: str, s3_key: str):
    """
    Uploads a file to MinIO using credentials from settings.
    """
    print(f"Connecting to MinIO at {settings.MINIO_URL}...")
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.MINIO_URL,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
        region_name="us-east-1",
    )

    # Check if bucket exists, if not create it
    try:
        s3_client.head_bucket(Bucket=bucket)
        print(f"Bucket '{bucket}' already exists.")
    except Exception:
        print(f"Bucket '{bucket}' not found. Creating it...")
        s3_client.create_bucket(Bucket=bucket)

    print(f"Uploading {local_file} to MinIO bucket '{bucket}' with key '{s3_key}'...")
    s3_client.upload_file(local_file, bucket, s3_key)
    print("Upload completed successfully.")

def verify_minio_state(bucket: str, video_id: str):
    """
    Verifies that after M4 processing:
    - transcripts/{video_id}.txt EXISTS in MinIO
    - audio/{video_id}.wav is DELETED from MinIO
    """
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.MINIO_URL,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
        region_name="us-east-1",
    )

    # Check transcript exists
    transcript_key = f"transcripts/{video_id}.txt"
    try:
        s3_client.head_object(Bucket=bucket, Key=transcript_key)
        print(f"\n  ✅ Transcript EXISTS: s3://{bucket}/{transcript_key}")
    except Exception:
        print(f"\n  ❌ Transcript MISSING: s3://{bucket}/{transcript_key}")

    # Check audio is deleted
    audio_key = f"audio/{video_id}.wav"
    try:
        s3_client.head_object(Bucket=bucket, Key=audio_key)
        print(f"  ❌ Audio still EXISTS (should be deleted): s3://{bucket}/{audio_key}")
    except Exception:
        print(f"  ✅ Audio DELETED: s3://{bucket}/{audio_key}")

def main():
    local_audio = "sample.wav"
    bucket = settings.BUCKET_NAME
    video_id = "test_audio_001"
    s3_key = f"audio/{video_id}.wav"

    # 1. Generate local dummy file
    if not os.path.exists(local_audio):
        generate_silent_wav(local_audio)

    # 2. Upload dummy file to MinIO
    upload_to_minio(local_audio, bucket, s3_key)

    # 3. Trigger the M4 Celery task
    mock_payload = {
        "video_id": video_id,
        "metadata": {
            "title": "Test Title",
            "channel_name": "Test Channel",
            "duration_seconds": 120
        },
        "has_captions": False,
        "s3_transcript_uri": None,
        "s3_audio_uri": f"s3://{bucket}/{s3_key}"
    }

    print("\n[M4] Sending 'process_transcription' task asynchronously to Celery...")
    result = process_transcription.delay(mock_payload)
    print(f"[M4] Task sent successfully! Task ID: {result.id}")

    try:
        print("[M4] Waiting for task completion (timeout: 120s)...")
        result_value = result.get(timeout=120)
        print("\n=== M4 TASK COMPLETED SUCCESSFULLY ===")
        print(f"  video_id:          {result_value['video_id']}")
        print(f"  source:            {result_value['source']}")
        print(f"  s3_transcript_uri: {result_value['s3_transcript_uri']}")
        print(f"  s3_audio_uri:      {result_value['s3_audio_uri']}")
        print(f"  status:            {result_value['status']}")

        # 4. Verify MinIO state
        print("\n[M4] Verifying MinIO state...")
        verify_minio_state(bucket, video_id)

    except Exception as e:
        print(f"\n[M4] Task failed or timed out: {e}")

if __name__ == "__main__":
    main()
