import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from celery import Celery
from dotenv import load_dotenv
load_dotenv()

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery(
    "codevisualizer",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,         # Process one job at a time per worker
    task_soft_time_limit=300,             # Soft kill after 5 minutes
    task_time_limit=360,                  # Hard kill after 6 minutes
)


@celery_app.task(bind=True, name="render_visualization")
def render_visualization(self, code: str, language: str, job_id: str):
    """
    Main Celery task. Orchestrates:
    1. Code tracing
    2. Per-step narration clip generation (TTS)
    3. Manim video rendering, with narration audio embedded directly
       into the same output file via Scene.add_sound()

    NOTE: narration now has to be generated BEFORE rendering, not after —
    the Manim scene needs each clip's file path and duration while it's
    building the animation, so it can attach audio at the right moment
    and hold each frame long enough for that clip to finish playing.
    There is no longer a separate audio file or audio_url; the single
    output .mp4 contains both video and audio.
    """
    from tracer import trace_code
    from manim_renderer import render_scene
    from tts_engine import generate_narration_clips
    from narration_builder import build_narration_lines

    self.update_state(state="STARTED", meta={"step": "tracing"})

    # Step 1: Trace the code execution
    steps = trace_code(code)

    if steps and steps[-1].get("event") == "error":
        raise Exception(steps[-1].get("error", "Tracing failed"))

    self.update_state(state="STARTED", meta={"step": "narrating"})

    # Step 2: Build narration lines tagged with their step index, then
    # generate one short TTS clip per line into a job-scoped temp dir.
    narration_lines = build_narration_lines(steps, code)

    with tempfile.TemporaryDirectory(prefix=f"narration_{job_id}_") as clip_dir:
        texts = [text for _, text in narration_lines]
        clips = generate_narration_clips(texts, job_id, clip_dir)

        # Zip the (step_index, text) pairs back up with their
        # (clip_path, duration) results to build the lookup dict
        # the renderer expects: step_index -> (clip_path, duration).
        # Multiple lines can share a step_index (e.g. a step with both
        # a variable update and a print output) — last one wins, which
        # is an acceptable simplification since add_sound() only takes
        # one clip per call site in the current renderer.
        narration_by_step = {}
        for (step_index, _text), (clip_path, duration) in zip(narration_lines, clips):
            narration_by_step[step_index] = (clip_path, duration)

        self.update_state(state="STARTED", meta={"step": "rendering"})

        # Step 3: Render the Manim animation with narration embedded.
        # This must happen while clip_dir still exists (hence being
        # inside the `with` block) since Scene.add_sound() reads the
        # clip files directly during scene.render().
        render_scene(steps, job_id, narration_by_step=narration_by_step)

    return {"job_id": job_id, "step_count": len(steps)}
