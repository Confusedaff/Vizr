import os
import logging
import wave
import contextlib
from typing import List, Tuple

MEDIA_PATH = os.getenv("MEDIA_PATH", "/app/media")
logger = logging.getLogger(__name__)

_tts_instance = None

# LJSpeech Tacotron2-DDC is the default — fast, clear, and known to fit
# comfortably inside the Celery task's time budget (see celery_worker.py's
# task_soft_time_limit=300 / task_time_limit=360). It's also a single,
# fairly dated, fairly monotone voice, and generating one WAV per line
# (see generate_narration_clips below) means no cross-sentence prosody,
# so it will sound choppier than continuous narration from a stronger
# model.
#
# ON UPGRADING THIS: Coqui AI (the company behind this project) shut down
# in January 2024. The `TTS` package on PyPI is frozen at its final
# release (0.22.0) and requires Python >=3.9,<3.12 — that's *why*
# Dockerfile.backend is pinned to python:3.11-slim specifically, not just
# a convenient default. Don't bump that base image without checking
# whether whatever TTS-related package is in use at the time still
# supports it.
#
# XTTS v2 (multilingual, voice-cloning capable, noticeably more natural)
# shipped in the original TTS package before the shutdown, so it may
# already be available via this same frozen release just by changing
# TTS_MODEL_NAME below to an XTTS v2 model string — no package swap
# needed. Two things to check before doing that, though, neither of
# which has been validated here: (1) XTTS v2's model weights are
# licensed CPML (nc-only) — confirm that's compatible with your use of
# this app before shipping it; (2) it's a substantially heavier model
# per-clip than Tacotron2-DDC, so load-test actual clip generation time
# against the existing task_soft_time_limit/task_time_limit above before
# changing the default — a model that's simply too slow will start
# failing jobs outright rather than just sounding better.
DEFAULT_MODEL_NAME = "tts_models/en/ljspeech/tacotron2-DDC"
TTS_MODEL_NAME = os.getenv("TTS_MODEL_NAME", DEFAULT_MODEL_NAME)


def _load_tts_model():
    """
    Load the Coqui TTS model once and cache it globally.
    The model is about 100MB and takes ~20s to load the first time.
    Subsequent calls use the cached instance.
    """
    global _tts_instance
    if _tts_instance is None:
        from TTS.api import TTS
        logger.info(f"Loading TTS model '{TTS_MODEL_NAME}' for the first time...")
        _tts_instance = TTS(
            model_name=TTS_MODEL_NAME,
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
