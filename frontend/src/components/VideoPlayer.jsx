import React, { useRef } from 'react';

function VideoPlayer({ videoUrl, onTimeUpdate }) {
  const videoRef = useRef(null);

  if (!videoUrl) {
    return (
      <div className="player-placeholder">
        <p>Visualization will appear here after rendering</p>
      </div>
    );
  }

  return (
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
        style={{ borderRadius: '8px', background: '#000' }}
      >
        Your browser does not support the video tag.
      </video>
    </div>
  );
}

export default VideoPlayer;
