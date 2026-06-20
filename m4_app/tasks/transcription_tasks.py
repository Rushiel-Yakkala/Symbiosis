import os
import tempfile
import logging
from celery import shared_task

from m4_app.services import s3_service, whisper_service

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
    M4 Celery task: receives the ingestion result from Module 1 (M3).

    Flow A — Captions exist (s3_transcript_uri is set):
        The transcript text already lives in MinIO. Nothing to do — return the URI as-is.

    Flow B — No captions (s3_audio_uri is set):
        1. Download the audio WAV from MinIO
        2. Transcribe it locally with OpenAI Whisper (small model)
        3. Upload the resulting transcript text to MinIO at transcripts/{video_id}.txt
        4. Delete the original audio WAV from MinIO (cleanup)
        5. Return the new s3_transcript_uri

    No MongoDB is used. All outputs are stored in MinIO/S3.
    """
    logger.info(f"[M4] Starting process_transcription for: {ingestion_result}")

    video_id = ingestion_result.get("video_id")
    metadata = ingestion_result.get("metadata", {})
    s3_transcript_uri = ingestion_result.get("s3_transcript_uri")
    s3_audio_uri = ingestion_result.get("s3_audio_uri")

    if not video_id:
        raise ValueError("Ingestion result payload must contain 'video_id'")

    temp_files = []

    try:
        if s3_transcript_uri:
            # ----- Flow A: Captions already exist in MinIO -----
            logger.info(f"[M4] Transcript already exists at: {s3_transcript_uri}. No Whisper needed.")

            return {
                "video_id": video_id,
                "metadata": metadata,
                "source": "youtube_captions",
                "s3_transcript_uri": s3_transcript_uri,
                "s3_audio_uri": None,
                "status": "transcript_already_exists"
            }

        elif s3_audio_uri:
            # ----- Flow B: Audio exists, needs Whisper transcription -----
            logger.info(f"[M4] Audio found at: {s3_audio_uri}. Starting Whisper transcription pipeline.")

            # Step 1: Download audio WAV from MinIO
            temp_fd, temp_audio_path = tempfile.mkstemp(suffix=".wav", prefix=f"audio_{video_id}_")
            os.close(temp_fd)
            temp_files.append(temp_audio_path)

            logger.info(f"[M4] Downloading audio from S3: {s3_audio_uri}")
            s3_service.download_file(s3_audio_uri, temp_audio_path)

            # Step 2: Transcribe with Whisper (small model)
            logger.info(f"[M4] Running Whisper transcription on: {temp_audio_path}")
            transcript_text = whisper_service.transcribe_audio(temp_audio_path)

            if not transcript_text:
                raise ValueError(f"Whisper returned empty transcription for video {video_id}")

            logger.info(f"[M4] Whisper transcription complete. Length: {len(transcript_text)} chars")

            # Step 3: Upload transcript text to MinIO transcripts/ folder
            logger.info(f"[M4] Uploading transcript to MinIO for video: {video_id}")
            new_transcript_uri = s3_service.upload_transcript(transcript_text, video_id)
            logger.info(f"[M4] Transcript uploaded to: {new_transcript_uri}")

            # Step 4: Delete the original audio WAV from MinIO
            audio_bucket, audio_key = s3_service.parse_s3_uri(s3_audio_uri)
            if audio_bucket and audio_key:
                logger.info(f"[M4] Deleting audio from MinIO: {audio_bucket}/{audio_key}")
                s3_service.delete_object(audio_bucket, audio_key)
                logger.info(f"[M4] Audio deleted successfully.")

            return {
                "video_id": video_id,
                "metadata": metadata,
                "source": "whisper",
                "s3_transcript_uri": new_transcript_uri,
                "s3_audio_uri": None,  # Audio has been cleaned up
                "status": "transcribed_and_stored"
            }

        else:
            raise ValueError(
                "Invalid ingestion result: both s3_transcript_uri and s3_audio_uri are null/missing."
            )

    except Exception as e:
        logger.error(f"[M4] Failed to process transcription for video {video_id}: {str(e)}", exc_info=True)
        raise

    finally:
        # Clean up local temporary files
        for path in temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"[M4] Removed temp file: {path}")
                except Exception as err:
                    logger.warning(f"[M4] Could not remove temp file {path}: {str(err)}")
