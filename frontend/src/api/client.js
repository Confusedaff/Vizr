import axios from 'axios';

const BASE_URL = '/api';

// Submit code for visualization.
// quality: "standard" (720p30, default) or "high" (1080p60, slower).
// Returns a job_id string immediately.
export const submitCode = async (code, language = 'python', quality = 'standard') => {
  const response = await axios.post(`${BASE_URL}/submit`, {
    code,
    language,
    quality,
  });
  return response.data.job_id;
};

// Poll the status of a rendering job by its ID.
// Returns an object with: status ("queued" | "processing" | "complete" | "error"),
// step (only meaningful while processing: "tracing" | "narrating" | "rendering" | null),
// video_url (only once complete -- narration is embedded directly in this
// video, there is no separate audio_url), message (only on error).
//
// While processing, may also include:
//   elapsed_seconds     — wall-clock time since the job actually started
//                          (server-anchored, not client-clock-based, so
//                          a missed poll or a slow one doesn't skew it)
//   step_count / steps_done — only present once rendering has begun;
//                          tracing must finish first since step_count
//                          comes from the real trace
//   estimated_seconds / eta_sample_count — a predicted total duration
//                          from the backend's render_stats history.
//                          Absent when there isn't yet enough history
//                          for this quality/step-count combination --
//                          absence means "no countdown yet," not zero.
export const getJobStatus = async (jobId) => {
  const response = await axios.get(`${BASE_URL}/job/${jobId}`);
  return response.data;
};

// Cancel a queued or in-progress job.
export const cancelJob = async (jobId) => {
  const response = await axios.delete(`${BASE_URL}/job/${jobId}`);
  return response.data;
};

// Fetch the list of supported programming languages.
export const getSupportedLanguages = async () => {
  const response = await axios.get(`${BASE_URL}/languages`);
  return response.data.languages;
};