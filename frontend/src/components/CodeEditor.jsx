import React from 'react';
import Editor from '@monaco-editor/react';

const DEFAULT_CODE = `def two_sum(nums, target):
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
        theme="vs-dark"
        defaultValue={DEFAULT_CODE}
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
