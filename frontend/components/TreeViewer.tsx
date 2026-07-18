"use client";

import type { TreeStructure } from "@/lib/types";

/**
 * Read-only rendering of a decision tree. TO IMPLEMENT.
 *
 * Spec:
 *  - Render from structure.root_id as an indented outline (simplest) or a
 *    proper node-edge diagram if someone wants to pull in reactflow.
 *  - Each node: label (bold), type badge (question=blue, action=amber,
 *    end=green), prompt text, and its option labels as edge captions.
 *  - `highlightPath`: node ids to emphasize (used by CallReport to show the
 *    path the agent took; also color 'deviated'/'skipped' nodes red/orange
 *    via `verdictByNode`).
 *  - onNodeClick optional (used by the tree edit stretch goal).
 *  - Trees can branch into the same node twice (it's a DAG in practice);
 *    when rendering as an outline, re-visited nodes render as a stub link
 *    ("↪ n7 Confirm address") instead of recursing forever.
 */
export interface TreeViewerProps {
  structure: TreeStructure;
  highlightPath?: string[];
  verdictByNode?: Record<string, "followed" | "deviated" | "skipped">;
  onNodeClick?: (nodeId: string) => void;
}

export default function TreeViewer(props: TreeViewerProps) {
  return <p>TODO: implement TreeViewer</p>;
}
