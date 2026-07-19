import React from 'react';

const STATUS_MESSAGES = {
  idle:       { text: 'Ready. Paste your code and click Visualize.', color: 'var(--text-tertiary)', active: false },
  submitting: { text: 'Submitting code…', color: 'var(--accent)', active: true },
  processing: { text: 'Rendering animation. This takes 15–60 seconds…', color: 'var(--accent)', active: true },
  complete:   { text: 'Done! Press play to watch the visualization.', color: 'var(--success)', active: false },
  error:      { text: 'Something went wrong. Check the console for details.', color: 'var(--danger)', active: false },
};

function StatusBar({ status, error }) {
  const info = STATUS_MESSAGES[status] || STATUS_MESSAGES.idle;
  return (
    <div className="status-bar" style={{ borderLeft: `3px solid ${info.color}` }}>
      <div
        className={`status-indicator${info.active ? ' pulse' : ''}`}
        style={{ background: info.color, color: info.color }}
      />
      <span style={{ color: info.color }}>
        {status === 'error' && error ? error : info.text}
      </span>
    </div>
  );
}

export default StatusBar;

