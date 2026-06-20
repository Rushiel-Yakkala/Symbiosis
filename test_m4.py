"""
M4 Unit Tests — Validates the standalone transcription pipeline.

Tests:
- S3 download service
- S3 upload_transcript service
- S3 delete_object service
- Whisper service (small model)
- Full task: audio flow (Whisper → upload transcript → delete audio)
- Full task: captions pass-through flow
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys

# Import services and tasks
from m4_app.services import s3_service, whisper_service
from m4_app.tasks.transcription_tasks import process_transcription


class TestM4S3Service(unittest.TestCase):
    """Tests for S3/MinIO service functions."""

    @patch("m4_app.services.s3_service.boto3.client")
    def test_s3_download(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        s3_service.download_file("audio/xyz.wav", "temp_xyz.wav")

        mock_s3.download_file.assert_called_once_with(
            "video-synopsis-audio", "audio/xyz.wav", "temp_xyz.wav"
        )

    @patch("m4_app.services.s3_service.boto3.client")
    def test_s3_upload_transcript(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        result = s3_service.upload_transcript("Hello world transcript", "vid123")

        self.assertEqual(result, "s3://video-synopsis-audio/transcripts/vid123.txt")
        mock_s3.upload_file.assert_called_once()

    @patch("m4_app.services.s3_service.boto3.client")
    def test_s3_delete_object(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        s3_service.delete_object("video-synopsis-audio", "audio/vid123.wav")

        mock_s3.delete_object.assert_called_once_with(
            Bucket="video-synopsis-audio", Key="audio/vid123.wav"
        )


class TestM4WhisperService(unittest.TestCase):
    """Tests for Whisper transcription service (small model)."""

    @patch("m4_app.services.whisper_service.os.path.exists")
    def test_whisper_transcription(self, mock_exists):
        mock_exists.return_value = True
        whisper_service._model = None  # Reset cached model

        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_whisper.load_model.return_value = mock_model
        mock_model.transcribe.return_value = {"text": "   Transcribed text from whisper   "}

        with patch.dict("sys.modules", {"whisper": mock_whisper}):
            text = whisper_service.transcribe_audio("fake_path.wav")

            # Verify small model is loaded (M4 uses small for better accuracy)
            mock_whisper.load_model.assert_called_once_with("small", device="cpu")
            mock_model.transcribe.assert_called_once_with("fake_path.wav")
            self.assertEqual(text, "Transcribed text from whisper")


class TestM4TranscriptionTask(unittest.TestCase):
    """Tests for the M4 Celery transcription task."""

    @patch("m4_app.tasks.transcription_tasks.os.path.exists")
    @patch("m4_app.tasks.transcription_tasks.os.remove")
    @patch("m4_app.tasks.transcription_tasks.s3_service")
    @patch("m4_app.tasks.transcription_tasks.whisper_service")
    def test_audio_flow_whisper(self, mock_whisper, mock_s3, mock_remove, mock_exists):
        """Flow B: Audio → Whisper → Upload transcript → Delete audio."""
        mock_exists.return_value = True
        mock_whisper.transcribe_audio.return_value = "transcribed audio text"
        mock_s3.upload_transcript.return_value = "s3://video-synopsis-audio/transcripts/v123.txt"
        mock_s3.parse_s3_uri.return_value = ("video-synopsis-audio", "audio/v123.wav")

        payload = {
            "video_id": "v123",
            "metadata": {"title": "T", "channel_name": "C", "duration_seconds": 10},
            "has_captions": False,
            "s3_transcript_uri": None,
            "s3_audio_uri": "s3://video-synopsis-audio/audio/v123.wav"
        }

        result = process_transcription(payload)

        # S3 download should have been called (downloading audio)
        mock_s3.download_file.assert_called_once()
        # Whisper transcription should have been called
        mock_whisper.transcribe_audio.assert_called_once()
        # Transcript should have been uploaded to MinIO
        mock_s3.upload_transcript.assert_called_once_with("transcribed audio text", "v123")
        # Audio should have been deleted from MinIO
        mock_s3.delete_object.assert_called_once_with("video-synopsis-audio", "audio/v123.wav")
        # Result should have transcript URI and no audio URI
        self.assertEqual(result["source"], "whisper")
        self.assertEqual(result["s3_transcript_uri"], "s3://video-synopsis-audio/transcripts/v123.txt")
        self.assertIsNone(result["s3_audio_uri"])
        self.assertEqual(result["status"], "transcribed_and_stored")
        # Local temp file should have been cleaned up
        mock_remove.assert_called_once()

    def test_captions_passthrough(self):
        """Flow A: Transcript already exists — pass through, no Whisper."""
        payload = {
            "video_id": "v456",
            "metadata": {"title": "T2", "channel_name": "C2", "duration_seconds": 20},
            "has_captions": True,
            "s3_transcript_uri": "s3://video-synopsis-audio/transcripts/v456.txt",
            "s3_audio_uri": None
        }

        result = process_transcription(payload)

        # Should pass through without any external calls
        self.assertEqual(result["source"], "youtube_captions")
        self.assertEqual(result["s3_transcript_uri"], "s3://video-synopsis-audio/transcripts/v456.txt")
        self.assertIsNone(result["s3_audio_uri"])
        self.assertEqual(result["status"], "transcript_already_exists")

    def test_missing_video_id_raises(self):
        """Task should raise ValueError when video_id is missing."""
        payload = {
            "metadata": {},
            "s3_transcript_uri": None,
            "s3_audio_uri": None
        }
        with self.assertRaises(ValueError):
            process_transcription(payload)

    def test_no_uri_raises(self):
        """Task should raise ValueError when both URIs are missing."""
        payload = {
            "video_id": "v789",
            "metadata": {},
            "s3_transcript_uri": None,
            "s3_audio_uri": None
        }
        with self.assertRaises(ValueError):
            process_transcription(payload)


if __name__ == "__main__":
    unittest.main()
