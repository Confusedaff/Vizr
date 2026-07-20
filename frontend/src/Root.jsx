import React, { useState } from 'react';
import App from './App';
import LandingPage from './components/LandingPage';
import { EXAMPLES } from './exampleCode';

function Root() {
  const [showApp, setShowApp] = useState(false);
  const [initialCode, setInitialCode] = useState('');

  const handleLaunch = (promptText) => {
    // promptText is either a known example chip's label, arbitrary text
    // typed into the free-text prompt bar, or undefined (the plain
    // "Open the editor" buttons call onLaunch() with no argument).
    //
    // Only known chip labels resolve to real code -- there's no
    // code-generation step in this app, so arbitrary free text can't be
    // turned into a runnable algorithm. Previously ANY promptText (chip
    // or free text alike) was wrapped as `# ${promptText}`, a Python
    // comment with nothing for the tracer to actually execute; the
    // resulting "narrated walkthrough" was just generic intro/outro
    // narration over an almost-empty video. Silently doing that for
    // unmatched free text would be just as broken as before, so instead
    // unmatched input is ignored and the editor opens with its normal
    // default rather than a comment that looks like a bug.
    const matched = EXAMPLES.find((ex) => ex.label === promptText);
    if (matched) {
      setInitialCode(matched.code);
    }
    setShowApp(true);
  };

  if (showApp) {
    return <App initialCode={initialCode} />;
  }

  return <LandingPage onLaunch={handleLaunch} />;
}

export default Root;
