import React, { useRef, useEffect } from 'react';

function AudioNarration({ audioUrl, currentTime }) {
  const audioRef = useRef(null);

  // Sync audio playback position to the video's current time
  useEffect(() => {
    if (audioRef.current && currentTime !== undefined) {
      const diff = Math.abs(audioRef.current.currentTime - currentTime);
      if (diff > 0.5) {
        audioRef.current.currentTime = currentTime;
      }
    }
  }, [currentTime]);

  if (!audioUrl) return null;

  return (
    <div className="audio-container">
      <label className="audio-label">
        🔊 Audio Narration
      </label>
      <audio
        ref={audioRef}
        controls
        src={audioUrl}
        style={{ width: '100%', marginTop: '8px' }}
      >
        Your browser does not support the audio element.
      </audio>
    </div>
  );
}

export default AudioNarration;
