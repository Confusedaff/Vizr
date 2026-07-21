import React, { useState, useEffect, useRef } from 'react';

const STATUS_MESSAGES = {
  idle:       { text: 'Ready. Paste your code and click Visualize.', color: 'var(--text-tertiary)', active: false },
  submitting: { text: 'Submitting code…', color: 'var(--accent)', active: true },
  processing: { text: 'Rendering animation…', color: 'var(--accent)', active: true },
  complete:   { text: 'Done! Press play to watch the visualization.', color: 'var(--success)', active: false },
  error:      { text: 'Something went wrong.', color: 'var(--danger)', active: false },
};

// celery_worker.py reports one of these while a job is processing (see
// main.py's /api/job/{job_id}). Falls back to STATUS_MESSAGES.processing's
// generic text if step is missing or unrecognized, rather than showing
// nothing -- the backend genuinely doesn't have a step to report yet in
// the brief window right after a job is queued.
const STEP_MESSAGES = {
  tracing: 'Tracing your code…',
  narrating: 'Generating narration…',
  rendering: 'Rendering animation…',
};

// Rough relative weight of each phase, used ONLY as a progress-bar
// fallback for the tracing/narrating phases, which have no real
// step-by-step counter the way rendering does (see stepProgress prop).
// Tracing and narrating are both typically fast relative to rendering
// -- tracing is a single Python exec() pass, narrating is a handful of
// short TTS calls -- so they're weighted as small fixed slivers of the
// bar rather than attempting to estimate their own internal progress.
// Once rendering begins, the bar switches entirely to real
// stepsDone/stepCount data and these weights no longer apply.
const PHASE_FLOOR = {
  tracing: 0.03,
  narrating: 0.08,
  rendering: 0.12,   // rendering's OWN floor before any steps have completed yet
};

function formatSeconds(totalSeconds) {
  const s = Math.max(0, Math.round(totalSeconds));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m > 0 ? `${m}:${String(rem).padStart(2, '0')}` : `${rem}s`;
}

/**
 * Local ticking clock so the countdown updates every second between
 * poll responses, rather than only jumping every POLL_INTERVAL_MS
 * (3s) when App.jsx's interval actually lands. elapsedSeconds/eta come
 * from the server (see App.jsx/client.js); this hook just interpolates
 * a smooth per-second display between those server-anchored updates,
 * and resets its own baseline every time a fresh elapsedSeconds
 * arrives so it can't drift far from the server's number over a long
 * job.
 */
function useTickingElapsed(serverElapsedSeconds) {
  const [displaySeconds, setDisplaySeconds] = useState(serverElapsedSeconds);
  const baselineRef = useRef({ server: serverElapsedSeconds, wallClock: Date.now() });

  useEffect(() => {
    if (typeof serverElapsedSeconds === 'number') {
      baselineRef.current = { server: serverElapsedSeconds, wallClock: Date.now() };
      setDisplaySeconds(serverElapsedSeconds);
    }
  }, [serverElapsedSeconds]);

  useEffect(() => {
    if (typeof serverElapsedSeconds !== 'number') return undefined;
    const id = setInterval(() => {
      const { server, wallClock } = baselineRef.current;
      setDisplaySeconds(server + (Date.now() - wallClock) / 1000);
    }, 1000);
    return () => clearInterval(id);
  }, [serverElapsedSeconds]);

  return displaySeconds;
}

