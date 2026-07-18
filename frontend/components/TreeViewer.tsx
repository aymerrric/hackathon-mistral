"use client";

import { useState } from "react";
import type { TreeStructure } from "@/lib/types";

/**
 * Outline rendering of a decision tree, from root_id down.
 * Trees are DAGs in practice: a node reached through a second branch renders
 * as a stub link instead of recursing forever. Nodes not reachable from the
 * root (possible mid-edit) are listed at the bottom under "Unlinked".
 */
export interface TreeViewerProps {
  structure: TreeStructure;
  highlightPath?: string[];
  verdictByNode?: Record<string, "followed" | "deviated" | "skipped">;
  onNodeClick?: (nodeId: string) => void;
  selectedId?: string;
}

export default function TreeViewer({
  structure,
  highlightPath,
  verdictByNode,
  onNodeClick,
  selectedId,
}: TreeViewerProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const onPath = new Set(highlightPath ?? []);

  function toggle(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function renderNode(id: string, seen: Set<string>): JSX.Element {
    const node = structure.nodes[id];
    if (!node) {
      return (
        <div key={`missing-${id}`} className="tv-stub" style={{ color: "var(--bad)" }}>
          ↪ {id} (missing node)
        </div>
      );
    }
    if (seen.has(id)) {
      return (
        <div
          key={`stub-${id}-${seen.size}`}
          className="tv-stub"
          onClick={() => onNodeClick?.(id)}
        >
          ↪ {id} {node.label}
        </div>
      );
    }
    const nextSeen = new Set(seen).add(id);
    const isCollapsed = collapsed.has(id);
    const verdict = verdictByNode?.[id];
    const classes = [
      "tv-row",
      selectedId === id ? "selected" : "",
      verdict ? `v-${verdict}` : "",
      onPath.has(id) ? "on-path" : "",
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <div key={id}>
        <div className={classes} onClick={() => onNodeClick?.(id)}>
          <button
            className={`tv-caret ${node.options.length === 0 ? "leaf" : ""}`}
            onClick={(e) => {
              e.stopPropagation();
              toggle(id);
            }}
            aria-label={isCollapsed ? "Expand" : "Collapse"}
          >
            {isCollapsed ? "▶" : "▼"}
          </button>
          <span className={`tv-badge ${node.type}`} />
          <span className="tv-label">{node.label}</span>
          <span className="tv-id">{node.id}</span>
        </div>
        {!isCollapsed && node.options.length > 0 && (
          <div className="tv-children">
            {node.options.map((opt, i) => (
              <div key={`${id}-opt-${i}`}>
                {node.type === "question" && (
                  <div className="tv-edge">{opt.label}</div>
                )}
                {renderNode(opt.next_id, nextSeen)}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Nodes unreachable from the root (can appear while editing).
  const reachable = new Set<string>();
  const stack = [structure.root_id];
  while (stack.length) {
    const id = stack.pop()!;
    if (reachable.has(id) || !structure.nodes[id]) continue;
    reachable.add(id);
    for (const o of structure.nodes[id].options) stack.push(o.next_id);
  }
  const unlinked = Object.keys(structure.nodes).filter((id) => !reachable.has(id));

  return (
    <div>
      {renderNode(structure.root_id, new Set())}
      {unlinked.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="menu-head">Unlinked</div>
          {unlinked.map((id) => renderNode(id, new Set(reachable)))}
        </div>
      )}
    </div>
  );
}
