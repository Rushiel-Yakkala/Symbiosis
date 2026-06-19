import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys

# Import services and tasks relative to current workspace
from m4_app.services import s3_service, db_service, whisper_service
from m4_app.tasks.transcription_tasks import process_transcription

class TestModule4(unittest.TestCase):
    
    @patch("m4_app.services.s3_service.boto3.client")
    def test_s3_service_download(self, mock_boto_client):
        # Setup mock client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Test download
        s3_service.download_file("audio/xyz.wav", "temp_xyz.wav")
        
        # Check download_file was called with default bucket and key
        mock_s3.download_file.assert_called_once_with(
            "video-synopsis-audio", "audio/xyz.wav", "temp_xyz.wav"
        )
        
    @patch("m4_app.services.db_service.pymongo.MongoClient")
    def test_db_service_save(self, mock_mongo_client):
        # Setup mock mongo client & collection
        mock_client = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_db = mock_client["video_synopsis"]
        mock_coll = mock_db["transcripts"]
        
        metadata = {
            "title": "Test Title",
            "channel_name": "Test Channel",
            "duration_seconds": 120
        }
        
        result = db_service.save_transcript(
            video_id="video123",
            transcript_text="Hello world",
            source="whisper",
            metadata=metadata
        )
        
        # Verify schema structure matches requested requirements
        self.assertEqual(result["_id"], "video123")
        self.assertEqual(result["video_id"], "video123")
        self.assertEqual(result["transcript_text"], "Hello world")
        self.assertEqual(result["source"], "whisper")
        self.assertEqual(result["language"], "en")
        self.assertIn("created_at", result)
        self.assertEqual(result["metadata"]["title"], "Test Title")
        self.assertEqual(result["metadata"]["channel_name"], "Test Channel")
        self.assertEqual(result["metadata"]["duration_seconds"], 120)
        
        # Verify upsert call
        mock_coll.replace_one.assert_called_once_with(
            {"_id": "video123"}, result, upsert=True
        )
        
    @patch("m4_app.services.whisper_service.os.path.exists")
    def test_whisper_service(self, mock_exists):
        mock_exists.return_value = True
        whisper_service._model = None  # Reset cached model
        
        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_whisper.load_model.return_value = mock_model
        mock_model.transcribe.return_value = {"text": "   Transcribed text from whisper   "}
        
        with patch.dict("sys.modules", {"whisper": mock_whisper}):
            # Call transcribe
            text = whisper_service.transcribe_audio("fake_path.wav")
            
            # Verify model loading and transcribe call
            mock_whisper.load_model.assert_called_once_with("base", device="cpu")
            mock_model.transcribe.assert_called_once_with("fake_path.wav")
            self.assertEqual(text, "Transcribed text from whisper")

    @patch("m4_app.tasks.transcription_tasks.os.path.exists")
    @patch("m4_app.tasks.transcription_tasks.os.remove")
    @patch("m4_app.tasks.transcription_tasks.s3_service")
    @patch("m4_app.tasks.transcription_tasks.db_service")
    @patch("m4_app.tasks.transcription_tasks.whisper_service")
    def test_task_whisper_flow(self, mock_whisper, mock_db, mock_s3, mock_remove, mock_exists):
        # Setup mock behaviors
        mock_exists.return_value = True
        mock_whisper.transcribe_audio.return_value = "transcribed audio text"
        mock_db.save_transcript.return_value = {"status": "saved"}
        
        payload = {
            "video_id": "v123",
            "metadata": {"title": "T", "channel_name": "C", "duration_seconds": 10},
            "has_captions": False,
            "s3_transcript_uri": None,
            "s3_audio_uri": "audio/v123.wav"
        }
        
        result = process_transcription(payload)
        
        # S3 download should have been called
        mock_s3.download_file.assert_called_once()
        # Whisper transcription should have been called
        mock_whisper.transcribe_audio.assert_called_once()
        # Save transcript should have been called
        mock_db.save_transcript.assert_called_once_with(
            video_id="v123",
            transcript_text="transcribed audio text",
            source="whisper",
            metadata=payload["metadata"]
        )
        # Cleanup should have deleted the temp file
        mock_remove.assert_called_once()

    @patch("m4_app.tasks.transcription_tasks.os.path.exists")
    @patch("m4_app.tasks.transcription_tasks.os.remove")
    @patch("m4_app.tasks.transcription_tasks.s3_service")
    @patch("m4_app.tasks.transcription_tasks.db_service")
    @patch("builtins.open", new_callable=mock_open, read_data="downloaded caption transcript")
    def test_task_transcript_flow(self, mock_file_open, mock_db, mock_s3, mock_remove, mock_exists):
        mock_exists.return_value = True
        mock_db.save_transcript.return_value = {"status": "saved"}
        
        payload = {
            "video_id": "v456",
            "metadata": {"title": "T2", "channel_name": "C2", "duration_seconds": 20},
            "has_captions": True,
            "s3_transcript_uri": "transcripts/v456.txt",
            "s3_audio_uri": None
        }
        
        result = process_transcription(payload)
        
        # S3 download called
        mock_s3.download_file.assert_called_once()
        # File opened and read
        mock_file_open.assert_called_once()
        # DB save called with captions source
        mock_db.save_transcript.assert_called_once_with(
            video_id="v456",
            transcript_text="downloaded caption transcript",
            source="youtube_captions",
            metadata=payload["metadata"]
        )
        # Cleanup called
        mock_remove.assert_called_once()

if __name__ == "__main__":
    unittest.main()