function StatusBar({ status, error, step, elapsedSeconds, stepProgress, eta, onCancel }) {
  const info = STATUS_MESSAGES[status] || STATUS_MESSAGES.idle;
  const tickingElapsed = useTickingElapsed(status === 'processing' ? elapsedSeconds : null);

  const text =
    status === 'error' && error
      ? error
      : status === 'processing' && step && STEP_MESSAGES[step]
      ? STEP_MESSAGES[step]
      : info.text;

  const showCancel = (status === 'submitting' || status === 'processing') && !!onCancel;
  const showProgress = status === 'processing' && (step === 'tracing' || step === 'narrating' || step === 'rendering');

  // Progress bar fraction (0-1). Real step counts (stepProgress) are
  // ground truth once rendering has begun -- they come directly from
  // AlgorithmScene's construct() loop via celery_worker.py's throttled
  // progress callback, not a guess -- so they take priority whenever
  // present. Before that (tracing/narrating, or rendering's first
  // moments before any step has completed) there's nothing like that
  // to read, so PHASE_FLOOR gives a small fixed sliver just to show
  // that something is happening, rather than a bar frozen at 0%.
  let progressFraction;
  if (stepProgress && stepProgress.stepCount > 0) {
    // Rendering has its own floor (PHASE_FLOOR.rendering) blended in as
    // a minimum, so the bar visibly jumps forward the instant rendering
    // starts (coming from tracing/narrating's much smaller floors)
    // rather than sitting at 0% until the first throttled progress
    // update arrives, which per celery_worker.py's
    // PROGRESS_UPDATE_MIN_INTERVAL_SECONDS could be close to a second in.
    const stepFraction = stepProgress.stepsDone / stepProgress.stepCount;
    progressFraction = PHASE_FLOOR.rendering + stepFraction * (1 - PHASE_FLOOR.rendering);
  } else if (step && PHASE_FLOOR[step] !== undefined) {
    progressFraction = PHASE_FLOOR[step];
  } else {
    progressFraction = 0;
  }

  // Countdown text: elapsed vs. estimated, both server-anchored (see
  // useTickingElapsed). Once elapsed exceeds the estimate, this
  // deliberately does NOT clamp at "0s remaining" or hide the
  // countdown -- either of those reads as broken/frozen to someone
  // watching a real timer. Instead it switches to counting UP past the
  // estimate with an explicit note, which is still an honest signal
  // ("this is taking longer than the typical case") rather than a
  // silently wrong or frozen number.
  let etaText = null;
  if (eta && typeof tickingElapsed === 'number') {
    const remaining = eta.estimatedSeconds - tickingElapsed;
    if (remaining > 0) {
      etaText = `~${formatSeconds(remaining)} remaining`;
    } else {
      etaText = `taking longer than usual (${formatSeconds(tickingElapsed)} so far)`;
    }
  } else if (typeof tickingElapsed === 'number') {
    // No ETA yet (bucket doesn't have MIN_SAMPLES_FOR_ESTIMATE completed
    // jobs -- see render_stats.py) but elapsed time is still known and
    // still worth showing, just without a projected total.
    etaText = `${formatSeconds(tickingElapsed)} elapsed`;
  }

  return (
    <div className="status-bar-container">
      <div className="status-bar" style={{ borderLeft: `3px solid ${info.color}` }}>
        <div
          className={`status-indicator${info.active ? ' pulse' : ''}`}
          style={{ background: info.color, color: info.color }}
        />
        <span style={{ color: info.color }}>{text}</span>
        {etaText && <span className="status-eta">{etaText}</span>}
        {showCancel && (
          <button type="button" className="status-cancel-btn" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
      {showProgress && (
        <div className="status-progress-track" role="progressbar" aria-valuenow={Math.round(progressFraction * 100)} aria-valuemin={0} aria-valuemax={100}>
          <div className="status-progress-fill" style={{ width: `${Math.min(100, progressFraction * 100)}%` }} />
        </div>
      )}
      {stepProgress && step === 'rendering' && (
        <div className="status-step-count">
          Step {stepProgress.stepsDone} of {stepProgress.stepCount}
          {eta && eta.sampleCount < 10 && (
            <span className="status-eta-caveat"> · estimate based on {eta.sampleCount} past render{eta.sampleCount === 1 ? '' : 's'}</span>
          )}
        </div>
      )}
    </div>
  );
}

export default StatusBar;
