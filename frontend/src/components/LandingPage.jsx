import React, { useState } from 'react';
import { EXAMPLES } from '../exampleCode';

function LandingPage({ onLaunch }) {
  const [prompt, setPrompt] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onLaunch(prompt.trim());
  };

  return (
    <div className="landing">
      <nav className="landing-nav">
        <span className="landing-logo">
          <span className="landing-logo-dot" />
          Code Visualizer
        </span>
        <div className="landing-nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#footer-cta">Get started</a>
        </div>
        <button className="landing-nav-cta" onClick={() => onLaunch()}>
          Open the editor
        </button>
      </nav>

      <header className="landing-hero">
        <h1 className="landing-hero-title">
          Paste code. <span className="dim">Get a narrated video.</span>
        </h1>
        <p className="landing-hero-sub">
          Drop in an algorithm and Code Visualizer renders a step-by-step walkthrough
          with voice narration — no manual animation, no screen recording.
        </p>

        <form className="landing-prompt-bar" onSubmit={handleSubmit}>
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Paste your own code, or try one of the examples below"
            aria-label="Paste the code you want visualized"
          />
          <button type="submit" aria-label="Start visualizing">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </form>

        <div className="landing-chips">
          {EXAMPLES.map((ex) => (
            <button key={ex.label} className="landing-chip" onClick={() => onLaunch(ex.label)}>
              {ex.label}
            </button>
          ))}
        </div>
      </header>

      <section className="landing-feature" id="how-it-works">
        <div className="landing-feature-copy">
          <span className="landing-eyebrow">How it works</span>
          <h2>Watch your algorithm think.</h2>
          <p>
            Every run traces the actual execution — the variables that change, the
            lines that fire, the comparisons that happen — and turns it into a video
            with narration synced to what's on screen. You get something you can
            rewatch, share, or scrub through, not just a static diagram.
          </p>
          <ul className="landing-feature-list">
            <li>Python, with syntax highlighting as you type</li>
            <li>Narrated walkthroughs with the actual code on screen, generated per submission</li>
            <li>Scrub the video and the narration stays in sync — it's baked into the same file</li>
          </ul>
        </div>

        <div className="landing-feature-preview" aria-hidden="true">
          <div className="preview-chrome">
            <span className="preview-dot" />
            <span className="preview-dot" />
            <span className="preview-dot" />
          </div>
          <pre className="preview-code">{`def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []`}</pre>
          <div className="preview-player">
            <div className="preview-play-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
            <div className="preview-track">
              <div className="preview-track-fill" />
            </div>
            <span className="preview-time">0:07 / 0:35</span>
          </div>
        </div>
      </section>

      <section className="landing-footer-cta" id="footer-cta">
        <h2>Paste your first algorithm.</h2>
        <p>No sign-up. Just code, and a video comes back.</p>
        <button className="landing-nav-cta large" onClick={() => onLaunch()}>
          Open the editor
        </button>
      </section>
    </div>
  );
}

export default LandingPage;
