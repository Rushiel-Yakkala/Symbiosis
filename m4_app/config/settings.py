import os
from dotenv import load_dotenv

# Load .env file from /m4_standalone/ relative to this settings file
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

class Settings:
    MINIO_URL: str = os.getenv("MINIO_URL", "") # Empty means standard AWS S3 endpoint
    MINIO_ROOT_USER: str = os.getenv("MINIO_ROOT_USER", "") # Empty means boto3 reads IAM credentials
    MINIO_ROOT_PASSWORD: str = os.getenv("MINIO_ROOT_PASSWORD", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    
    # Bucket name for video synopsis audio/transcripts (matches M3's bucket)
    BUCKET_NAME: str = os.getenv("BUCKET_NAME", "video-synopsis-audio")

settings = Settings()
