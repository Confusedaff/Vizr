import React, { useRef } from 'react';

function VideoPlayer({ videoUrl, onTimeUpdate }) {
  const videoRef = useRef(null);

  if (!videoUrl) {
    return (
      <div className="player-placeholder">
        <p>Paste code on the left and press Visualize to generate a narrated walkthrough</p>
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
        style={{ display: 'block' }}
      >
        Your browser does not support the video tag.
      </video>
    </div>
  );
}

export default VideoPlayer;
