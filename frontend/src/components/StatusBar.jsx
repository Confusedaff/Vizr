import React from 'react';

const STATUS_MESSAGES = {
  idle:       { text: 'Ready. Paste your code and click Visualize.', color: 'var(--text-tertiary)', active: false },
  submitting: { text: 'Submitting code…', color: 'var(--accent)', active: true },
  processing: { text: 'Rendering animation. This takes 15–60 seconds…', color: 'var(--accent)', active: true },
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

function StatusBar({ status, error, step, onCancel }) {
  const info = STATUS_MESSAGES[status] || STATUS_MESSAGES.idle;
  const text =
    status === 'error' && error
      ? error
      : status === 'processing' && step && STEP_MESSAGES[step]
      ? STEP_MESSAGES[step]
      : info.text;

  const showCancel = (status === 'submitting' || status === 'processing') && !!onCancel;

  return (
    <div className="status-bar" style={{ borderLeft: `3px solid ${info.color}` }}>
      <div
        className={`status-indicator${info.active ? ' pulse' : ''}`}
        style={{ background: info.color, color: info.color }}
      />
      <span style={{ color: info.color }}>{text}</span>
      {showCancel && (
        <button type="button" className="status-cancel-btn" onClick={onCancel}>
          Cancel
        </button>
      )}
    </div>
  );
}

export default StatusBar;
