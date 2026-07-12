import os
import logging
import wave
import contextlib
from typing import List, Tuple

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


def generate_narration_clips(lines: List[str], job_id: str, clip_dir: str) -> List[Tuple[str, float]]:
    """
    Generate one short audio clip per narration line, instead of a single
    file for the whole script. This lets the Manim renderer attach each
    clip to the exact animation beat it describes via Scene.add_sound(),
    so audio and video share one timeline and can't drift apart the way
    a single pre-generated narration track could against animations of
    a different total length.

    NOTE ON COST: this trades one TTS inference call for N calls (one per
    line). The model itself is only loaded once (cached in _tts_instance),
    so this doesn't re-pay the ~20s model load per clip — only the actual
    text-to-speech inference is repeated, which is proportional to text
    length either way. For a typical trace (10-20 narrated lines), this is
    still comfortably within the Celery task's time limits, but it is
    slower in aggregate than one big call due to per-call overhead.

    Returns a list of (clip_path, duration_seconds) tuples, one per input
    line, in the same order as `lines`. If a given line fails to render,
    its tuple is (silent_clip_path, duration_seconds) using a short
    silent placeholder so the caller's timeline math doesn't break.
    """
    os.makedirs(clip_dir, exist_ok=True)
    results: List[Tuple[str, float]] = []

    try:
        tts = _load_tts_model()
    except Exception as e:
        logger.error(f"Could not load TTS model for job {job_id}: {e}")
        tts = None

    for i, line in enumerate(lines):
        clip_path = os.path.join(clip_dir, f"line_{i:03d}.wav")

        if tts is not None and line.strip():
            try:
                tts.tts_to_file(text=line, file_path=clip_path, speaker_wav=None)
            except Exception as e:
                logger.error(f"TTS failed on line {i} of job {job_id}: {e}")
                _create_silent_clip(clip_path, duration_seconds=1.5)
        else:
            _create_silent_clip(clip_path, duration_seconds=1.5)

        duration = _get_wav_duration(clip_path)
        results.append((clip_path, duration))

    return results


def _get_wav_duration(wav_path: str) -> float:
    """Read a WAV file's duration in seconds without needing ffprobe."""
    try:
        with contextlib.closing(wave.open(wav_path, "rb")) as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate) if rate else 1.5
    except Exception as e:
        logger.error(f"Could not read duration of {wav_path}: {e}")
        return 1.5   # Safe fallback so timeline math still proceeds


def _create_silent_clip(output_path: str, duration_seconds: float = 1.5):
    """
    Use ffmpeg to generate a short silent WAV as a fallback.
    Keeps the same duration-based timing contract as a real TTS clip,
    so a failed line just plays silently instead of breaking sync.
    """
    import subprocess
    subprocess.run([
        "ffmpeg", "-f", "lavfi",
        "-i", "anullsrc=channel_layout=mono:sample_rate=22050",
        "-t", str(duration_seconds),
        output_path, "-y"
    ], check=True, capture_output=True)
