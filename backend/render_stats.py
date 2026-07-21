import json
import logging
from typing import Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = None  # set by init_redis(), called once from celery_worker.py at import time
_redis_client: Optional["redis.Redis"] = None

# Step counts are bucketed on a log-ish scale rather than tracked
# per-exact-count. An exact-count key (e.g. "steps:47") would almost
# never accumulate more than one or two samples -- most submissions
# land on a different step count from each other -- so no bucket would
# ever mature past the "not enough history yet" state. These six
# buckets are wide enough to actually collect repeat samples while
# still being narrow enough that render time within a bucket doesn't
# vary by more than roughly 2-3x end to end.
STEP_BUCKETS = [
    (1, 10, "1-10"),
    (11, 25, "11-25"),
    (26, 50, "26-50"),
    (51, 100, "51-100"),
    (101, 250, "101-250"),
    (251, 500, "251-500"),
]

# A bucket's estimate isn't trusted for showing an ETA until it has
# this many completed samples. Below this, we know too little to claim
# a number -- an ETA computed from a single data point is just that
# one job's incidental render time, dressed up as a prediction.
MIN_SAMPLES_FOR_ESTIMATE = 3

# Rolling average smoothing: newer completions matter more than a job
# from months ago. capping the effective sample count keeps the
# average responsive to recent conditions (e.g. the host machine
# getting busier/quieter, or a manim/quality-mapping change) rather
# than converging to a fixed number that 1000 historical jobs would
# make almost impossible to move.
ROLLING_WINDOW = 20

STATS_KEY_PREFIX = "render_stats"


def init_redis(redis_url: str) -> None:
    """
    Called once from celery_worker.py after it computes BROKER_URL, so
    this module reuses that same connection target rather than each
    module independently reading REDIS_URL/CELERY_BROKER_URL env vars
    and risking them drifting apart.
    """
    global _redis_client, REDIS_URL
    REDIS_URL = redis_url
    _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)


def _client() -> "redis.Redis":
    if _redis_client is None:
        raise RuntimeError(
            "render_stats.init_redis() must be called before use "
            "(celery_worker.py does this at import time)"
        )
    return _redis_client


def _bucket_for(step_count: int) -> str:
    for low, high, label in STEP_BUCKETS:
        if low <= step_count <= high:
            return label
    # Anything above the highest bucket's ceiling (>500) shouldn't
    # actually be reachable -- tracer.py's MAX_STEPS caps step_count at
    # 500 -- but falls back to the top bucket rather than raising, so a
    # future change to MAX_STEPS doesn't turn this into a hard error
    # for what's still a perfectly valid job.
    return STEP_BUCKETS[-1][2]


def _stats_key(quality: str, step_count: int) -> str:
    return f"{STATS_KEY_PREFIX}:{quality}:{_bucket_for(step_count)}"


def record_render_time(quality: str, step_count: int, actual_seconds: float) -> None:
    """
    Called from celery_worker.py after a render completes successfully.
    Updates that bucket's rolling average and sample count, and
    separately tracks the bucket's own running average step_count --
    the latter is what estimate_render_time() scales against, so a
    47-step job in the "26-50" bucket gets a slightly different
    estimate than a 27-step job in that same bucket, rather than both
    reading out the exact same number just for sharing a bucket.

    Best-effort: a Redis write failure here should not fail the job
    that already rendered successfully, so exceptions are caught and
    logged rather than propagated.
    """
    key = _stats_key(quality, step_count)
    try:
        client = _client()
        raw = client.get(key)
        if raw:
            data = json.loads(raw)
            count = data["count"]
            avg_seconds = data["avg_seconds"]
            avg_steps = data["avg_steps"]
        else:
            count, avg_seconds, avg_steps = 0, 0.0, 0.0

        # Standard incremental-average update, but capped at
        # ROLLING_WINDOW effective samples -- see the module docstring
        # comment on ROLLING_WINDOW for why.
        effective_n = min(count + 1, ROLLING_WINDOW)
        avg_seconds += (actual_seconds - avg_seconds) / effective_n
        avg_steps += (step_count - avg_steps) / effective_n

        client.set(key, json.dumps({
            "count": count + 1,
            "avg_seconds": avg_seconds,
            "avg_steps": avg_steps,
        }))
    except Exception as e:
        # Deliberately swallowed: see docstring. Logged so a persistent
        # Redis problem is still visible in worker logs rather than
        # silently degrading every future job's ETA with no trace of why.
        logger.error(f"render_stats: failed to record render time: {e}")


def estimate_render_time(quality: str, step_count: int) -> Optional[dict]:
    """
    Called from main.py when a job is first submitted, to attach an
    initial ETA to the job's status. Returns None if the relevant
    bucket doesn't have enough samples yet (see MIN_SAMPLES_FOR_ESTIMATE)
    -- the caller (main.py) treats None as "don't show a countdown for
    this job," which is the intended behavior for a bucket's first
    couple of jobs rather than showing a number derived from too little
    data.

    Returns {"estimated_seconds": float, "sample_count": int} on success.
    estimated_seconds is scaled by how this job's actual step_count
    compares to the bucket's own running average step count, so jobs
    near a bucket's edges aren't all given the bucket's flat average
    regardless of where in the bucket's range they actually fall.
    """
    key = _stats_key(quality, step_count)
    try:
        client = _client()
        raw = client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        if data["count"] < MIN_SAMPLES_FOR_ESTIMATE:
            return None

        avg_steps = data["avg_steps"]
        avg_seconds = data["avg_seconds"]
        if avg_steps <= 0:
            # Guards a division below; shouldn't be reachable in
            # practice since avg_steps is only ever set from a real
            # completed job's step_count (always >= 1), but a corrupt
            # or hand-edited Redis value shouldn't turn into a 500.
            return {"estimated_seconds": avg_seconds, "sample_count": data["count"]}

        scale = step_count / avg_steps
        return {
            "estimated_seconds": avg_seconds * scale,
            "sample_count": data["count"],
        }
    except Exception as e:
        # Same rationale as record_render_time: a stats lookup failure
        # should degrade to "no ETA shown," not fail job submission.
        logger.error(f"render_stats: failed to estimate render time: {e}")
        return None