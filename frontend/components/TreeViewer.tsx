"use client";

import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { TreeStructure } from "@/lib/types";

/**
 * Interactive graph rendering of a decision tree: node cards laid out
 * top-down, SVG edges carrying the option labels, pan (drag) and zoom
 * (scroll / buttons), click to select.
 *
 * Trees are DAGs in practice: the layout uses the first-visit spanning tree
 * from root_id; any edge that reaches an already-placed node is drawn as a
 * dashed cross-link back to it instead of duplicating the subtree. Nodes
 * unreachable from the root (possible mid-edit) are laid out to the right
 * with a dashed border. Options pointing to a missing node render a red
 * "missing" leaf so validation problems stay visible.
 */
export interface TreeViewerProps {
  structure: TreeStructure;
  highlightPath?: string[];
  verdictByNode?: Record<string, "followed" | "deviated" | "skipped">;
  onNodeClick?: (nodeId: string) => void;
  selectedId?: string;
}

const NODE_W = 200;
const NODE_H = 72;
const GAP_X = 30;
const GAP_Y = 64;
const ROW_H = NODE_H + GAP_Y;

interface PlacedNode {
  key: string; // unique render key (real node id, or synthetic for missing)
  id: string; // node id it represents / points to
  x: number;
  y: number;
  missing?: boolean;
  unlinked?: boolean;
}

interface EdgeSpec {
  fromKey: string;
  toKey: string;
  fromId: string;
  toId: string;
  label?: string;
  kind: "tree" | "link";
}

interface Layout {
  nodes: PlacedNode[];
  edges: EdgeSpec[];
  width: number;
  height: number;
}

function computeLayout(structure: TreeStructure): Layout {
  const defs = structure.nodes;
  const placed: PlacedNode[] = [];
  const posByKey = new Map<string, { x: number; y: number }>();
  const edges: EdgeSpec[] = [];
  const visited = new Set<string>();

  function put(node: PlacedNode) {
    placed.push(node);
    posByKey.set(node.key, { x: node.x, y: node.y });
  }

  // Places the first-visit subtree of `id`, returns its width.
  function place(id: string, depth: number, x0: number, unlinked: boolean): number {
    const node = defs[id];
    visited.add(id);
    const childCenters: number[] = [];
    let cursor = x0;

    for (let i = 0; i < node.options.length; i++) {
      const opt = node.options[i];
      const label = node.type === "question" ? opt.label : undefined;
      const target = opt.next_id;
      if (!defs[target]) {
        const key = `missing:${id}:${i}`;
        put({ key, id: target, x: cursor, y: (depth + 1) * ROW_H, missing: true, unlinked });
        edges.push({ fromKey: id, toKey: key, fromId: id, toId: target, label, kind: "tree" });
        childCenters.push(cursor + NODE_W / 2);
        cursor += NODE_W + GAP_X;
      } else if (!visited.has(target)) {
        const w = place(target, depth + 1, cursor, unlinked);
        childCenters.push(posByKey.get(target)!.x + NODE_W / 2);
        edges.push({ fromKey: id, toKey: target, fromId: id, toId: target, label, kind: "tree" });
        cursor += w + GAP_X;
      } else {
        edges.push({ fromKey: id, toKey: target, fromId: id, toId: target, label, kind: "link" });
      }
    }

    const childSpan = cursor - x0 - (childCenters.length ? GAP_X : 0);
    const x = childCenters.length
      ? (childCenters[0] + childCenters[childCenters.length - 1]) / 2 - NODE_W / 2
      : x0;
    put({ key: id, id, x, y: depth * ROW_H, unlinked });
    return Math.max(childSpan, NODE_W);
  }

  let cursorX = 0;
  if (defs[structure.root_id]) {
    cursorX = place(structure.root_id, 0, 0, false) + GAP_X * 2;
  }

  // Components unreachable from the root, laid out to the right.
  while (true) {
    const remaining = Object.keys(defs).filter((id) => !visited.has(id));
    if (remaining.length === 0) break;
    const referenced = new Set(
      remaining.flatMap((id) => defs[id].options.map((o) => o.next_id))
    );
    const root = remaining.find((id) => !referenced.has(id)) ?? remaining[0];
    cursorX += place(root, 0, cursorX, true) + GAP_X * 2;
  }

  let width = 0;
  let height = 0;
  for (const n of placed) {
    width = Math.max(width, n.x + NODE_W);
    height = Math.max(height, n.y + NODE_H);
  }
  return { nodes: placed, edges, width, height };
}

