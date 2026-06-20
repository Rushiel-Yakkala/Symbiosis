import boto3
import os
from urllib.parse import urlparse
from m4_app.config.settings import settings

def get_s3_client():
    """
    Initializes and returns a boto3 S3 client.
    Supports local MinIO overriding and standard AWS production credentials.
    """
    kwargs = {}
    if settings.MINIO_URL:
        kwargs["endpoint_url"] = settings.MINIO_URL
    if settings.MINIO_ROOT_USER:
        kwargs["aws_access_key_id"] = settings.MINIO_ROOT_USER
    if settings.MINIO_ROOT_PASSWORD:
        kwargs["aws_secret_access_key"] = settings.MINIO_ROOT_PASSWORD
    
    kwargs["region_name"] = settings.AWS_REGION
        
    return boto3.client("s3", **kwargs)

def parse_s3_uri(uri: str):
    """
    Parses an S3 URI (e.g. s3://bucket/key or http://endpoint/bucket/key)
    and returns (bucket, key). If it's a relative path/key, defaults to
    settings.BUCKET_NAME.
    """
    if not uri:
        return None, None
        
    if uri.startswith("s3://"):
        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        return bucket, key
    elif uri.startswith("http://") or uri.startswith("https://"):
        parsed = urlparse(uri)
        # Parse path. Format is usually /bucket/key or similar
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) == 2:
            return path_parts[0], path_parts[1]
        return settings.BUCKET_NAME, parsed.path.lstrip("/")
    
    # Fallback to default bucket and use uri as the key
    return settings.BUCKET_NAME, uri

def download_file(s3_uri: str, local_path: str) -> str:
    """
    Downloads a file from S3/MinIO.
    """
    bucket, key = parse_s3_uri(s3_uri)
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI or key: {s3_uri}")
        
    s3_client = get_s3_client()
    
    # Ensure local directory exists
    local_dir = os.path.dirname(local_path)
    if local_dir and not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
        
    s3_client.download_file(bucket, key, local_path)
    return local_path

def upload_transcript(transcript_text: str, video_id: str, bucket_name: str = None) -> str:
    """
    Uploads transcript text as a .txt file to S3/MinIO under transcripts/{video_id}.txt.
    Returns the s3:// URI of the uploaded transcript.
    (M4 — Whisper transcription output storage)
    """
    if bucket_name is None:
        bucket_name = settings.BUCKET_NAME

    s3_client = get_s3_client()
    object_name = f"transcripts/{video_id}.txt"

    # Write transcript to a temp file, upload, then cleanup
    import tempfile
    temp_fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix=f"trans_{video_id}_")
    os.close(temp_fd)

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        s3_client.upload_file(temp_path, bucket_name, object_name)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return f"s3://{bucket_name}/{object_name}"

def delete_object(bucket_name: str, object_key: str) -> None:
    """
    Deletes an object from S3/MinIO.
    (M4 — Cleanup: remove audio WAV after transcript is stored)
    """
    s3_client = get_s3_client()
    s3_client.delete_object(Bucket=bucket_name, Key=object_key)

