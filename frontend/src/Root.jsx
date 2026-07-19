import React, { useState } from 'react';
import App from './App';
import LandingPage from './components/LandingPage';

function Root() {
  const [showApp, setShowApp] = useState(false);
  const [initialCode, setInitialCode] = useState('');

  const handleLaunch = (promptText) => {
    // Example chips pass through a plain description (e.g. "Explain binary search").
    // Only route it into the editor as a code comment when it looks like a prompt,
    // not code the person actually typed themselves.
    if (promptText) {
      setInitialCode(`# ${promptText}\n`);
    }
    setShowApp(true);
  };

  if (showApp) {
    return <App initialCode={initialCode} />;
  }

  return <LandingPage onLaunch={handleLaunch} />;
}

export default Root;
