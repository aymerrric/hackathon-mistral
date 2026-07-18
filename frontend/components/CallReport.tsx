"use client";

import type { CallAnalysis, TranscriptTurn, Tree } from "@/lib/types";

/**
 * The judgment view — where the call went well and where it went wrong.
 * TO IMPLEMENT. This is the second demo centerpiece.
 *
 * Spec:
 *  - Top: score as a big number with color (>=80 green, 50-79 orange,
 *    <50 red) and the summary sentence next to it.
 *  - Left column: <TreeViewer/> with highlightPath=analysis.matched_path
 *    and verdictByNode derived from step_verdicts (followed=green,
 *    deviated=red, skipped=orange).
 *  - Right column: the step-by-step verdict list, in matched_path order:
 *    node label, verdict badge, the transcript_excerpt as a quoted block,
 *    the explanation underneath.
 *  - Bottom (collapsible): full transcript with timestamps and speaker
 *    labels.
 */
export interface CallReportProps {
  tree: Tree;
  transcript: TranscriptTurn[];
  analysis: CallAnalysis;
}

export default function CallReport(props: CallReportProps) {
  return <p>TODO: implement CallReport</p>;
}
