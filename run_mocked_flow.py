import sys
from unittest.mock import patch, MagicMock, mock_open

# 1. Enable Celery eager mode before loading tasks so they execute synchronously
from m4_app.main import celery_app
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True
)

# 2. Mock external services
@patch("m4_app.services.s3_service.boto3.client")
@patch("m4_app.services.db_service.pymongo.MongoClient")
def run_flow(mock_mongo_client, mock_boto_client):
    # Setup mock S3
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3
    
    # Setup mock Mongo
    mock_client = MagicMock()
    mock_mongo_client.return_value = mock_client
    mock_db = mock_client["video_synopsis"]
    mock_coll = mock_db["transcripts"]
    
    # We will print what gets saved to the mock DB
    def save_mock_doc(query, doc, upsert=True):
        print(f"\n[MongoDB] Mock saved document:")
        print(f"  _id: {doc['_id']}")
        print(f"  video_id: {doc['video_id']}")
        print(f"  source: {doc['source']}")
        print(f"  transcript_text: '{doc['transcript_text']}'")
        print(f"  language: {doc['language']}")
        print(f"  created_at: {doc['created_at']}")
        print(f"  metadata: {doc['metadata']}")
        return MagicMock()
    mock_coll.replace_one = save_mock_doc
    
    # Mock whisper library
    mock_whisper = MagicMock()
    mock_model = MagicMock()
    mock_whisper.load_model.return_value = mock_model
    mock_model.transcribe.return_value = {"text": "This is a successful mock transcription using OpenAI Whisper!"}
    
    # Mock file open for captions flow
    mock_file = mock_open(read_data="This is a mock caption transcript from YouTube captions.")
    
    # Use patch context managers to execute the task
    with patch.dict("sys.modules", {"whisper": mock_whisper}), \
         patch("builtins.open", mock_file), \
         patch("m4_app.tasks.transcription_tasks.os.path.exists", return_value=True), \
         patch("m4_app.tasks.transcription_tasks.os.remove") as mock_remove:
         
        # Import the Celery task
        from m4_app.tasks.transcription_tasks import process_transcription
        
        # Test Case A: Audio Flow (Whisper)
        payload_audio = {
            "video_id": "test_audio_001",
            "metadata": {"title": "Test Title Audio", "channel_name": "Test Channel", "duration_seconds": 120},
            "has_captions": False,
            "s3_transcript_uri": None,
            "s3_audio_uri": "s3://video-synopsis-audio/audio/test_audio_001.wav"
        }
        
        print("="*60)
        print("RUNNING FLOW A: Audio WAV Download & Whisper Transcription")
        print("="*60)
        result_audio = process_transcription.delay(payload_audio)
        print(f"Task A execution status: {result_audio.status}")
        
        # Test Case B: Captions Flow (Direct Text download)
        payload_captions = {
            "video_id": "test_captions_002",
            "metadata": {"title": "Test Title Captions", "channel_name": "Test Channel", "duration_seconds": 240},
            "has_captions": True,
            "s3_transcript_uri": "s3://video-synopsis-audio/transcripts/test_captions_002.txt",
            "s3_audio_uri": None
        }
        
        print("\n" + "="*60)
        print("RUNNING FLOW B: Existing YouTube Captions Download")
        print("="*60)
        result_captions = process_transcription.delay(payload_captions)
        print(f"Task B execution status: {result_captions.status}")

if __name__ == "__main__":
    run_flow()
