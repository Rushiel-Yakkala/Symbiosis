import os
import tempfile
import logging
from celery import shared_task

from m4_app.services import s3_service, db_service, whisper_service

logger = logging.getLogger(__name__)

@shared_task(
    name="process_transcription",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5
)
def process_transcription(self, ingestion_result: dict) -> dict:
    """
    Celery task that receives the ingestion result from Module 1.
    If captions exist, it downloads the text file from S3/MinIO.
    Otherwise, it downloads the audio WAV file and runs Whisper transcription.
    The resulting transcript is saved to MongoDB.
    """
    logger.info(f"Starting process_transcription for ingestion result: {ingestion_result}")
    
    video_id = ingestion_result.get("video_id")
    metadata = ingestion_result.get("metadata", {})
    s3_transcript_uri = ingestion_result.get("s3_transcript_uri")
    s3_audio_uri = ingestion_result.get("s3_audio_uri")
    
    if not video_id:
        raise ValueError("Ingestion result payload must contain 'video_id'")
        
    temp_files = []
    
    try:
        if s3_transcript_uri:
            # Flow A: Download existing transcript text file
            logger.info(f"Download transcript from S3: {s3_transcript_uri}")
            
            # Generate a temporary file path
            temp_fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix=f"trans_{video_id}_")
            os.close(temp_fd)  # Close the file descriptor immediately
            temp_files.append(temp_path)
            
            # Download file from S3/MinIO
            s3_service.download_file(s3_transcript_uri, temp_path)
            
            # Read transcript contents
            with open(temp_path, "r", encoding="utf-8") as f:
                transcript_text = f.read().strip()
                
            source = "youtube_captions"
            logger.info(f"Successfully loaded transcript for video_id: {video_id}")
            
        elif s3_audio_uri:
            # Flow B: Download audio WAV file and transcribe with Whisper
            logger.info(f"Download audio from S3: {s3_audio_uri}")
            
            # Generate temporary file path for WAV
            temp_fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix=f"audio_{video_id}_")
            os.close(temp_fd)  # Close the file descriptor immediately
            temp_files.append(temp_path)
            
            # Download file from S3/MinIO
            s3_service.download_file(s3_audio_uri, temp_path)
            
            # Run transcription using Whisper
            transcript_text = whisper_service.transcribe_audio(temp_path)
            source = "whisper"
            logger.info(f"Successfully transcribed audio for video_id: {video_id}")
            
        else:
            raise ValueError(
                "Invalid ingestion result: both s3_transcript_uri and s3_audio_uri are null/missing."
            )
            
        # Save results to MongoDB
        saved_doc = db_service.save_transcript(
            video_id=video_id,
            transcript_text=transcript_text,
            source=source,
            metadata=metadata
        )
        
        logger.info(f"Successfully stored transcript for video_id {video_id} to MongoDB.")
        return saved_doc
        
    except Exception as e:
        logger.error(f"Failed to process transcription for video {video_id}: {str(e)}", exc_info=True)
        raise
        
    finally:
        # Clean up temporary files
        for path in temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Removed temp file: {path}")
                except Exception as err:
                    logger.warning(f"Could not remove temp file {path}: {str(err)}")
