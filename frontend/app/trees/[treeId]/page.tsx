"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { deleteTree, getTree, listTrees, selectTree, updateTree } from "@/lib/api";
import type { NodeType, Tree, TreeStructure } from "@/lib/types";
import TreeViewer from "@/components/TreeViewer";

/**
 * Tree mode: free browsing and editing of the ground-truth tree.
 * Edits are local until saved; saving writes a NEW version (the backend
 * never mutates a tree in place) and navigates to it.
 */

function validate(s: TreeStructure): string[] {
  const out: string[] = [];
  if (!s.nodes[s.root_id]) out.push(`Root node ${s.root_id} does not exist.`);

  for (const [id, n] of Object.entries(s.nodes)) {
    if (n.id !== id) out.push(`Node key ${id} does not match its id ${n.id}.`);
    if (n.type === "question" && n.options.length < 2)
      out.push(`${id} ${n.label}: questions need at least 2 options.`);
    if (n.type === "action" && n.options.length !== 1)
      out.push(`${id} ${n.label}: actions need exactly 1 option.`);
    if (n.type === "end" && n.options.length !== 0)
      out.push(`${id} ${n.label}: end nodes cannot have options.`);
    for (const o of n.options) {
      if (!s.nodes[o.next_id])
        out.push(`${id} ${n.label}: option "${o.label}" points to missing node ${o.next_id}.`);
    }
  }

  // Every node reachable from the root must be able to reach an end node.
  const canEnd = new Set(
    Object.values(s.nodes).filter((n) => n.type === "end").map((n) => n.id)
  );
  let grew = true;
  while (grew) {
    grew = false;
    for (const n of Object.values(s.nodes)) {
      if (canEnd.has(n.id)) continue;
      if (n.options.some((o) => canEnd.has(o.next_id))) {
        canEnd.add(n.id);
        grew = true;
      }
    }
  }
  const reachable = new Set<string>();
  const stack = s.nodes[s.root_id] ? [s.root_id] : [];
  while (stack.length) {
    const id = stack.pop()!;
    if (reachable.has(id) || !s.nodes[id]) continue;
    reachable.add(id);
    for (const o of s.nodes[id].options) stack.push(o.next_id);
  }
  for (const id of reachable) {
    if (!canEnd.has(id))
      out.push(`${id} ${s.nodes[id].label}: no path from here reaches an end node.`);
  }
  return out;
}

