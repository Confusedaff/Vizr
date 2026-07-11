import os
import logging

MEDIA_PATH = os.getenv("MEDIA_PATH", "/app/media")
logger = logging.getLogger(__name__)

_tts_instance = None


def _load_tts_model():
    """
    Load the Coqui TTS model once and cache it globally.
    The model is about 100MB and takes ~20s to load the first time.
    Subsequent calls use the cached instance.
    """
    global _tts_instance
    if _tts_instance is None:
        from TTS.api import TTS
        logger.info("Loading TTS model for the first time...")
        # LJSpeech Tacotron2 — fast, clear, natural-sounding English voice
        _tts_instance = TTS(
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            progress_bar=False
        )
        logger.info("TTS model loaded.")
    return _tts_instance


def generate_narration(script: str, job_id: str):
    """
    Convert a plain-text narration script to an MP3 file.
    Saves to MEDIA_PATH/{job_id}.mp3
    """
    output_path = os.path.join(MEDIA_PATH, f"{job_id}.mp3")

    try:
        tts = _load_tts_model()
        tts.tts_to_file(
            text=script,
            file_path=output_path,
            speaker_wav=None,
        )
        logger.info(f"TTS audio saved to {output_path}")
    except Exception as e:
        # TTS failure is non-fatal — log it but don't abort the whole job
        logger.error(f"TTS generation failed for job {job_id}: {e}")
        # Create a silent placeholder so the frontend doesn't break
        _create_silent_audio(output_path)


def _create_silent_audio(output_path: str, duration_seconds: int = 5):
    """
    Use ffmpeg to generate a short silent MP3 as a fallback.
    This prevents the frontend from erroring if TTS fails.
    """
    import subprocess
    subprocess.run([
        "ffmpeg", "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(duration_seconds),
        "-q:a", "9", "-acodec", "libmp3lame",
        output_path, "-y"
    ], check=True, capture_output=True)