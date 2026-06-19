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

def main():
    local_audio = "sample.wav"
    bucket = settings.BUCKET_NAME
    s3_key = "audio/test_audio_001.wav"
    
    # 1. Generate local dummy file
    if not os.path.exists(local_audio):
        generate_silent_wav(local_audio)
        
    # 2. Upload dummy file to MinIO
    upload_to_minio(local_audio, bucket, s3_key)
    
    # 3. Trigger the Celery task
    mock_payload = {
        "video_id": "test_audio_001",
        "metadata": {
            "title": "Test Title",
            "channel_name": "Test Channel",
            "duration_seconds": 120
        },
        "has_captions": False,
        "s3_transcript_uri": None,
        "s3_audio_uri": f"s3://{bucket}/{s3_key}"
    }
    
    print("\nSending 'process_transcription' task asynchronously to Celery...")
    result = process_transcription.delay(mock_payload)
    print(f"Task sent successfully! Task ID: {result.id}")
    print("You can monitor the Celery worker terminal to watch the execution progress.")
    
    try:
        print("Waiting for task completion and returning result (timeout: 60s)...")
        result_value = result.get(timeout=60)
        print("\n=== TASK COMPLETED SUCCESSFULLY ===")
        print(f"Result: {result_value}")
    except Exception as e:
        print(f"\nTask failed or timed out: {e}")

if __name__ == "__main__":
    main()
