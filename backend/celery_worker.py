import os
import sys

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
    2. Manim video rendering
    3. TTS audio generation
    """
    from tracer import trace_code
    from manim_renderer import render_scene
    from tts_engine import generate_narration
    from narration_builder import build_narration_script

    self.update_state(state="STARTED", meta={"step": "tracing"})

    # Step 1: Trace the code execution
    steps = trace_code(code)

    if steps and steps[-1].get("event") == "error":
        raise Exception(steps[-1].get("error", "Tracing failed"))

    self.update_state(state="STARTED", meta={"step": "rendering"})

    # Step 2: Render the Manim animation
    render_scene(steps, job_id)

    self.update_state(state="STARTED", meta={"step": "narrating"})

    # Step 3: Build and render TTS narration
    script = build_narration_script(steps, code)
    generate_narration(script, job_id)

    return {"job_id": job_id, "step_count": len(steps)}