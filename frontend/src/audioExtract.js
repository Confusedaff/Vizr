/**
 * Extracts the audio track from a video file entirely client-side and
 * hand-encodes it as a standard WAV file for download.
 *
 * WHY THIS EXISTS: the backend (main.py / celery_worker.py) no longer
 * produces a separate audio file at all -- narration is muxed directly
 * into the rendered .mp4 via Manim's Scene.add_sound() (see
 * celery_worker.py's docstring). There is no audio_url anywhere in the
 * API. Getting a standalone audio file back out has to happen here, on
 * whatever video file the person already has.
 *
 * HOW IT WORKS: AudioContext.decodeAudioData() accepts a complete media
 * file's raw bytes and hands back decoded PCM -- it delegates to the
 * browser's native codec stack (e.g. Chromium's bundled FFmpeg for
 * AAC/mp4), so this works directly on an .mp4 container without this
 * code needing to parse MP4 boxes or demux anything itself. The result
 * is a plain AudioBuffer of decoded samples, which this module then
 * writes into a WAV container by hand -- WAV's header is simple enough
 * (44 bytes, documented below) that no encoding library is needed, and
 * critically there's no browser API to ENCODE compressed formats
 * (MP3/AAC) from arbitrary PCM in the first place, so an uncompressed
 * format is the only one actually reachable without a WASM dependency.
 * That's a reasonable trade here anyway: the stated goal is analyzing
 * the narration for errors, and uncompressed audio is the more useful
 * artifact for that, not a compromise made because compression wasn't
 * available.
 *
 * SAMPLE RATE: never assumed. decodeAudioData resamples to whatever
 * rate the browser's AudioContext ends up using, which varies by
 * device (44100/48000/32000 Hz have all been observed across
 * browsers), and there's no way to know it in advance -- only after
 * decoding. The real buffer.sampleRate is always what gets written
 * into the WAV header; hardcoding 44100 (or any other value) would
 * make the file play back at the wrong speed/pitch on a browser that
 * decoded at a different rate.
 */

/**
 * Fetches a video URL, decodes its audio track, and returns a WAV Blob.
 * Throws with a descriptive message on failure rather than returning
 * null, so the caller (VideoPlayer.jsx) can show the actual reason
 * (network failure vs. decode failure) instead of one generic error.
 *
 * @param {string} videoUrl - same URL already used as the <video> src
 * @returns {Promise<Blob>} a Blob of type 'audio/wav'
 */
export async function extractAudioAsWav(videoUrl) {
  let response;
  try {
    response = await fetch(videoUrl);
  } catch (e) {
    throw new Error('Could not download the video to extract audio from. Check your connection and try again.');
  }

  if (!response.ok) {
    throw new Error(`Could not download the video (server returned ${response.status}).`);
  }

  const arrayBuffer = await response.arrayBuffer();

  // Safari historically requires the webkit-prefixed constructor; both
  // are checked since this runs in whatever browser the person has,
  // not a controlled environment. AudioContext (not OfflineAudioContext)
  // is deliberate here -- decodeAudioData is a method on the shared
  // BaseAudioContext interface, and creating a full AudioContext just
  // to call decodeAudioData once is the standard, documented pattern;
  // it's closed immediately after (see finally below) so it never
  // actually reaches the speakers or holds hardware audio resources
  // open.
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    throw new Error('This browser does not support audio decoding, so audio can\'t be extracted here.');
  }

  const audioCtx = new AudioContextClass();
  let audioBuffer;
  try {
    audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
  } catch (e) {
    // decodeAudioData rejects (rather than resolving with null) on
    // malformed data or an unsupported codec in this browser -- give a
    // specific, actionable message rather than a raw DOMException,
    // since "EncodingError" alone means nothing to someone downloading
    // narration audio.
    throw new Error('Could not decode the audio track from this video. The file may be corrupted, or this browser may not support its audio codec.');
  } finally {
    // Always release the AudioContext's resources, whether decode
    // succeeded or failed -- an AudioContext left open holds onto
    // browser audio-processing resources indefinitely, and the person
    // may extract audio from several jobs in one session.
    audioCtx.close().catch(() => {
      // close() can itself reject (e.g. if already closed) -- nothing
      // actionable to do about that, and it must never mask whatever
      // the real result of decodeAudioData was above.
    });
  }

  return audioBufferToWavBlob(audioBuffer);
}

