"""
M4 Standalone Mock Flow — Tests the full transcription pipeline without external services.

Flow A: Audio → Whisper → Upload transcript to MinIO → Delete audio from MinIO
Flow B: Transcript already exists → Pass through (no Whisper needed)
"""
import sys
from unittest.mock import patch, MagicMock

# 1. Enable Celery eager mode before loading tasks so they execute synchronously
from m4_app.main import celery_app
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True
)

# 2. Mock external services (S3 only — no MongoDB needed in M4)
@patch("m4_app.services.s3_service.boto3.client")
def run_flow(mock_boto_client):
    # Setup mock S3
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    # Track what gets uploaded to mock S3
    uploaded_files = {}
    deleted_files = []

    def mock_upload(local_path, bucket, key):
        uploaded_files[f"s3://{bucket}/{key}"] = local_path
        print(f"\n  [MinIO] Uploaded: s3://{bucket}/{key}")

    def mock_delete(Bucket=None, Key=None):
        deleted_files.append(f"s3://{Bucket}/{Key}")
        print(f"  [MinIO] Deleted: s3://{Bucket}/{Key}")

    mock_s3.upload_file = mock_upload
    mock_s3.delete_object = mock_delete

    # Mock whisper library
    mock_whisper = MagicMock()
    mock_model = MagicMock()
    mock_whisper.load_model.return_value = mock_model
    mock_model.transcribe.return_value = {"text": "This is a successful mock transcription using OpenAI Whisper small model!"}

    # Use patch context managers to execute the task
    with patch.dict("sys.modules", {"whisper": mock_whisper}), \
         patch("m4_app.tasks.transcription_tasks.os.path.exists", return_value=True), \
         patch("m4_app.tasks.transcription_tasks.os.remove") as mock_remove:

        # Import the Celery task
        from m4_app.tasks.transcription_tasks import process_transcription

        # ========================
        # Test Case A: Audio Flow — Whisper → Upload transcript → Delete audio
        # ========================
        payload_audio = {
            "video_id": "test_audio_001",
            "metadata": {"title": "Test Title Audio", "channel_name": "Test Channel", "duration_seconds": 120},
            "has_captions": False,
            "s3_transcript_uri": None,
            "s3_audio_uri": "s3://video-synopsis-audio/audio/test_audio_001.wav"
        }

        print("=" * 60)
        print("M4 FLOW A: Audio WAV → Whisper → Transcript Upload → Audio Delete")
        print("=" * 60)
        result_audio = process_transcription.delay(payload_audio)
        result_a = result_audio.result

        print(f"\n  Task status: {result_audio.status}")
        print(f"  Result:")
        print(f"    video_id:          {result_a['video_id']}")
        print(f"    source:            {result_a['source']}")
        print(f"    s3_transcript_uri: {result_a['s3_transcript_uri']}")
        print(f"    s3_audio_uri:      {result_a['s3_audio_uri']}")
        print(f"    status:            {result_a['status']}")

        # Verify transcript was uploaded and audio was deleted
        assert result_a["source"] == "whisper", "Source should be 'whisper'"
        assert result_a["s3_transcript_uri"] is not None, "Transcript URI should be set"
        assert result_a["s3_audio_uri"] is None, "Audio URI should be None (deleted)"
        assert result_a["status"] == "transcribed_and_stored"
        assert len(deleted_files) > 0, "Audio should have been deleted from MinIO"

        print("\n  ✅ FLOW A PASSED — Audio transcribed, transcript uploaded, audio deleted!")

        # ========================
        # Test Case B: Captions already exist → pass through
        # ========================
        uploaded_files.clear()
        deleted_files.clear()

        payload_captions = {
            "video_id": "test_captions_002",
            "metadata": {"title": "Test Title Captions", "channel_name": "Test Channel", "duration_seconds": 240},
            "has_captions": True,
            "s3_transcript_uri": "s3://video-synopsis-audio/transcripts/test_captions_002.txt",
            "s3_audio_uri": None
        }

        print("\n" + "=" * 60)
        print("M4 FLOW B: Transcript Already Exists (YouTube Captions) — Pass Through")
        print("=" * 60)
        result_captions = process_transcription.delay(payload_captions)
        result_b = result_captions.result

        print(f"\n  Task status: {result_captions.status}")
        print(f"  Result:")
        print(f"    video_id:          {result_b['video_id']}")
        print(f"    source:            {result_b['source']}")
        print(f"    s3_transcript_uri: {result_b['s3_transcript_uri']}")
        print(f"    s3_audio_uri:      {result_b['s3_audio_uri']}")
        print(f"    status:            {result_b['status']}")

        # Verify no upload or delete happened
        assert result_b["source"] == "youtube_captions", "Source should be 'youtube_captions'"
        assert result_b["s3_transcript_uri"] is not None, "Transcript URI should be passed through"
        assert result_b["s3_audio_uri"] is None, "Audio URI should be None"
        assert result_b["status"] == "transcript_already_exists"
        assert len(uploaded_files) == 0, "Nothing should be uploaded for existing captions"
        assert len(deleted_files) == 0, "Nothing should be deleted for existing captions"

        print("\n  ✅ FLOW B PASSED — Existing transcript passed through, no Whisper needed!")

    print("\n" + "=" * 60)
    print("ALL M4 STANDALONE TESTS PASSED ✅")
    print("=" * 60)

if __name__ == "__main__":
    run_flow()
