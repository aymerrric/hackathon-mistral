"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { generateTree, uploadSpec } from "@/lib/api";

type Phase = "idle" | "uploading" | "generating";

/**
 * Procedure upload: name + file (.pdf/.txt/.md), drag and drop, then
 * uploadSpec -> generateTree with a live elapsed counter (generation is
 * synchronous, typically 10-30s). Routes to the new tree on success.
 */
export default function UploadCard() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (phase !== "generating") return;
    setElapsed(0);
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  // Must match what the backend extracts text from (routers/specs.py).
  const SUPPORTED = /\.(pdf|txt|md|markdown)$/i;

  function pick(f: File | null) {
    if (!f) return;
    if (!SUPPORTED.test(f.name)) {
      setError(`Unsupported file type: ${f.name}. Use PDF, TXT or MD.`);
      return;
    }
    setError(null);
    setFile(f);
    if (!name) setName(f.name.replace(SUPPORTED, ""));
  }

  async function submit() {
    if (!file || !name.trim() || phase !== "idle") return;
    setError(null);
    try {
      setPhase("uploading");
      const spec = await uploadSpec(name.trim(), file);
      setPhase("generating");
      const tree = await generateTree(spec.id);
      localStorage.setItem("calltree:last", tree.id);
      router.push(`/trees/${tree.id}`);
    } catch (e) {
      setPhase("idle");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const busy = phase !== "idle";

  return (
    <div className="card">
      <div style={{ marginBottom: 16 }}>
        <label className="label" htmlFor="tree-name">
          Procedure name
        </label>
        <input
          id="tree-name"
          className="input"
          placeholder="e.g. Dispatch intake, Returns and refunds"
          value={name}
          disabled={busy}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

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
          <span className="file-chip">{file.name}</span>
        ) : (
          <>
            <span className="primary-line">Drop the procedure document here</span>
            <span className="hint">or click to browse. PDF, TXT or MD.</span>
          </>
        )}
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,.txt,.md,.markdown"
          hidden
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
      </div>

      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
        <button
          className="btn btn-primary btn-lg"
          disabled={!file || !name.trim() || busy}
          onClick={submit}
        >
          {busy ? "Working" : "Generate tree"}
        </button>
        {phase === "uploading" && (
          <div className="progress-line" style={{ flex: 1 }}>
            <span className="spinner" /> Uploading and extracting text
          </div>
        )}
        {phase === "generating" && (
          <div className="progress-line" style={{ flex: 1 }}>
            <span className="spinner" />
            Generating tree with Mistral · {elapsed}s
            <span className="faint">typically 10 to 30s</span>
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
