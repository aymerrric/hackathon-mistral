"use client";

import { useMemo } from "react";
import type { GuidanceSession, TreeStructure } from "@/lib/types";

/**
 * Vertical node-link diagram of the decision tree with call-traffic
 * overlaid: root at the top, layers flowing down. Nodes show how many calls
 * reached them; each edge's thickness, color and % label show the share of
 * calls that took that branch. Never-taken branches stay thin and dashed,
 * so the important routes stand out.
 *
 * Counts are per call (a call revisiting a node in a loop counts once).
 * Path entries that do not resolve in this tree version are ignored.
 */

const BOX_W = 176;
const BOX_H = 48;
const SIB_GAP = 26; // horizontal gap between nodes in a layer
const LAYER_GAP = 88; // vertical gap between layers (room for % labels)
const PAD = 28;

interface Placed {
  id: string;
  x: number;
  y: number;
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export default function FlowTree({
  structure,
  sessions,
}: {
  structure: TreeStructure;
  sessions: GuidanceSession[];
}) {
  const { placed, edges, nodeCount, total, width, height } = useMemo(() => {
    const total = sessions.length;

    // Per-call traversal counts (dedupe within a session).
    const nodeCount = new Map<string, number>();
    const edgeCount = new Map<string, number>();
    for (const s of sessions) {
      const nodesSeen = new Set<string>();
      const edgesSeen = new Set<string>();
      for (const p of s.path) {
        const node = structure.nodes[p.node_id];
        if (!node || !node.options[p.option_index]) continue;
        nodesSeen.add(p.node_id);
        edgesSeen.add(`${p.node_id}#${p.option_index}`);
      }
      if (structure.nodes[s.current_node_id]) nodesSeen.add(s.current_node_id);
      for (const id of nodesSeen) nodeCount.set(id, (nodeCount.get(id) ?? 0) + 1);
      for (const k of edgesSeen) edgeCount.set(k, (edgeCount.get(k) ?? 0) + 1);
    }

    // Layer nodes by shortest distance from the root (BFS).
    const depth = new Map<string, number>();
    const queue = [structure.root_id];
    depth.set(structure.root_id, 0);
    while (queue.length) {
      const id = queue.shift()!;
      const node = structure.nodes[id];
      if (!node) continue;
      for (const opt of node.options) {
        if (!depth.has(opt.next_id) && structure.nodes[opt.next_id]) {
          depth.set(opt.next_id, depth.get(id)! + 1);
          queue.push(opt.next_id);
        }
      }
    }

    // Order within a layer = DFS preorder, keeps sibling branches together.
    const order: string[] = [];
    const seen = new Set<string>();
    const dfs = (id: string) => {
      if (seen.has(id) || !structure.nodes[id]) return;
      seen.add(id);
      order.push(id);
      for (const opt of structure.nodes[id].options) dfs(opt.next_id);
    };
    dfs(structure.root_id);

    const layers = new Map<number, string[]>();
    for (const id of order) {
      const d = depth.get(id)!;
      layers.set(d, [...(layers.get(d) ?? []), id]);
    }

    const maxCols = Math.max(...[...layers.values()].map((l) => l.length), 1);
    const maxDepth = Math.max(...layers.keys(), 0);
    const width = maxCols * (BOX_W + SIB_GAP) - SIB_GAP + PAD * 2;
    const height = (maxDepth + 1) * (BOX_H + LAYER_GAP) - LAYER_GAP + PAD * 2;

    const placed: Placed[] = [];
    const pos = new Map<string, Placed>();
    for (const [d, ids] of layers) {
      const rowW = ids.length * (BOX_W + SIB_GAP) - SIB_GAP;
      ids.forEach((id, i) => {
        const p = {
          id,
          x: PAD + (width - PAD * 2 - rowW) / 2 + i * (BOX_W + SIB_GAP),
          y: PAD + d * (BOX_H + LAYER_GAP),
        };
        placed.push(p);
        pos.set(id, p);
      });
    }

    const maxEdge = Math.max(...edgeCount.values(), 1);
    const edges = order.flatMap((id) => {
      const node = structure.nodes[id];
      return node.options
        .map((opt, i) => {
          const from = pos.get(id);
          const to = pos.get(opt.next_id);
          if (!from || !to) return null;
          const count = edgeCount.get(`${id}#${i}`) ?? 0;
          return { from, to, count, optIndex: i, optCount: node.options.length, maxEdge };
        })
        .filter((e): e is NonNullable<typeof e> => e !== null);
    });

    return { placed, edges, nodeCount, total, width, height };
  }, [structure, sessions]);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: "block", minWidth: width, margin: "0 auto" }}
      role="img"
      aria-label="Call flow diagram"
    >
      {/* Edges under nodes */}
      {edges.map((e, idx) => {
        // Fan multiple options out across the bottom edge of the parent.
        const spread = (e.optIndex - (e.optCount - 1) / 2) * 26;
        const sx = e.from.x + BOX_W / 2 + spread;
        const sy = e.from.y + BOX_H;
        const tx = e.to.x + BOX_W / 2;
        const ty = e.to.y;
        const backward = ty <= sy;
        const d = backward
          ? `M ${sx} ${sy} C ${sx + 90} ${sy + 60}, ${tx + 90} ${ty - 60}, ${tx} ${ty}`
          : `M ${sx} ${sy} C ${sx} ${sy + LAYER_GAP / 2}, ${tx} ${ty - LAYER_GAP / 2}, ${tx} ${ty}`;
        const share = total ? e.count / total : 0;
        const taken = e.count > 0;
        const strokeW = taken ? 1.5 + 5 * (e.count / e.maxEdge) : 1;
        const midX = backward ? Math.max(sx, tx) + 82 : (sx + tx) / 2;
        const midY = backward ? (sy + ty) / 2 : (sy + ty) / 2 + 4;
        return (
          <g key={idx}>
            <path
              d={d}
              fill="none"
              stroke={taken ? "var(--accent)" : "var(--border-strong)"}
              strokeOpacity={taken ? 0.35 + 0.65 * (e.count / e.maxEdge) : 0.6}
              strokeWidth={strokeW}
              strokeDasharray={taken ? undefined : "4 4"}
            />
            {taken && (
              <text
                x={midX}
                y={midY}
                textAnchor="middle"
                fontSize={10.5}
                fontFamily="var(--mono)"
                fill="var(--text)"
                stroke="var(--bg)"
                strokeWidth={3}
                paintOrder="stroke"
              >
                {Math.round(share * 100)}%
              </text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {placed.map((p) => {
        const node = structure.nodes[p.id];
        const count = nodeCount.get(p.id) ?? 0;
        const pct = total ? Math.round((100 * count) / total) : 0;
        const isRoot = p.id === structure.root_id;
        const stroke =
          node.type === "end"
            ? "var(--ok)"
            : isRoot
              ? "var(--accent)"
              : "var(--border-strong)";
        return (
          <g key={p.id} opacity={count > 0 || total === 0 ? 1 : 0.45}>
            <rect
              x={p.x}
              y={p.y}
              width={BOX_W}
              height={BOX_H}
              rx={9}
              fill="var(--panel)"
              stroke={stroke}
              strokeWidth={node.type === "end" || isRoot ? 1.5 : 1}
            />
            <text
              x={p.x + 12}
              y={p.y + 20}
              fontSize={12}
              fontWeight={600}
              fill="var(--text)"
            >
              {truncate(node.label, 24)}
            </text>
            <text
              x={p.x + 12}
              y={p.y + 36}
              fontSize={10.5}
              fontFamily="var(--mono)"
              fill={count > 0 ? "var(--text-dim)" : "var(--text-faint)"}
            >
              {total === 0 ? node.id : `${count} calls · ${pct}%`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
