import os
import sys
import tempfile
import shutil
import time

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

# render_stats shares this worker's own broker connection rather than
# reading CELERY_BROKER_URL a second time independently, so the two
# can't end up pointed at different Redis instances if only one of the
# two env vars ever gets updated in a deployment.
import render_stats
render_stats.init_redis(BROKER_URL)

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


# Minimum wall-clock gap between progress-triggered update_state() calls
# during rendering. Without this, a fast standard-quality render of a
# short trace could fire dozens of Redis writes within a couple of
# seconds (one per animated step) for a number the frontend only polls
# every POLL_INTERVAL_MS=3000ms anyway (see App.jsx) -- those extra
# writes cost Redis traffic and worker CPU without ever being visible
# to anyone polling at that interval.
PROGRESS_UPDATE_MIN_INTERVAL_SECONDS = 1.0


@celery_app.task(bind=True, name="render_visualization")
def render_visualization(self, code: str, language: str, job_id: str, quality: str = "standard"):
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

    quality: "standard" (720p30, default) or "high" (1080p60, slower).
    See manim_renderer.QUALITY_MAP.

    TIMING / ETA: this task records its own total wall-clock duration
    (tracing + narrating + rendering combined, not just the render call)
    to render_stats on successful completion. That total is what
    main.py's estimate_render_time() call is predicting for FUTURE jobs
    at submission time, so what's recorded here has to match what's
    being predicted there -- if only the render_scene() portion were
    timed, the resulting estimate would systematically undercount the
    tracing/narrating time that a person is actually waiting through.
    """
    from tracer import trace_code
    from manim_renderer import render_scene
    from tts_engine import generate_narration_clips
    from narration_builder import build_narration_lines

    task_start = time.monotonic()
    # Separate wall-clock timestamp (not the monotonic clock used for
    # the actual duration measurement above) purely so main.py -- a
    # different process, which can't see this worker's monotonic clock
    # -- can compute "how long has this job been running" for display.
    # Included in every update_state call below so it's available on
    # main.py's very first poll, not just once rendering begins.
    task_start_wall = time.time()

    self.update_state(state="STARTED", meta={
        "step": "tracing", "task_start": task_start_wall, "quality": quality,
    })

    # Step 1: Trace the code execution
    steps = trace_code(code)

    if steps and steps[-1].get("event") == "error":
        raise Exception(steps[-1].get("error", "Tracing failed"))

    self.update_state(state="STARTED", meta={
        "step": "narrating", "task_start": task_start_wall, "quality": quality,
    })

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

        self.update_state(state="STARTED", meta={
            "step": "rendering",
            "step_count": len(steps),
            "steps_done": 0,
            "task_start": task_start_wall,
            "quality": quality,
        })

        # Throttled progress callback passed into the renderer. Called
        # once per animated step from AlgorithmScene.construct(); only
        # actually writes to the result backend at most once per
        # PROGRESS_UPDATE_MIN_INTERVAL_SECONDS -- see that constant's
        # comment. Uses a mutable single-element list (not a bare
        # closured float) as the standard Python pattern for a nested
        # function to update a variable owned by its enclosing scope.
        last_update = [task_start]

        def on_step_progress(steps_done: int, step_count: int) -> None:
            now = time.monotonic()
            if now - last_update[0] < PROGRESS_UPDATE_MIN_INTERVAL_SECONDS:
                return
            last_update[0] = now
            self.update_state(state="STARTED", meta={
                "step": "rendering",
                "step_count": step_count,
                "steps_done": steps_done,
                "task_start": task_start_wall,
                "quality": quality,
            })

        # Step 3: Render the Manim animation with narration embedded.
        # This must happen while clip_dir still exists (hence being
        # inside the `with` block) since Scene.add_sound() reads the
        # clip files directly during scene.render().
        render_scene(
            steps, job_id, code=code, narration_by_step=narration_by_step,
            quality=quality, on_progress=on_step_progress,
        )

    total_seconds = time.monotonic() - task_start
    render_stats.record_render_time(quality, len(steps), total_seconds)

    return {"job_id": job_id, "step_count": len(steps)}