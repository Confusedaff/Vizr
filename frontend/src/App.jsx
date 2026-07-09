import React, { useState, useCallback, useRef } from 'react';
import CodeEditor from './components/CodeEditor';
import VideoPlayer from './components/VideoPlayer';
import AudioNarration from './components/AudioNarration';
import StatusBar from './components/StatusBar';
import { submitCode, getJobStatus } from './api/client';

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 60;     // 60 × 3s = 3 minutes max wait

function App() {
  const [code, setCode] = useState('');
  const [language, setLanguage] = useState('python');
  const [status, setStatus] = useState('idle');
  const [videoUrl, setVideoUrl] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [videoTime, setVideoTime] = useState(0);
  const pollRef = useRef(null);
  const attemptRef = useRef(0);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const pollJob = useCallback((jobId) => {
    attemptRef.current = 0;
    pollRef.current = setInterval(async () => {
      attemptRef.current += 1;

      if (attemptRef.current > MAX_POLL_ATTEMPTS) {
        stopPolling();
        setStatus('error');
        setErrorMsg('Rendering timed out. The server may be under load — try again.');
        return;
      }

      try {
        const data = await getJobStatus(jobId);
        if (data.status === 'complete') {
          stopPolling();
          setVideoUrl(data.video_url);
          setAudioUrl(data.audio_url);
          setStatus('complete');
        } else if (data.status === 'error') {
          stopPolling();
          setStatus('error');
          setErrorMsg(data.message || 'An error occurred during rendering.');
        }
        // If status is 'processing', just wait and poll again
      } catch (err) {
        stopPolling();
        setStatus('error');
        setErrorMsg('Could not reach the server. Is it running?');
      }
    }, POLL_INTERVAL_MS);
  }, []);

  const handleVisualize = async () => {
    if (!code.trim()) {
      setErrorMsg('Please enter some code first.');
      setStatus('error');
      return;
    }

    stopPolling();
    setStatus('submitting');
    setVideoUrl(null);
    setAudioUrl(null);
    setErrorMsg('');

    try {
      const jobId = await submitCode(code, language);
      setStatus('processing');
      pollJob(jobId);
    } catch (err) {
      setStatus('error');
      setErrorMsg('Failed to submit. Is the backend running?');
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Code Visualizer</h1>
        <p>Paste an algorithm, watch it animate step by step</p>
      </header>

      <main className="app-main">
        <div className="left-panel">
          <div className="controls-row">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="lang-select"
            >
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
            </select>

            <button
              className="visualize-btn"
              onClick={handleVisualize}
              disabled={status === 'submitting' || status === 'processing'}
            >
              {status === 'processing' ? 'Rendering…' : '▶ Visualize'}
            </button>
          </div>

          <CodeEditor code={code} setCode={setCode} language={language} />
          <StatusBar status={status} error={errorMsg} />
        </div>

        <div className="right-panel">
          <VideoPlayer videoUrl={videoUrl} onTimeUpdate={setVideoTime} />
          <AudioNarration audioUrl={audioUrl} currentTime={videoTime} />
        </div>
      </main>
    </div>
  );
}

export default App;
