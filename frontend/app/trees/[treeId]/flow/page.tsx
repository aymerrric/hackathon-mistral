"use client";

import { useEffect, useMemo, useState } from "react";
import { getTree, listSessions, listTrees } from "@/lib/api";
import type { GuidanceSession, Tree } from "@/lib/types";
import FlowTree from "@/components/FlowTree";

/**
 * Flow analytics: the decision tree as a node-link diagram with the share
 * of calls flowing through every branch. Aggregates sessions from all
 * versions of this procedure; path entries that no longer resolve in the
 * displayed version are ignored.
 */
export default function FlowPage({ params }: { params: { treeId: string } }) {
  const [tree, setTree] = useState<Tree | null>(null);
  const [trees, setTrees] = useState<Tree[]>([]);
  const [sessions, setSessions] = useState<GuidanceSession[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([getTree(params.treeId), listTrees(), listSessions()])
      .then(([t, all, sess]) => {
        setTree(t);
        setTrees(all);
        setSessions(sess);
        setLoaded(true);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [params.treeId]);

  const familySessions = useMemo(() => {
    if (!tree) return [];
    const family = new Set(
      trees.filter((t) => t.spec_id === tree.spec_id).map((t) => t.id)
    );
    return sessions.filter((s) => family.has(s.tree_id));
  }, [tree, trees, sessions]);

  if (error) {
    return (
      <div className="container">
        <p className="error-text">{error}</p>
      </div>
    );
  }
  if (!loaded || !tree) {
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading call flow
      </div>
    );
  }

  return (
    <div className="container">
      <div className="browse-head">
        <h1 className="browse-title">Call flow</h1>
        <span className="version-pill">v{tree.version}</span>
        <span className="muted">{tree.title}</span>
      </div>
      <p className="muted" style={{ margin: "4px 0 16px", fontSize: 13 }}>
        {familySessions.length} call{familySessions.length === 1 ? "" : "s"} ·
        edge thickness and % = share of calls taking that branch · dashed grey
        = never taken
      </p>

      {familySessions.length === 0 && (
        <p className="muted">
          No calls yet. Run guided calls and their routes appear here.
        </p>
      )}

      <div className="outline" style={{ overflow: "auto", padding: 0 }}>
        <FlowTree structure={tree.structure} sessions={familySessions} />
      </div>
    </div>
  );
}
