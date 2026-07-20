import React, { useCallback } from 'react';
import Editor from '@monaco-editor/react';

// Monaco can't read CSS custom properties directly, so the editor's
// palette is defined here in lockstep with the hex values in App.css
// (--surface, --accent, --text-primary, etc).
const applyEditorTheme = (monaco) => {
  monaco.editor.defineTheme('code-visualizer-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '5b6577', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'f5c542' },
      { token: 'string', foreground: '4fb0a5' },
      { token: 'number', foreground: 'f0716b' },
    ],
    colors: {
      'editor.background': '#161d29',
      'editor.foreground': '#e8ecf1',
      'editor.lineHighlightBackground': '#1c243360',
      'editorLineNumber.foreground': '#5b6577',
      'editorLineNumber.activeForeground': '#8593a8',
      'editorCursor.foreground': '#f5c542',
      'editor.selectionBackground': '#f5c54233',
      'editorIndentGuide.background': '#232b3a',
    },
  });
};

// Exported so App.jsx can use this as the real initial editor content.
// Previously this was only ever passed as Monaco's `defaultValue`, but
// App.jsx always supplies a defined `value` prop (even as an empty
// string) -- and once `value` is defined, Monaco treats the editor as
// controlled and `defaultValue` is never consulted at all. That made
// this demo unreachable in practice: anyone opening the editor directly
// (rather than through a chip that sets real starter code) just saw a
// blank box instead of this example.
export const DEFAULT_CODE = `def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# Test the function
result = two_sum([2, 7, 11, 15], 9)
print(result)  # Expected: [0, 1]
`;

function CodeEditor({ code, setCode, language }) {
  const handleBeforeMount = useCallback((monaco) => {
    applyEditorTheme(monaco);
  }, []);

  return (
    <div className="editor-container">
      <div className="editor-header">
        <span className="editor-label">Code Editor</span>
        <span className="editor-lang">{language}</span>
      </div>
      <Editor
        height="400px"
        language={language}
        value={code}
        onChange={(value) => setCode(value || '')}
        theme="code-visualizer-dark"
        beforeMount={handleBeforeMount}
        options={{
          fontSize: 14,
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          lineNumbers: 'on',
          renderLineHighlight: 'all',
          suggestOnTriggerCharacters: true,
          wordWrap: 'on',
          padding: { top: 12, bottom: 12 },
        }}
      />
    </div>
  );
}

export default CodeEditor;
