import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from celery.result import AsyncResult
from celery_worker import celery_app, render_visualization
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Code Visualizer API",
    description="Submit code, get back visualization videos and narration audio",
    version="1.0.0"
)

# Allow the React frontend to call this API.
#
# allow_credentials is False because nothing in this app uses cookies or
# any other credentialed request (there's no auth system at all) — and
# leaving it True alongside a wildcard origin is actually a no-op in
# every real browser anyway: the CORS spec forbids combining
# `Access-Control-Allow-Origin: *` with
# `Access-Control-Allow-Credentials: true`, so a browser will silently
# refuse that combination. Better to make the "no credentials" reality
# explicit than to leave a setting that looks like it's doing something
# it structurally can't.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGINS", "*")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_LANGUAGES = ["python"]   # Add "javascript" later when JS tracer is implemented
MAX_CODE_LENGTH = int(os.getenv("MAX_CODE_LENGTH", 10000))
SUPPORTED_QUALITIES = ["standard", "high"]


class CodeSubmission(BaseModel):
    code: str
    language: str = "python"
    quality: str = "standard"   # "standard" (720p30) or "high" (1080p60, slower)

    @validator("code")
    def code_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("code cannot be empty")
        return v

    @validator("code")
    def code_must_not_be_too_long(cls, v):
        if len(v) > MAX_CODE_LENGTH:
            raise ValueError(f"code exceeds maximum length of {MAX_CODE_LENGTH} characters")
        return v

    @validator("language")
    def language_must_be_supported(cls, v):
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"language '{v}' is not supported. Choose from: {SUPPORTED_LANGUAGES}")
        return v

    @validator("quality")
    def quality_must_be_supported(cls, v):
        if v not in SUPPORTED_QUALITIES:
            raise ValueError(f"quality '{v}' is not supported. Choose from: {SUPPORTED_QUALITIES}")
        return v


@app.get("/api/health")
def health_check():
    """Used by Docker healthcheck and monitoring."""
    return {"status": "ok"}


@app.get("/api/languages")
def get_languages():
    """Return list of supported languages for the frontend dropdown."""
    return {"languages": SUPPORTED_LANGUAGES}


@app.post("/api/submit")
def submit_code(submission: CodeSubmission):
    """
    Accept a code submission, dispatch a Celery job, and immediately
    return a job_id. The frontend will poll /api/job/{job_id} for results.
    """
    job_id = str(uuid.uuid4())

    render_visualization.apply_async(
        args=[submission.code, submission.language, job_id, submission.quality],
        task_id=job_id
    )

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/job/{job_id}")
def get_job_status(job_id: str):
    """
    Poll this endpoint after submitting code.
    Returns: status (queued | processing | complete | error),
             step (only while processing — "tracing" | "narrating" | "rendering"),
             video_url when complete. The video already contains
             narration audio embedded in it — there is no separate
             audio file anymore.
    """
    result = AsyncResult(job_id, app=celery_app)

    if result.state == "SUCCESS":
        return {
            "status": "complete",
            "video_url": f"/media/{job_id}.mp4",
        }

    if result.state == "FAILURE":
        return {
            "status": "error",
            "message": str(result.info) if result.info else "Unknown error",
        }

    # PENDING means the task hasn't been picked up yet; STARTED means it's running.
    # celery_worker.py calls self.update_state(meta={"step": ...}) at each phase
    # (tracing / narrating / rendering) -- surface that here so the frontend can
    # show something more specific than one static "processing" message for
    # however long the render takes.
    if result.state in ("PENDING", "STARTED", "RETRY"):
        step = (result.info or {}).get("step") if isinstance(result.info, dict) else None
        return {"status": "processing", "step": step}

    return {"status": "processing", "step": None}


@app.delete("/api/job/{job_id}")
def cancel_job(job_id: str):
    """
    Cancel a job that's queued or in progress. Best-effort: if the task
    has already finished (or already failed), this just confirms there's
    nothing left to cancel rather than erroring.
    """
    result = AsyncResult(job_id, app=celery_app)

    if result.state in ("SUCCESS", "FAILURE"):
        return {"status": "already_finished"}

    celery_app.control.revoke(job_id, terminate=True)
    return {"status": "cancelled"}
