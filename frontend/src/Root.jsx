import React, { useState, useEffect, useCallback } from 'react';
import App from './App';
import LandingPage from './components/LandingPage';
import { EXAMPLES } from './exampleCode';

// history.state's shape for the one entry this app ever pushes.
const APP_VIEW_STATE = { view: 'app' };

function Root() {
  // Previously `showApp` was plain useState with no connection to the
  // browser's history stack at all -- entering the editor never pushed
  // an entry, so from the browser's point of view the landing page and
  // the editor were the same single "page." Pressing back therefore had
  // nothing of this site's to go back TO, and fell through to whatever
  // was open before the site (a different tab, or closing the tab).
  // Initializing from history.state (rather than always starting at
  // landing) also means a hard refresh while on the editor -- which
  // already lands back on history's current entry -- doesn't then
  // disagree with that entry on the very next back press.
  const [showApp, setShowApp] = useState(
    () => window.history.state?.view === 'app'
  );
  const [initialCode, setInitialCode] = useState('');

  // Back/forward button presses fire popstate; this is the only place
  // showApp should flip in response to navigation (as opposed to
  // handleLaunch, which flips it in response to an in-app button click
  // and separately pushes the entry that this listener later reacts to).
  useEffect(() => {
    const handlePopState = (event) => {
      setShowApp(event.state?.view === 'app');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleLaunch = useCallback((promptText) => {
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
    // pushState (not replaceState): this needs to be a NEW entry on top
    // of the landing page's, not a replacement of it -- replacing would
    // still leave nothing for a subsequent back press to land on.
    window.history.pushState(APP_VIEW_STATE, '');
    setShowApp(true);
  }, []);

  if (showApp) {
    return <App initialCode={initialCode} />;
  }

  return <LandingPage onLaunch={handleLaunch} />;
}

export default Root;