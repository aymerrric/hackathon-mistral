"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AudioUploader from "@/components/AudioUploader";
import CallReport from "@/components/CallReport";
import {
  analyzeCall,
  getAnalysis,
  getCall,
  getTree,
  uploadCall,
} from "@/lib/api";
import type { Call, CallAnalysis, Tree } from "@/lib/types";

/**
 * Call audit page — upload a recording of a past call, transcribe it with
 * Voxtral, then judge it against this tree. The call id lives in the URL
 * (?call=<id>) so a refresh re-fetches call + analysis instead of losing
 * state.
 */
export default function AuditPage({ params }: { params: { treeId: string } }) {
  const router = useRouter();
  const search = useSearchParams();
  const callId = search.get("call");

  const [tree, setTree] = useState<Tree | null>(null);
  const [call, setCall] = useState<Call | null>(null);
  const [analysis, setAnalysis] = useState<CallAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTree(params.treeId)
      .then(setTree)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [params.treeId]);

  // Restore from the URL on refresh / deep link.
  useEffect(() => {
    if (!callId) {
      setCall(null);
      setAnalysis(null);
      return;
    }
    if (call?.id === callId) return;
    getCall(callId)
      .then(setCall)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    getAnalysis(callId)
      .then(setAnalysis)
      .catch(() => setAnalysis(null)); // 404 = not analyzed yet
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callId]);

  useEffect(() => {
    if (!analyzing) return;
    setElapsed(0);
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [analyzing]);

  async function handleUpload(file: File) {
    setError(null);
    const created = await uploadCall(params.treeId, file); // throws -> uploader shows it
    setCall(created);
    setAnalysis(null);
    router.replace(`/trees/${params.treeId}/audit?call=${created.id}`);
  }

  async function runAnalysis() {
    if (!call || analyzing) return;
    setError(null);
    setAnalyzing(true);
    try {
      setAnalysis(await analyzeCall(call.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  }

  if (!tree) {
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading tree
      </div>
    );
  }

  return (
    <div className="container">
      <div className="browse-head">
        <h1 className="browse-title">Call audit</h1>
        <span className="muted">{tree.title}</span>
        <span style={{ flex: 1 }} />
        {call && (
          <button
            className="btn btn-ghost"
            onClick={() => {
              setError(null);
              router.replace(`/trees/${params.treeId}/audit`);
            }}
          >
            Audit another call
          </button>
        )}
      </div>

      {!call && (
        <AudioUploader busyLabel="Transcribing with Voxtral" onUpload={handleUpload} />
      )}

      {call && !analysis && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              className="btn btn-primary btn-lg"
              disabled={analyzing || !call.transcript}
              onClick={runAnalysis}
            >
              {analyzing ? "Judging" : "Analyze call"}
            </button>
            {analyzing && (
              <div className="progress-line" style={{ flex: 1 }}>
                <span className="spinner" />
                Judging against the tree · {elapsed}s
                <span className="faint">typically 10 to 30s</span>
              </div>
            )}
          </div>

          {call.transcript && (
            <>
              <div className="divider" />
              <div className="transcript-list">
                {call.transcript.map((t, i) => (
                  <div key={i} className="transcript-turn">
                    <span className="t-time">
                      {String(Math.floor(Math.max(0, Math.round(t.start)) / 60)).padStart(2, "0")}
                      :
                      {String(Math.max(0, Math.round(t.start)) % 60).padStart(2, "0")}
                    </span>
                    <span className={`t-speaker ${t.speaker}`}>{t.speaker}</span>
                    <span className="t-text">{t.text}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {call && analysis && call.transcript && (
        <CallReport tree={tree} transcript={call.transcript} analysis={analysis} />
      )}

      {error && (
        <p className="error-text" style={{ marginTop: 14 }}>
          {error}
        </p>
      )}
    </div>
  );
}
