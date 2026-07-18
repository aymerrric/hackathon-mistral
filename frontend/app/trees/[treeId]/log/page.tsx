"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { finishSession, getTree, listSessions, listTrees } from "@/lib/api";
import type { GuidanceSession, Tree } from "@/lib/types";

/**
 * Call log: every guided session for this procedure (all versions of it),
 * a small KPI row, and the exact path taken per call (click a row).
 */

function fmtDuration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function fmtWhen(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function LogPage({ params }: { params: { treeId: string } }) {
  const [tree, setTree] = useState<Tree | null>(null);
  const [trees, setTrees] = useState<Tree[]>([]);
  const [sessions, setSessions] = useState<GuidanceSession[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [closing, setClosing] = useState<string | null>(null);

  // Admin action: force-finish a session someone left open. The backend
  // marks it abandoned unless it is already on an end node.
  async function closeCall(sessionId: string) {
    setClosing(sessionId);
    setError(null);
    try {
      const updated = await finishSession(sessionId);
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setClosing(null);
    }
  }

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

  // Sessions for any version of this procedure, with each session's own
  // tree version used to resolve node labels.
  const rows = useMemo(() => {
    if (!tree) return [];
    const family = new Map(
      trees.filter((t) => t.spec_id === tree.spec_id).map((t) => [t.id, t])
    );
    return sessions
      .filter((s) => family.has(s.tree_id))
      .map((s) => {
        const structure = family.get(s.tree_id)!.structure;
        const label = (id: string) => structure.nodes[id]?.label ?? id;
        const endMs = s.ended_at ? new Date(s.ended_at).getTime() : null;
        return {
          s,
          version: family.get(s.tree_id)!.version,
          outcome: label(s.current_node_id),
          steps: s.path.map((p) => ({
            label: label(p.node_id),
            answer:
              structure.nodes[p.node_id]?.options[p.option_index]?.label ?? "",
          })),
          durationMs: endMs ? endMs - new Date(s.started_at).getTime() : null,
        };
      });
  }, [tree, trees, sessions]);

  const kpi = useMemo(() => {
    const ended = rows.filter((r) => r.durationMs !== null);
    const completed = rows.filter((r) => r.s.status === "completed");
    const avg = (xs: number[]) =>
      xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
    return {
      total: rows.length,
      completedPct: rows.length
        ? Math.round((100 * completed.length) / rows.length)
        : null,
      avgDurationMs: avg(ended.map((r) => r.durationMs!)),
      avgSteps: avg(rows.map((r) => r.s.path.length)),
    };
  }, [rows]);

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
        <span className="spinner" /> Loading call log
      </div>
    );
  }

  return (
    <div className="container">
      <div className="browse-head">
        <h1 className="browse-title">Call log</h1>
        <span className="muted">{tree.title}</span>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <div className="v">{kpi.total}</div>
          <div className="k">Calls</div>
        </div>
        <div className="kpi">
          <div className="v">{kpi.completedPct === null ? "–" : `${kpi.completedPct}%`}</div>
          <div className="k">Completed</div>
        </div>
        <div className="kpi">
          <div className="v">
            {kpi.avgDurationMs === null ? "–" : fmtDuration(kpi.avgDurationMs)}
          </div>
          <div className="k">Avg duration</div>
        </div>
        <div className="kpi">
          <div className="v">{kpi.avgSteps === null ? "–" : kpi.avgSteps.toFixed(1)}</div>
          <div className="k">Avg steps</div>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="muted">No calls yet. They appear here as soon as a guided call is started.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="log-table">
            <thead>
              <tr>
                <th>Started</th>
                <th>Operator</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Steps</th>
                <th>Outcome</th>
                <th>Tree</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.s.id}>
                  <tr
                    className="log-row"
                    onClick={() =>
                      setExpanded(expanded === r.s.id ? null : r.s.id)
                    }
                  >
                    <td>{fmtWhen(r.s.started_at)}</td>
                    <td>{r.s.agent_name}</td>
                    <td>
                      <span className={`status-chip ${r.s.status}`}>
                        {r.s.status}
                      </span>
                    </td>
                    <td className="mono">
                      {r.durationMs === null ? "live" : fmtDuration(r.durationMs)}
                    </td>
                    <td className="mono">{r.s.path.length}</td>
                    <td>{r.outcome}</td>
                    <td className="mono faint">v{r.version}</td>
                    <td style={{ textAlign: "right", padding: "4px 8px" }}>
                      {r.s.status === "active" && (
                        <button
                          className="btn btn-danger-ghost"
                          style={{ padding: "3px 10px", fontSize: 12 }}
                          disabled={closing === r.s.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            closeCall(r.s.id);
                          }}
                        >
                          {closing === r.s.id ? "Closing" : "Close"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expanded === r.s.id && (
                    <tr className="log-detail">
                      <td colSpan={8}>
                        {r.steps.length === 0 ? (
                          <span className="faint">No steps taken.</span>
                        ) : (
                          <div className="crumbs" style={{ margin: 0 }}>
                            {r.steps.map((st, i) => (
                              <span key={i} style={{ display: "contents" }}>
                                <span
                                  className="crumb"
                                  title={st.answer ? `Answer: ${st.answer}` : undefined}
                                >
                                  {st.label}
                                  {st.answer ? ` · ${st.answer}` : ""}
                                </span>
                                <span className="crumb-arrow">›</span>
                              </span>
                            ))}
                            <span
                              className="crumb"
                              style={{
                                color:
                                  r.s.status === "completed"
                                    ? "var(--ok)"
                                    : undefined,
                              }}
                            >
                              {r.outcome}
                            </span>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
