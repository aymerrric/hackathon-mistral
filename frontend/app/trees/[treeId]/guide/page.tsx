"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createSession, finishSession, getTree, listTrees, takeStep } from "@/lib/api";
import type { GuidanceSession, Tree } from "@/lib/types";
import GuidePanel from "@/components/GuidePanel";
import AssistBar from "@/components/AssistBar";

/**
 * Guide mode: the operator-facing flow used DURING a live call.
 * One step on screen at a time, number keys to answer, path breadcrumb,
 * quiet assistant bar at the bottom. No Back: the session path is
 * append-only by design.
 */

function fmtDuration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function GuidePage(props: { params: { treeId: string } }) {
  // useSearchParams needs a Suspense boundary in the app router.
  return (
    <Suspense fallback={null}>
      <GuidePageInner {...props} />
    </Suspense>
  );
}

function GuidePageInner({ params }: { params: { treeId: string } }) {
  const router = useRouter();
  const search = useSearchParams();
  // ?stay=1 — the user explicitly chose this version; don't redirect away.
  const stay = search.get("stay") === "1";
  // ?switched=<v>&from=<id> — we landed here via the auto-redirect.
  const switchedFrom = search.get("switched");
  const switchedFromId = search.get("from");
  const [tree, setTree] = useState<Tree | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [operator, setOperator] = useState("");
  const [session, setSession] = useState<GuidanceSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [mainTree, setMainTree] = useState<Tree | null>(null);
  const [mainChecked, setMainChecked] = useState(false);

  useEffect(() => {
    getTree(params.treeId)
      .then(setTree)
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)));
    setOperator(localStorage.getItem("calltree:operator") ?? "");
  }, [params.treeId]);

  // Guiding happens on the employees' version by default: landing on any
  // other version redirects there, unless the user opted out with ?stay=1
  // (the redirect notice offers the way back).
  useEffect(() => {
    if (!tree || tree.is_main) {
      setMainTree(null);
      setMainChecked(true);
      return;
    }
    setMainChecked(false);
    listTrees()
      .then((all) => {
        const main =
          all.find((t) => t.spec_id === tree.spec_id && t.is_main) ?? null;
        setMainTree(main);
        setMainChecked(true);
        if (main && !stay) {
          router.replace(
            `/trees/${main.id}/guide?switched=${tree.version}&from=${tree.id}`
          );
        }
      })
      .catch(() => {
        setMainTree(null);
        setMainChecked(true);
      });
  }, [tree, stay, router]);

  useEffect(() => {
    if (session?.status !== "active") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [session?.status]);

  const currentNode =
    tree && session ? tree.structure.nodes[session.current_node_id] : null;

  const choose = useCallback(
    async (optionIndex: number) => {
      if (!session || !currentNode || busy || session.status !== "active") return;
      setBusy(true);
      setActionError(null);
      try {
        setSession(await takeStep(session.id, currentNode.id, optionIndex));
      } catch (e) {
        setActionError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [session, currentNode, busy]
  );

  const finish = useCallback(async () => {
    if (!session || busy) return;
    setBusy(true);
    setActionError(null);
    try {
      setSession(await finishSession(session.id));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [session, busy]);

  // Number keys answer questions; Enter advances actions / completes ends.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (!currentNode || session?.status !== "active") return;
      if (currentNode.type === "question") {
        const n = parseInt(e.key, 10);
        if (n >= 1 && n <= currentNode.options.length) choose(n - 1);
      } else if (e.key === "Enter") {
        currentNode.type === "action" ? choose(0) : finish();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [currentNode, session?.status, choose, finish]);

  async function start() {
    if (!tree || !operator.trim()) return;
    setBusy(true);
    setActionError(null);
    try {
      localStorage.setItem("calltree:operator", operator.trim());
      setSession(await createSession(tree.id, operator.trim()));
      setEditingName(false);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <div className="container-narrow">
        <p className="error-text">{loadError}</p>
      </div>
    );
  }
  if (!tree) {
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading tree
      </div>
    );
  }
  // Not the employees' version and no opt-out: the redirect effect is about
  // to fire (or the main lookup is still running) — don't flash this version.
  if (!tree.is_main && !stay && (!mainChecked || mainTree)) {
    return (
      <div className="page-loading">
        <span className="spinner" /> Switching to the employees&apos; version
      </div>
    );
  }

  // --- Pre-call: one keystroke to start ---------------------------------
  // The last operator name is remembered; the name form only appears the
  // first time (or via "change"), so a new call is a single Enter press.
  const versionNotice = !tree.is_main ? (
    // The user chose to stay on a non-employees version (?stay=1).
    <div className="version-notice">
      <span>
        Guiding on v{tree.version} — not the version employees use
        {mainTree ? ` (v${mainTree.version})` : ""}.
      </span>
      {mainTree && (
        <a
          href={`/trees/${mainTree.id}/guide`}
          style={{ color: "inherit", fontWeight: 600 }}
        >
          Back to v{mainTree.version}
        </a>
      )}
    </div>
  ) : switchedFrom && switchedFromId ? (
    // Landed here via the auto-redirect: leave a way back.
    <div className="version-notice info">
      <span>
        Switched to v{tree.version}, the version employees use.
      </span>
      <a
        href={`/trees/${switchedFromId}/guide?stay=1`}
        style={{ color: "inherit", fontWeight: 600 }}
      >
        Use v{switchedFrom} instead
      </a>
      <button
        className="notice-dismiss"
        aria-label="Dismiss"
        onClick={() => router.replace(`/trees/${tree.id}/guide`)}
      >
        ×
      </button>
    </div>
  ) : null;

  if (!session) {
    const knownOperator = operator.trim().length > 0 && !editingName;
    return (
      <div className="container-narrow" style={{ paddingTop: 56 }}>
        {versionNotice}
        <div className="eyebrow">
          {tree.title} · v{tree.version}
        </div>
        <h1 className="hero-title" style={{ fontSize: 26 }}>
          New call
        </h1>
        <div className="card" style={{ maxWidth: 460 }}>
          {knownOperator ? (
            <>
              <button
                className="btn btn-primary btn-lg"
                style={{ width: "100%" }}
                autoFocus
                disabled={busy}
                onClick={start}
              >
                {busy ? "Starting" : "Start call"}
              </button>
              <p
                className="muted"
                style={{ margin: "12px 0 0", fontSize: 13, textAlign: "center" }}
              >
                Operator: {operator.trim()} ·{" "}
                <button
                  className="btn btn-ghost"
                  style={{ padding: "0 4px", fontSize: 13 }}
                  onClick={() => setEditingName(true)}
                >
                  change
                </button>
              </p>
            </>
          ) : (
            <>
              <label className="label" htmlFor="operator">
                Operator
              </label>
              <input
                id="operator"
                className="input"
                placeholder="Your name"
                value={operator}
                autoFocus
                onChange={(e) => setOperator(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && start()}
              />
              <button
                className="btn btn-primary btn-lg"
                style={{ marginTop: 14, width: "100%" }}
                disabled={!operator.trim() || busy}
                onClick={start}
              >
                {busy ? "Starting" : "Start call"}
              </button>
            </>
          )}
          {actionError && (
            <p className="error-text" style={{ marginTop: 10, marginBottom: 0 }}>
              {actionError}
            </p>
          )}
        </div>
      </div>
    );
  }

  const startedMs = new Date(session.started_at).getTime();
  const endMs = session.ended_at ? new Date(session.ended_at).getTime() : now;

  // --- Finished: recap --------------------------------------------------
  if (session.status !== "active") {
    return (
      <div className="container-narrow" style={{ paddingTop: 56 }}>
        <div className="card">
          <span
            className="end-banner"
            style={
              session.status === "abandoned"
                ? { background: "var(--warn-dim)", color: "var(--warn)" }
                : undefined
            }
          >
            Call {session.status}
          </span>
          <div className="summary-row">
            <div className="stat">
              <div className="v">{fmtDuration(endMs - startedMs)}</div>
              <div className="k">Duration</div>
            </div>
            <div className="stat">
              <div className="v">{session.path.length}</div>
              <div className="k">Steps</div>
            </div>
            <div className="stat">
              <div className="v">{session.agent_name}</div>
              <div className="k">Operator</div>
            </div>
          </div>
          <hr className="divider" />
          <div className="crumbs" style={{ marginBottom: 0 }}>
            {session.path.map((p, i) => {
              const n = tree.structure.nodes[p.node_id];
              return (
                <span key={i} style={{ display: "contents" }}>
                  <span className="crumb">{n?.label ?? p.node_id}</span>
                  <span className="crumb-arrow">›</span>
                </span>
              );
            })}
            <span className="crumb" style={{ color: "var(--ok)" }}>
              {tree.structure.nodes[session.current_node_id]?.label ??
                session.current_node_id}
            </span>
          </div>
        </div>
        <button
          className="btn btn-primary btn-lg"
          style={{ marginTop: 18 }}
          autoFocus
          disabled={busy}
          onClick={start}
        >
          {busy ? "Starting" : `New call as ${session.agent_name}`}
        </button>
        {actionError && (
          <p className="error-text" style={{ marginTop: 10 }}>
            {actionError}
          </p>
        )}
      </div>
    );
  }

  // --- Active call ------------------------------------------------------
  return (
    <div className="container-narrow" style={{ paddingTop: 26, paddingBottom: 140 }}>
      <div className="session-meta">
        <span className="timer">{fmtDuration(now - startedMs)}</span>
        <span>
          {session.agent_name} · {tree.title} v{tree.version}
        </span>
        <span className="spacer" />
        <span className="faint">
          step {session.path.length + 1}
        </span>
        <button className="btn btn-danger-ghost" onClick={finish} disabled={busy}>
          Abandon
        </button>
      </div>

      <div className="crumbs">
        {session.path.map((p, i) => {
          const n = tree.structure.nodes[p.node_id];
          const optLabel = n?.options[p.option_index]?.label;
          return (
            <span key={i} style={{ display: "contents" }}>
              <span
                className="crumb"
                title={optLabel ? `Answer: ${optLabel}` : undefined}
              >
                {n?.label ?? p.node_id}
              </span>
              <span className="crumb-arrow">›</span>
            </span>
          );
        })}
        {session.path.length === 0 && (
          <span className="faint" style={{ fontSize: 12 }}>
            Call started, first step below
          </span>
        )}
      </div>

      {currentNode ? (
        <>
          <GuidePanel node={currentNode} busy={busy} onChoose={choose} />
          {currentNode.type === "end" && (
            <button
              className="btn btn-primary btn-lg"
              style={{ marginTop: 16 }}
              disabled={busy}
              onClick={finish}
            >
              Complete call
            </button>
          )}
        </>
      ) : (
        <p className="error-text">
          Node {session.current_node_id} is missing from this tree version.
        </p>
      )}

      {actionError && (
        <p className="error-text" style={{ marginTop: 12 }}>
          {actionError}
        </p>
      )}

      <AssistBar treeId={tree.id} nodeId={session.current_node_id} />
    </div>
  );
}
