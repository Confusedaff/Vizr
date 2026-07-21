import React, { useRef, useState } from 'react';
import { extractAudioAsWav, downloadBlob } from '../audioExtract';

const PLAYBACK_SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

// Extraction states, tracked separately from the video's own load state
// -- 'idle' | 'extracting' | 'error'. Deliberately NOT storing a
// 'success' state that lingers: once the download actually fires (see
// handleDownloadAudio), there's nothing further to show -- the
// browser's own download UI takes over from there, so this resets
// straight back to 'idle' rather than showing a stale "downloaded!"
// checkmark that would be wrong the next time the person clicks it for
// a re-download.
function AudioDownloadButton({ videoUrl }) {
  const [state, setState] = useState('idle');   // 'idle' | 'extracting' | 'error'
  const [errorMsg, setErrorMsg] = useState('');

  const handleDownloadAudio = async () => {
    setState('extracting');
    setErrorMsg('');
    try {
      const wavBlob = await extractAudioAsWav(videoUrl);
      // Filename derived from the video's own job-id-based name (e.g.
      // "/media/<uuid>.mp4") rather than a generic "audio.wav", so
      // multiple downloads across different jobs in the same browser
      // session don't silently overwrite each other in the Downloads
      // folder.
      const jobId = videoUrl.split('/').pop()?.replace(/\.mp4$/, '') || 'narration';
      downloadBlob(wavBlob, `${jobId}-audio.wav`);
      setState('idle');
    } catch (err) {
      setState('error');
      setErrorMsg(err.message || 'Could not extract audio from this video.');
    }
  };

  return (
    <div className="audio-download">
      <button
        type="button"
        className="audio-download-btn"
        onClick={handleDownloadAudio}
        disabled={state === 'extracting'}
        title="Extract and download the narration audio as a WAV file"
      >
        {/* No JSX fragment wrapper (<>...</>) anywhere in this button --
            a <button> already accepts multiple sibling children
            directly, so the icon/spinner and the label are just two
            separate conditional expressions in sequence rather than
            grouped under a fragment shorthand. This sidesteps a
            Fragment/JSX-transform interaction that was failing to
            compile under react-scripts in one environment (exact root
            cause not reproducible in isolation), without needing a
            React.Fragment import or any transform-config change. */}
        {state === 'extracting' ? (
          <span className="audio-download-spinner" aria-hidden="true" />
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        {state === 'extracting' ? 'Extracting audio…' : 'Download audio'}
      </button>
      {state === 'error' && (
        <span className="audio-download-error" role="alert">{errorMsg}</span>
      )}
    </div>
  );
}

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
        {/* Narration audio is embedded directly in the video file (see
            celery_worker.py/tts_engine.py) -- there's no separate
            audio_url from the backend at all. This button extracts it
            client-side (audioExtract.js) purely so it can be pulled out
            as a standalone file for analysis, e.g. checking the TTS
            output for mispronunciations without needing to also
            re-watch the animation. */}
        <AudioDownloadButton videoUrl={videoUrl} />
      </div>
    </div>
  );
}

export default VideoPlayer;
