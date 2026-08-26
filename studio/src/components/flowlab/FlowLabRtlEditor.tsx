"use client";

import dynamic from "next/dynamic";
import { useCallback } from "react";

const Monaco = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="fl-editor-skeleton" aria-busy="true" />,
});

export function FlowLabRtlEditor({
  value,
  onChange,
  readOnly,
}: {
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
}) {
  const onMount = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (editor: any, monaco: any) => {
      monaco.editor.defineTheme("flowlab-dark", {
        base: "vs-dark",
        inherit: true,
        rules: [
          { token: "comment", foreground: "6a9955", fontStyle: "italic" },
          { token: "keyword", foreground: "569cd6" },
          { token: "number", foreground: "b5cea8" },
          { token: "string", foreground: "ce9178" },
          { token: "identifier", foreground: "9cdcfe" },
        ],
        colors: {
          "editor.background": "#0a0e14",
          "editor.foreground": "#e6edf3",
          "editorLineNumber.foreground": "#484f58",
          "editorLineNumber.activeForeground": "#8b949e",
          "editor.selectionBackground": "#264f78",
          "editor.lineHighlightBackground": "#161b22",
          "editorCursor.foreground": "#f0883e",
          "editorGutter.background": "#0a0e14",
        },
      });
      monaco.editor.setTheme("flowlab-dark");
      editor.updateOptions({
        fontFamily: "var(--font-mono), ui-monospace, monospace",
        fontSize: 13,
        lineHeight: 22,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        wordWrap: "on",
        tabSize: 2,
        insertSpaces: true,
        automaticLayout: true,
        padding: { top: 12, bottom: 12 },
        renderLineHighlight: "all",
        bracketPairColorization: { enabled: true },
      });
    },
    [],
  );

  return (
    <div className="fl-editor-wrap">
      <Monaco
        height="100%"
        defaultLanguage="verilog"
        theme="flowlab-dark"
        value={value}
        onChange={(v) => onChange(v ?? "")}
        onMount={onMount}
        options={{
          readOnly,
          language: "verilog",
        }}
      />
    </div>
  );
}
