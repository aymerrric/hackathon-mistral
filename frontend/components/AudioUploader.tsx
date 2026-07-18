"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Audio file picker + upload button with progress states.
 *
 * Accepts .mp3/.wav/.m4a (others rejected with an inline error), shows the
 * chosen filename and size, renders `busyLabel` with a spinner and elapsed
 * counter while the parent's async onUpload runs, and surfaces thrown
 * errors inline below the button.
 */
export interface AudioUploaderProps {
  busyLabel: string;
  onUpload: (file: File) => Promise<void>;
}

const SUPPORTED = /\.(mp3|wav|m4a)$/i;

function fmtSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AudioUploader({ busyLabel, onUpload }: AudioUploaderProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!busy) return;
    setElapsed(0);
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [busy]);

  function pick(f: File | null) {
    if (!f) return;
    if (!SUPPORTED.test(f.name)) {
      setError(`Unsupported file type: ${f.name}. Use MP3, WAV or M4A.`);
      return;
    }
    setError(null);
    setFile(f);
  }

  async function submit() {
    if (!file || busy) return;
    setError(null);
    setBusy(true);
    try {
      await onUpload(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div
        className={`dropzone ${drag ? "drag" : ""}`}
        onClick={() => !busy && fileInput.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!busy) pick(e.dataTransfer.files?.[0] ?? null);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !busy) fileInput.current?.click();
        }}
      >
        {file ? (
          <span className="file-chip">
            {file.name} · {fmtSize(file.size)}
          </span>
        ) : (
          <>
            <span className="primary-line">Drop the call recording here</span>
            <span className="hint">or click to browse. MP3, WAV or M4A.</span>
          </>
        )}
        <input
          ref={fileInput}
          type="file"
          accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/mp4"
          hidden
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
      </div>

      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn btn-primary btn-lg" disabled={!file || busy} onClick={submit}>
          {busy ? "Working" : "Upload & transcribe"}
        </button>
        {busy && (
          <div className="progress-line" style={{ flex: 1 }}>
            <span className="spinner" />
            {busyLabel} · {elapsed}s
          </div>
        )}
      </div>

      {error && (
        <p className="error-text" style={{ marginTop: 12, marginBottom: 0 }}>
          {error}
        </p>
      )}
    </div>
  );
}
