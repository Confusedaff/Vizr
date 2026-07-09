import React from 'react';

const STATUS_MESSAGES = {
  idle:       { text: 'Ready. Paste your code and click Visualize.', color: '#888' },
  submitting: { text: 'Submitting code...', color: '#f0c040' },
  processing: { text: 'Rendering animation. This takes 15–60 seconds...', color: '#f0c040' },
  complete:   { text: 'Done! Press play to watch the visualization.', color: '#4caf50' },
  error:      { text: 'Something went wrong. Check the console for details.', color: '#f44336' },
};

function StatusBar({ status, error }) {
  const info = STATUS_MESSAGES[status] || STATUS_MESSAGES.idle;
  return (
    <div className="status-bar" style={{ borderLeft: `4px solid ${info.color}` }}>
      <div className="status-indicator" style={{ background: info.color }} />
      <span style={{ color: info.color }}>
        {status === 'error' && error ? error : info.text}
      </span>
    </div>
  );
}

export default StatusBar;

