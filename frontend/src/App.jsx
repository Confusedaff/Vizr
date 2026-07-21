import React, { useState, useCallback, useRef, useEffect } from 'react';
import CodeEditor, { DEFAULT_CODE } from './components/CodeEditor';
import VideoPlayer from './components/VideoPlayer';
import StatusBar from './components/StatusBar';
import { submitCode, getJobStatus, cancelJob } from './api/client';

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 60;     // 60 × 3s = 3 minutes max wait -- used only
                                   // as the FALLBACK ceiling when no backend
                                   // ETA is available yet (see pollJob below);
                                   // once an ETA is known, that's used instead
                                   // since it accounts for this specific job's
                                   // size and quality rather than guessing.

// Once a backend ETA is known, give the job this many times the estimate
// before declaring a timeout, rather than the estimate itself -- render
// times are a rolling AVERAGE (render_stats.py), so any individual job
// finishing slower than average is expected some of the time, not a sign
// of a truly stuck job. 2.5x means only a job running well past what
// history would predict gets flagged, while still catching a job that's
// actually hung (e.g. a worker crash Celery hasn't yet reported as FAILURE).
const ETA_TIMEOUT_MULTIPLIER = 2.5;

// Pulls the message out of a FastAPI/pydantic validation error response
// so a rejected submission (e.g. an unsupported language or quality
// value) shows the actual reason instead of a generic "is the backend
// running?" message that wrongly implies the server itself is broken.
// pydantic v2 prefixes custom validator errors with "Value error, ",
// which reads a little oddly in a UI message, so that's trimmed off.
function extractErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail) && detail[0]?.msg) {
    return detail[0].msg.replace(/^Value error,\s*/, '');
  }
  return fallback;
}

function App({ initialCode = '' }) {
  const [code, setCode] = useState(initialCode || DEFAULT_CODE);
  const [language, setLanguage] = useState('python');
  const [quality, setQuality] = useState('standard');
  const [status, setStatus] = useState('idle');
  const [videoUrl, setVideoUrl] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [processingStep, setProcessingStep] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(null);
  const [stepProgress, setStepProgress] = useState(null);   // { stepCount, stepsDone } | null
  const [eta, setEta] = useState(null);                     // { estimatedSeconds, sampleCount } | null
  const pollRef = useRef(null);
  const attemptRef = useRef(0);
  const jobIdRef = useRef(null);
  const etaRef = useRef(null);   // mirrors `eta` state; see pollJob's comment below for why

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // Stop polling if the component unmounts mid-job, so a leftover
  // interval doesn't keep firing (and touching state) after the fact.
  useEffect(() => stopPolling, []);

  const pollJob = useCallback((jobId) => {
    attemptRef.current = 0;
    pollRef.current = setInterval(async () => {
      attemptRef.current += 1;

      // Fallback ceiling (no ETA known yet): MAX_POLL_ATTEMPTS × interval.
      // Once main.py starts returning estimated_seconds for this job,
      // that becomes the real basis for "has this taken too long,"
      // scaled by ETA_TIMEOUT_MULTIPLIER -- see that constant's comment.
      //
      // Reads from etaRef, not the `eta` state variable directly: this
      // setInterval callback is created ONCE per job (pollJob is only
      // called once, from handleVisualize) and then invoked repeatedly
      // on its own timer -- it does not get a fresh closure over `eta`
      // on every tick just because `eta` state changed. Closing over
      // `eta` directly would permanently see whatever `eta` was at the
      // moment this interval was created (always null, since
      // handleVisualize resets it right before calling pollJob), even
      // long after setEta() fires with real data from a later poll.
      // etaRef.current is mutated directly wherever setEta is called,
      // so this callback always reads the latest value despite being
      // a single long-lived closure.
      const fallbackTimeoutMs = MAX_POLL_ATTEMPTS * POLL_INTERVAL_MS;
      const currentEta = etaRef.current;
      const etaTimeoutMs = currentEta ? currentEta.estimatedSeconds * ETA_TIMEOUT_MULTIPLIER * 1000 : null;
      const timeoutMs = etaTimeoutMs !== null ? Math.max(etaTimeoutMs, fallbackTimeoutMs) : fallbackTimeoutMs;
      // Math.max above: an ETA-based timeout should never be SHORTER than
      // the flat fallback would've allowed -- a bucket with a low average
      // (e.g. tiny scripts averaging 8s) shouldn't cut off a legitimate
      // job faster than the old fixed behavior did, only extend patience
      // for jobs that genuinely need more time, never reduce it.

      if (attemptRef.current * POLL_INTERVAL_MS > timeoutMs) {
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
          setStatus('complete');
        } else if (data.status === 'error') {
          stopPolling();
          setStatus('error');
          setErrorMsg(data.message || 'An error occurred during rendering.');
        } else {
          // status === 'processing': celery_worker.py reports which
          // phase it's in (tracing / narrating / rendering) -- surface
          // it so the wait isn't one static message the whole time.
          setProcessingStep(data.step || null);
          setElapsedSeconds(
            typeof data.elapsed_seconds === 'number' ? data.elapsed_seconds : null
          );
          setStepProgress(
            typeof data.step_count === 'number'
              ? { stepCount: data.step_count, stepsDone: data.steps_done || 0 }
              : null
          );
          const newEta = typeof data.estimated_seconds === 'number'
            ? { estimatedSeconds: data.estimated_seconds, sampleCount: data.eta_sample_count }
            : null;
          setEta(newEta);
          etaRef.current = newEta;
        }
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
    setErrorMsg('');
    setProcessingStep(null);
    setElapsedSeconds(null);
    setStepProgress(null);
    setEta(null);
    etaRef.current = null;

    try {
      const jobId = await submitCode(code, language, quality);
      jobIdRef.current = jobId;
      setStatus('processing');
      pollJob(jobId);
    } catch (err) {
      setStatus('error');
      setErrorMsg(extractErrorMessage(err, 'Failed to submit. Is the backend running?'));
    }
  };

  const handleCancel = async () => {
    stopPolling();
    const jobId = jobIdRef.current;
    setStatus('idle');
    setProcessingStep(null);
    setElapsedSeconds(null);
    setStepProgress(null);
    setEta(null);
    etaRef.current = null;
    if (jobId) {
      try {
        await cancelJob(jobId);
      } catch (err) {
        // Best-effort -- the job may already have finished server-side
        // by the time the cancel request lands. Nothing useful to show
        // the person here; the UI has already returned to idle.
      }
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Code Visualizer</h1>
        <p>Paste an algorithm, get a narrated walkthrough</p>
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
              <option value="javascript" disabled>JavaScript (coming soon)</option>
            </select>

            <select
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              className="quality-select"
              title="Higher quality takes longer to render"
            >
              <option value="standard">Standard quality</option>
              <option value="high">High quality (slower)</option>
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
          <StatusBar
            status={status}
            error={errorMsg}
            step={processingStep}
            elapsedSeconds={elapsedSeconds}
            stepProgress={stepProgress}
            eta={eta}
            onCancel={status === 'submitting' || status === 'processing' ? handleCancel : null}
          />
        </div>

        <div className="right-panel">
          <VideoPlayer videoUrl={videoUrl} />
        </div>
      </main>
    </div>
  );
}

export default App;