/**
 * Encodes a decoded AudioBuffer as 16-bit PCM WAV bytes and wraps them
 * in a Blob. Handles any channel count (mono narration clips or a
 * stereo mix, whichever the TTS/render pipeline actually produced) by
 * reading numberOfChannels off the real buffer rather than assuming.
 *
 * WAV FORMAT: a 44-byte header (RIFF chunk descriptor + fmt subchunk +
 * data subchunk header) followed by raw interleaved 16-bit PCM sample
 * data. This is the minimal, standard, universally-readable WAV
 * layout -- every field written below is required by the format, none
 * are optional extensions.
 */
function audioBufferToWavBlob(audioBuffer) {
  const numChannels = audioBuffer.numberOfChannels;
  const sampleRate = audioBuffer.sampleRate;   // the REAL rate the browser decoded at -- see module docstring
  const numFrames = audioBuffer.length;
  const bytesPerSample = 2;                    // 16-bit PCM
  const blockAlign = numChannels * bytesPerSample;
  const dataSize = numFrames * blockAlign;
  const headerSize = 44;

  const buffer = new ArrayBuffer(headerSize + dataSize);
  const view = new DataView(buffer);

  function writeString(offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  // --- RIFF chunk descriptor ---
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);        // ChunkSize: 4 + (8+fmtSize) + (8+dataSize), fmtSize=16
  writeString(8, 'WAVE');

  // --- fmt subchunk ---
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);                  // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true);                   // AudioFormat: 1 = Linear PCM (uncompressed) -- required for
                                                  // browser <audio> playback; ADPCM/other WAV codecs won't play
                                                  // natively (confirmed during research), which is exactly why
                                                  // this writes Linear PCM directly rather than any other WAV variant
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);  // ByteRate
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bytesPerSample * 8, true);   // BitsPerSample

  // --- data subchunk ---
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  // --- interleaved 16-bit PCM sample data ---
  // AudioBuffer stores each channel as a separate Float32Array in the
  // range [-1, 1] (getChannelData(ch)); WAV needs channels interleaved
  // sample-by-sample (L,R,L,R,... for stereo) and converted to 16-bit
  // signed integers.
  const channelData = [];
  for (let ch = 0; ch < numChannels; ch++) {
    channelData.push(audioBuffer.getChannelData(ch));
  }

  let offset = headerSize;
  for (let frame = 0; frame < numFrames; frame++) {
    for (let ch = 0; ch < numChannels; ch++) {
      // Clamp before scaling: decoded float samples can occasionally
      // exceed [-1, 1] slightly (e.g. from lossy-codec decode
      // artifacts or upstream clipping), and an unclamped value here
      // would wrap around instead of clipping, producing a loud
      // digital pop in the output rather than a clean clip at full
      // volume.
      const clamped = Math.max(-1, Math.min(1, channelData[ch][frame]));
      const intSample = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      view.setInt16(offset, intSample, true);
      offset += bytesPerSample;
    }
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

/**
 * Triggers a browser download of a Blob with the given filename.
 * Standard object-URL-and-synthetic-click pattern; the object URL is
 * revoked after the click is dispatched so it doesn't leak memory if
 * the person extracts audio from multiple jobs in one session.
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoking synchronously (rather than after a timeout) is safe here:
  // the click() call above is synchronous and the browser has already
  // initiated the download/navigation before this line runs, so the
  // object URL has already served its purpose by the time it's revoked.
  URL.revokeObjectURL(url);
}
