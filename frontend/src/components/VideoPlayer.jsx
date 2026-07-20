import React, { useRef, useState } from 'react';

const PLAYBACK_SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

function VideoPlayer({ videoUrl, onTimeUpdate }) {
  const videoRef = useRef(null);
  const [speed, setSpeed] = useState(1);

  const handleSpeedChange = (e) => {
    const value = Number(e.target.value);
    setSpeed(value);
    if (videoRef.current) {
      videoRef.current.playbackRate = value;
    }
  };

  if (!videoUrl) {
    return (
      <div className="player-placeholder">
        <p>Paste code on the left and press Visualize to generate a narrated walkthrough</p>
      </div>
    );
  }

  return (
    <div className="player-loaded">
      <div className="video-container">
        <video
          ref={videoRef}
          controls
          width="100%"
          src={videoUrl}
          onTimeUpdate={() => {
            if (onTimeUpdate && videoRef.current) {
              onTimeUpdate(videoRef.current.currentTime);
            }
          }}
          style={{ display: 'block' }}
        >
          Your browser does not support the video tag.
        </video>
      </div>
      <div className="playback-controls">
        <label htmlFor="playback-speed" className="playback-speed-label">
          Speed
        </label>
        <select
          id="playback-speed"
          className="playback-speed-select"
          value={speed}
          onChange={handleSpeedChange}
        >
          {PLAYBACK_SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default VideoPlayer;