function edgePath(x1: number, y1: number, x2: number, y2: number): string {
  const bend = Math.max(36, Math.abs(y2 - y1) * 0.45);
  return `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}`;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export default function TreeViewer({
  structure,
  highlightPath,
  verdictByNode,
  onNodeClick,
  selectedId,
}: TreeViewerProps) {
  const layout = useMemo(() => computeLayout(structure), [structure]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const drag = useRef<{ px: number; py: number } | null>(null);

  const onPath = new Set(highlightPath ?? []);
  const pathEdges = new Set<string>();
  if (highlightPath) {
    for (let i = 0; i + 1 < highlightPath.length; i++) {
      pathEdges.add(`${highlightPath[i]}>${highlightPath[i + 1]}`);
    }
  }

  function fit() {
    const el = wrapRef.current;
    if (!el || layout.width === 0) return;
    const pad = 36;
    const k = clamp(
      Math.min(
        (el.clientWidth - pad * 2) / layout.width,
        (el.clientHeight - pad * 2) / layout.height
      ),
      0.2,
      1
    );
    setView({
      k,
      x: (el.clientWidth - layout.width * k) / 2,
      y: Math.max(pad, (el.clientHeight - layout.height * k) / 2),
    });
  }

  // Refit when the topology changes (not on every label keystroke).
  const topoKey = useMemo(
    () =>
      Object.values(structure.nodes)
        .map((n) => `${n.id}:${n.options.map((o) => o.next_id).join(",")}`)
        .sort()
        .join("|"),
    [structure]
  );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(fit, [topoKey]);

  // Native listener: React's onWheel is passive, preventDefault would warn.
  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      setView((v) => {
        const k = clamp(v.k * Math.exp(-e.deltaY * 0.0016), 0.15, 2.2);
        const f = k / v.k;
        return { k, x: mx - (mx - v.x) * f, y: my - (my - v.y) * f };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  function zoomBy(factor: number) {
    const el = wrapRef.current;
    if (!el) return;
    const mx = el.clientWidth / 2;
    const my = el.clientHeight / 2;
    setView((v) => {
      const k = clamp(v.k * factor, 0.15, 2.2);
      const f = k / v.k;
      return { k, x: mx - (mx - v.x) * f, y: my - (my - v.y) * f };
    });
  }

  function onPointerDown(e: ReactPointerEvent) {
    drag.current = { px: e.clientX, py: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: ReactPointerEvent) {
    if (!drag.current) return;
    const dx = e.clientX - drag.current.px;
    const dy = e.clientY - drag.current.py;
    drag.current.px = e.clientX;
    drag.current.py = e.clientY;
    setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }));
  }
  function onPointerUp() {
    drag.current = null;
  }

  const posByKey = new Map(layout.nodes.map((n) => [n.key, n]));

  return (
    <div
      ref={wrapRef}
      className="tree-canvas"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div
        className="tree-canvas-inner"
        style={{
          transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`,
        }}
      >
        <svg
          className="tree-edges"
          width={layout.width}
          height={layout.height}
          style={{ overflow: "visible" }}
        >
          {layout.edges.map((edge, i) => {
            const from = posByKey.get(edge.fromKey);
            const to = posByKey.get(edge.toKey);
            if (!from || !to) return null;
            const x1 = from.x + NODE_W / 2;
            const y1 = from.y + NODE_H;
            const x2 = to.x + NODE_W / 2;
            const y2 = to.y;
            const active = pathEdges.has(`${edge.fromId}>${edge.toId}`);
            return (
              <path
                key={i}
                d={edgePath(x1, y1, x2, y2)}
                className={`tree-edge ${edge.kind} ${active ? "on-path" : ""}`}
              />
            );
          })}
        </svg>

        {layout.edges.map((edge, i) => {
          if (!edge.label) return null;
          const from = posByKey.get(edge.fromKey);
          const to = posByKey.get(edge.toKey);
          if (!from || !to) return null;
          const mx = (from.x + to.x) / 2 + NODE_W / 2;
          const my = (from.y + NODE_H + to.y) / 2;
          const active = pathEdges.has(`${edge.fromId}>${edge.toId}`);
          return (
            <div
              key={`label-${i}`}
              className={`edge-label ${active ? "on-path" : ""} ${
                edge.kind === "link" ? "link" : ""
              }`}
              style={{ left: mx, top: my }}
              title={edge.label}
            >
              {edge.label || "—"}
            </div>
          );
        })}

        {layout.nodes.map((n) => {
          const def = structure.nodes[n.id];
          const verdict = verdictByNode?.[n.id];
          const classes = [
            "gnode",
            n.missing ? "missing" : def?.type ?? "",
            n.unlinked ? "unlinked" : "",
            selectedId === n.id && !n.missing ? "selected" : "",
            onPath.has(n.id) ? "on-path" : "",
            verdict ? `v-${verdict}` : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              key={n.key}
              className={classes}
              style={{ left: n.x, top: n.y, width: NODE_W, height: NODE_H }}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => !n.missing && onNodeClick?.(n.id)}
              title={n.missing ? `${n.id} — missing node` : def?.prompt || def?.label}
            >
              <span className="gnode-top">
                <span className={`tv-badge ${n.missing ? "missing" : def?.type}`} />
                <span className="gnode-type">{n.missing ? "missing" : def?.type}</span>
                <span className="gnode-id">{n.id}</span>
              </span>
              <span className="gnode-label">
                {n.missing ? "Broken link" : def?.label || "(untitled)"}
              </span>
            </button>
          );
        })}
      </div>

      <div className="tree-controls" onPointerDown={(e) => e.stopPropagation()}>
        <button className="tree-ctrl" onClick={() => zoomBy(1.25)} title="Zoom in">
          +
        </button>
        <button className="tree-ctrl" onClick={() => zoomBy(0.8)} title="Zoom out">
          −
        </button>
        <button className="tree-ctrl" onClick={fit} title="Fit to view">
          ⤢
        </button>
      </div>
      <div className="tree-hint">drag to pan · scroll to zoom</div>
    </div>
  );
}
