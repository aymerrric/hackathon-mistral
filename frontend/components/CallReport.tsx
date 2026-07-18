"use client";

import { useMemo, useState } from "react";
import TreeViewer from "@/components/TreeViewer";
import type { CallAnalysis, TranscriptTurn, Tree } from "@/lib/types";

/**
 * The judgment view — where the call went well and where it went wrong.
 * Score header, tree with the matched path and per-node verdicts, the
 * step-by-step verdict list with quotes, and a collapsible full transcript.
 */
export interface CallReportProps {
  tree: Tree;
  transcript: TranscriptTurn[];
  analysis: CallAnalysis;
}

function fmtTime(s: number): string {
  const t = Math.max(0, Math.round(s));
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

export default function CallReport({ tree, transcript, analysis }: CallReportProps) {
  const [showTranscript, setShowTranscript] = useState(false);

  const scoreClass =
    analysis.score >= 80 ? "good" : analysis.score >= 50 ? "mid" : "bad";

  const verdictByNode = useMemo(() => {
    const map: Record<string, "followed" | "deviated" | "skipped"> = {};
    for (const v of analysis.step_verdicts) map[v.node_id] = v.verdict;
    return map;
  }, [analysis.step_verdicts]);

  // Verdicts in matched_path order; any verdict on a node outside the
  // matched path (e.g. a skipped branch) goes at the end.
  const orderedVerdicts = useMemo(() => {
    const order = new Map(analysis.matched_path.map((id, i) => [id, i]));
    return [...analysis.step_verdicts].sort(
      (a, b) =>
        (order.get(a.node_id) ?? Number.MAX_SAFE_INTEGER) -
        (order.get(b.node_id) ?? Number.MAX_SAFE_INTEGER)
    );
  }, [analysis]);

  return (
    <div className="report">
      <div className="report-head">
        <div className={`report-score ${scoreClass}`}>
          {analysis.score}
          <span className="of">/100</span>
        </div>
        <p className="report-summary">{analysis.summary}</p>
      </div>

      <div className="report-grid">
        <div className="report-tree">
          <TreeViewer
            structure={tree.structure}
            highlightPath={analysis.matched_path}
            verdictByNode={verdictByNode}
          />
        </div>

        <div className="report-steps">
          {orderedVerdicts.map((v, i) => (
            <div key={`${v.node_id}-${i}`} className="verdict-card">
              <div className="verdict-top">
                <span className="verdict-label">
                  {tree.structure.nodes[v.node_id]?.label ?? v.node_id}
                </span>
                <span className={`verdict-badge ${v.verdict}`}>{v.verdict}</span>
              </div>
              {v.transcript_excerpt && (
                <blockquote className="verdict-quote">“{v.transcript_excerpt}”</blockquote>
              )}
              <p className="verdict-expl">{v.explanation}</p>
            </div>
          ))}
          {orderedVerdicts.length === 0 && (
            <p className="muted">No step verdicts returned.</p>
          )}
        </div>
      </div>

      <div className="report-transcript">
        <button
          className="btn btn-ghost"
          onClick={() => setShowTranscript((s) => !s)}
          aria-expanded={showTranscript}
        >
          {showTranscript ? "Hide full transcript" : `Show full transcript (${transcript.length} turns)`}
        </button>
        {showTranscript && (
          <div className="transcript-list">
            {transcript.map((t, i) => (
              <div key={i} className="transcript-turn">
                <span className="t-time">{fmtTime(t.start)}</span>
                <span className={`t-speaker ${t.speaker}`}>{t.speaker}</span>
                <span className="t-text">{t.text}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
