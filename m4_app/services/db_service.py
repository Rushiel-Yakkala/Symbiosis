import pymongo
from datetime import datetime, timezone
from m4_app.config.settings import settings

_mongo_client = None

def get_mongo_client():
    """
    Initializes and returns a cached PyMongo MongoClient.
    Configured for production-level timeouts and retries.
    """
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            retryWrites=True
        )
    return _mongo_client

def get_transcripts_collection():
    """
    Returns the transcripts collection in the video_synopsis database.
    """
    client = get_mongo_client()
    db = client["video_synopsis"]
    return db["transcripts"]

def save_transcript(video_id: str, transcript_text: str, source: str, metadata: dict) -> dict:
    """
    Constructs and inserts or updates (upserts) the transcript document
    in the transcripts collection using video_id as the primary key.
    """
    collection = get_transcripts_collection()
    
    # ISO-8601 UTC Timestamp with 'Z' suffix
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    document = {
        "_id": video_id,
        "video_id": video_id,
        "transcript_text": transcript_text,
        "source": source,
        "language": "en",
        "created_at": created_at,
        "metadata": {
            "title": metadata.get("title", ""),
            "channel_name": metadata.get("channel_name", ""),
            "duration_seconds": int(metadata.get("duration_seconds", 0))
        }
    }
    
    # Upsert the document
    collection.replace_one({"_id": video_id}, document, upsert=True)
    return document
