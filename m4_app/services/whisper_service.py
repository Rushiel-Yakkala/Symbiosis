import os
import logging

logger = logging.getLogger(__name__)

# Cached whisper model instance
_model = None

def get_whisper_model(model_name: str = "small"):
    """
    Lazily loads the Whisper model and caches it in memory.
    The default model name is "base" (approx. 140MB).
    Leverages CUDA GPU if available for acceleration.
    """
    global _model
    if _model is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
        logger.info(f"Loading Whisper model '{model_name}' on device '{device}' (first run will download model weights)...")
        import whisper
        _model = whisper.load_model(model_name, device=device)
        logger.info("Whisper model loaded successfully.")
    return _model

def transcribe_audio(audio_path: str, model_name: str = "small") -> str:
    """
    Transcribes a local audio file using OpenAI Whisper and returns the clean text.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at {audio_path}")
        
    # Get or load cached model
    model = get_whisper_model(model_name)
    
    logger.info(f"Starting Whisper transcription for: {audio_path}")
    result = model.transcribe(audio_path)
    text = result.get("text", "").strip()
    
    logger.info(f"Whisper transcription completed successfully. Characters: {len(text)}")
    return text
