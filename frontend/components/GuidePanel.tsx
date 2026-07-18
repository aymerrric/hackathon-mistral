"use client";

import type { TreeNode } from "@/lib/types";

/**
 * The current step during a live call. The prompt is what the operator says
 * out loud; options advance the session. Number keys are bound by the page.
 */
export interface GuidePanelProps {
  node: TreeNode;
  busy: boolean;
  onChoose: (optionIndex: number) => void;
}

const KICKER: Record<TreeNode["type"], string> = {
  question: "Ask",
  action: "Do",
  end: "Close",
};

export default function GuidePanel({ node, busy, onChoose }: GuidePanelProps) {
  return (
    <div className="node-card">
      <div className="node-kicker">
        {node.type === "end" ? (
          <span className="end-banner">Outcome reached</span>
        ) : (
          <>
            <span className={`tv-badge ${node.type}`} />
            {KICKER[node.type]} · {node.label}
          </>
        )}
      </div>

      <p className="node-prompt">{node.prompt}</p>

      {node.type === "question" && (
        <div className="options">
          {node.options.map((opt, i) => (
            <button
              key={i}
              className="option-btn"
              disabled={busy}
              onClick={() => onChoose(i)}
            >
              <span className="option-key">{i + 1}</span>
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {node.type === "action" && (
        <div className="options">
          <button
            className="option-btn"
            disabled={busy}
            onClick={() => onChoose(0)}
          >
            <span className="option-key">↵</span>
            Done, continue
          </button>
        </div>
      )}
    </div>
  );
}