function freshId(s: TreeStructure): string {
  let max = 0;
  for (const id of Object.keys(s.nodes)) {
    const m = id.match(/^n(\d+)$/);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  let candidate = `n${max + 1}`;
  while (s.nodes[candidate]) candidate += "x";
  return candidate;
}

export default function TreePage({ params }: { params: { treeId: string } }) {
  const router = useRouter();
  const [tree, setTree] = useState<Tree | null>(null);
  const [draft, setDraft] = useState<TreeStructure | null>(null);
  const [title, setTitle] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState<Tree[]>([]);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);
  const [versionBusy, setVersionBusy] = useState(false);
  const verMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setVersionsOpen(false);
    setConfirmDelete(false);
    setVersionError(null);
    getTree(params.treeId)
      .then((t) => {
        setTree(t);
        setDraft(structuredClone(t.structure));
        setTitle(t.title);
        setSelected(t.structure.root_id);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)));
  }, [params.treeId]);

  // All versions of this spec, newest first, for the version switcher.
  useEffect(() => {
    if (!tree) return;
    listTrees()
      .then((all) =>
        setVersions(
          all
            .filter((t) => t.spec_id === tree.spec_id)
            .sort((a, b) => b.version - a.version)
        )
      )
      .catch(() => setVersions([]));
  }, [tree]);

  useEffect(() => {
    if (!versionsOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!verMenuRef.current?.contains(e.target as Node)) setVersionsOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [versionsOpen]);

  const dirty = useMemo(() => {
    if (!tree || !draft) return false;
    return (
      title !== tree.title ||
      JSON.stringify(draft) !== JSON.stringify(tree.structure)
    );
  }, [tree, draft, title]);

  const violations = useMemo(() => (draft ? validate(draft) : []), [draft]);

  function mutate(fn: (s: TreeStructure) => void) {
    setDraft((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
  }

  async function makeMain() {
    if (!tree || tree.is_main) return;
    setVersionBusy(true);
    setVersionError(null);
    try {
      const updated = await selectTree(tree.id);
      setTree(updated);
      setVersions((vs) => vs.map((v) => ({ ...v, is_main: v.id === updated.id })));
    } catch (e) {
      setVersionError(e instanceof Error ? e.message : String(e));
    } finally {
      setVersionBusy(false);
    }
  }

  async function removeVersion() {
    if (!tree) return;
    setVersionBusy(true);
    setVersionError(null);
    try {
      await deleteTree(tree.id);
      const rest = versions.filter((v) => v.id !== tree.id);
      // If the deleted version was the employees' one, the backend promotes
      // the highest remaining version — mirror that choice here.
      const target = rest.find((v) => v.is_main) ?? rest[0];
      router.push(target ? `/trees/${target.id}` : "/");
    } catch (e) {
      setVersionError(e instanceof Error ? e.message : String(e));
      setVersionBusy(false);
      setConfirmDelete(false);
    }
  }

  async function save() {
    if (!tree || !draft || violations.length > 0) return;
    setSaving(true);
    setSaveError(null);
    try {
      const next = await updateTree(tree.id, draft, title);
      router.push(`/trees/${next.id}`);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="container">
        <p className="error-text">{loadError}</p>
      </div>
    );
  }
  if (!tree || !draft) {
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading tree
      </div>
    );
  }

  const node = selected ? draft.nodes[selected] : null;
  const counts = { question: 0, action: 0, end: 0 } as Record<NodeType, number>;
  for (const n of Object.values(draft.nodes)) counts[n.type]++;
  const referencedBy = (id: string) =>
    Object.values(draft.nodes).filter((n) =>
      n.options.some((o) => o.next_id === id)
    );

  return (
    <div className="container" style={{ paddingBottom: dirty ? 120 : 80 }}>
      <div className="browse-head">
        <input
          className="browse-title-input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          aria-label="Tree title"
          size={Math.max(title.length, 10)}
        />
        <div className="switcher" ref={verMenuRef}>
          <button
            className="switcher-btn"
            style={{ padding: "3px 8px" }}
            onClick={() => setVersionsOpen((o) => !o)}
            aria-expanded={versionsOpen}
          >
            <span className="version-pill">v{tree.version}</span>
            <span className="chev">▾</span>
          </button>
          {versionsOpen && (
            <div className="switcher-menu">
              <div className="menu-head">Versions</div>
              {versions.map((v) => (
                <button
                  key={v.id}
                  className="menu-item"
                  onClick={() => {
                    setVersionsOpen(false);
                    if (v.id !== tree.id) router.push(`/trees/${v.id}`);
                  }}
                >
                  <span className="grow">
                    v{v.version}
                    <span className="faint" style={{ marginLeft: 8, fontSize: 12 }}>
                      {new Date(v.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </span>
                  {v.is_main && <span className="live-pill">employees</span>}
                  {v.id === tree.id && <span className="check">●</span>}
                </button>
              ))}
            </div>
          )}
        </div>
        {tree.is_main ? (
          <span className="live-pill">● live for employees</span>
        ) : (
          <button className="btn" disabled={versionBusy} onClick={makeMain}>
            Use for employees
          </button>
        )}
        <span style={{ flex: 1 }} />
        <button
          className={`btn ${confirmDelete ? "btn-danger" : "btn-danger-ghost"}`}
          disabled={versions.length < 2 || versionBusy}
          title={
            versions.length < 2
              ? "The only version cannot be deleted"
              : "Delete this version (sessions and calls recorded against it are removed too)"
          }
          onClick={() => (confirmDelete ? removeVersion() : setConfirmDelete(true))}
          onBlur={() => setConfirmDelete(false)}
        >
          {confirmDelete ? "Confirm delete" : "Delete version"}
        </button>
      </div>
      {versionError && (
        <p className="error-text" style={{ margin: "6px 0 0" }}>
          {versionError}
        </p>
      )}
      <div className="stat-strip">
        <span className="stat-chip">
          <span className="tv-badge question" /> {counts.question} questions
        </span>
        <span className="stat-chip">
          <span className="tv-badge action" /> {counts.action} actions
        </span>
        <span className="stat-chip">
          <span className="tv-badge end" /> {counts.end} outcomes
        </span>
        <span style={{ flex: 1 }} />
        <button
          className="btn btn-ghost"
          onClick={() =>
            mutate((s) => {
              const id = freshId(s);
              s.nodes[id] = {
                id,
                type: "end",
                label: "New step",
                prompt: "",
                options: [],
              };
              setSelected(id);
            })
          }
        >
          + Add node
        </button>
      </div>

      <div className="browse-grid">
        <TreeViewer
          structure={draft}
          selectedId={selected ?? undefined}
          onNodeClick={setSelected}
        />

        <aside className="detail">
          {!node ? (
            <div className="detail-empty">Select a node to inspect and edit it.</div>
          ) : (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <span className={`type-badge ${node.type}`}>{node.type}</span>
                <span className="mono faint">{node.id}</span>
                {node.id === draft.root_id && (
                  <span className="version-pill">root</span>
                )}
                <span style={{ flex: 1 }} />
                <button
                  className="btn btn-danger-ghost"
                  disabled={
                    node.id === draft.root_id || referencedBy(node.id).length > 0
                  }
                  title={
                    node.id === draft.root_id
                      ? "The root node cannot be deleted"
                      : referencedBy(node.id).length > 0
                        ? `Still referenced by ${referencedBy(node.id)
                            .map((n) => n.id)
                            .join(", ")}`
                        : "Delete this node"
                  }
                  onClick={() =>
                    mutate((s) => {
                      delete s.nodes[node.id];
                      setSelected(s.root_id);
                    })
                  }
                >
                  Delete
                </button>
              </div>

              <div style={{ marginBottom: 14 }}>
                <label className="label">Type</label>
                <select
                  className="select"
                  value={node.type}
                  onChange={(e) =>
                    mutate((s) => {
                      const n = s.nodes[node.id];
                      n.type = e.target.value as NodeType;
                      if (n.type === "end") n.options = [];
                      if (n.type === "action" && n.options.length > 1)
                        n.options = n.options.slice(0, 1);
                    })
                  }
                >
                  <option value="question">question, operator picks a branch</option>
                  <option value="action">action, do it then continue</option>
                  <option value="end">end, call outcome</option>
                </select>
              </div>

              <div style={{ marginBottom: 14 }}>
                <label className="label">Label</label>
                <input
                  className="input"
                  value={node.label}
                  onChange={(e) =>
                    mutate((s) => {
                      s.nodes[node.id].label = e.target.value;
                    })
                  }
                />
              </div>

              <div style={{ marginBottom: 14 }}>
                <label className="label">Prompt, read aloud by the operator</label>
                <textarea
                  className="textarea"
                  value={node.prompt}
                  onChange={(e) =>
                    mutate((s) => {
                      s.nodes[node.id].prompt = e.target.value;
                    })
                  }
                />
              </div>

              {node.type !== "end" && (
                <div>
                  <label className="label">
                    {node.type === "question" ? "Options" : "Next step"}
                  </label>
                  {node.options.map((opt, i) => (
                    <div className="opt-row" key={i}>
                      <input
                        className="input"
                        value={opt.label}
                        placeholder="Option label"
                        onChange={(e) =>
                          mutate((s) => {
                            s.nodes[node.id].options[i].label = e.target.value;
                          })
                        }
                      />
                      <select
                        className="select"
                        value={opt.next_id}
                        onChange={(e) =>
                          mutate((s) => {
                            s.nodes[node.id].options[i].next_id = e.target.value;
                          })
                        }
                      >
                        {Object.values(draft.nodes)
                          .filter((n) => n.id !== node.id)
                          .map((n) => (
                            <option key={n.id} value={n.id}>
                              {n.id} · {n.label}
                            </option>
                          ))}
                        {!draft.nodes[opt.next_id] && (
                          <option value={opt.next_id}>
                            {opt.next_id} (missing)
                          </option>
                        )}
                      </select>
                      <button
                        className="icon-btn"
                        title="Remove option"
                        onClick={() =>
                          mutate((s) => {
                            s.nodes[node.id].options.splice(i, 1);
                          })
                        }
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  {(node.type === "question" || node.options.length === 0) && (
                    <button
                      className="btn btn-ghost"
                      onClick={() =>
                        mutate((s) => {
                          const targets = Object.keys(s.nodes).filter(
                            (id) => id !== node.id
                          );
                          s.nodes[node.id].options.push({
                            label: node.type === "action" ? "Continue" : "",
                            next_id: targets[0] ?? node.id,
                          });
                        })
                      }
                    >
                      + Add option
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </aside>
      </div>

      {dirty && (
        <div className="savebar">
          {violations.length > 0 ? (
            <span className="error-text">
              {violations.length} issue{violations.length > 1 ? "s" : ""}: {violations[0]}
            </span>
          ) : (
            <span className="muted">Unsaved changes</span>
          )}
          {saveError && <span className="error-text">{saveError}</span>}
          <button
            className="btn btn-ghost"
            onClick={() => {
              setDraft(structuredClone(tree.structure));
              setTitle(tree.title);
              setSaveError(null);
            }}
          >
            Discard
          </button>
          <button
            className="btn btn-primary"
            disabled={violations.length > 0 || saving}
            onClick={save}
          >
            {saving ? "Saving" : `Save as v${tree.version + 1}`}
          </button>
        </div>
      )}
    </div>
  );
}
