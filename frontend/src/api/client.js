import axios from 'axios';

const BASE_URL = '/api';

// Submit code for visualization.
// Returns a job_id string immediately.
export const submitCode = async (code, language = 'python') => {
  const response = await axios.post(`${BASE_URL}/submit`, {
    code,
    language,
  });
  return response.data.job_id;
};

// Poll the status of a rendering job by its ID.
// Returns an object with: status, video_url, audio_url, steps, error
export const getJobStatus = async (jobId) => {
  const response = await axios.get(`${BASE_URL}/job/${jobId}`);
  return response.data;
};

// Fetch the list of supported programming languages.
export const getSupportedLanguages = async () => {
  const response = await axios.get(`${BASE_URL}/languages`);
  return response.data.languages;
};
