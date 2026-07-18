"use client";

import { useEffect, useRef, useState } from "react";
import { assist } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

/**
 * Quiet copilot input fixed at the bottom of guide mode. One thin bar;
 * answers open in a small panel above it and stay out of the way of the
 * step card. Answers are grounded in the active tree by the backend.
 */
export default function AssistBar({
  treeId,
  nodeId,
}: {
  treeId: string;
  nodeId?: string;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.scrollTo({ top: panelRef.current.scrollHeight });
  }, [messages, pending]);

  async function send() {
    const text = input.trim();
    if (!text || pending) return;
    const history: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(history);
    setInput("");
    setError(null);
    setHidden(false);
    setPending(true);
    try {
      const reply = await assist(treeId, history, nodeId);
      setMessages([...history, { role: "assistant", content: reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  }

  const showPanel = !hidden && (messages.length > 0 || error);

  return (
    <div className="assist-root">
      <div className="assist-inner">
        {showPanel && (
          <div className="assist-panel" ref={panelRef}>
            {messages.map((m, i) => (
              <div key={i} className={`assist-msg ${m.role}`}>
                {m.content}
              </div>
            ))}
            {pending && (
              <div className="assist-msg assistant">
                <span className="spinner" />
              </div>
            )}
            {error && <div className="error-text">{error}</div>}
            <button
              className="btn btn-ghost"
              style={{ alignSelf: "flex-end", padding: "2px 8px", fontSize: 12 }}
              onClick={() => setHidden(true)}
            >
              Hide
            </button>
          </div>
        )}
        <div className="assist-bar">
          <input
            placeholder="Ask about this procedure"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={() => setHidden(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
              if (e.key === "Escape") (e.target as HTMLInputElement).blur();
            }}
          />
          <button
            className="assist-send"
            disabled={!input.trim() || pending}
            onClick={send}
          >
            Ask
          </button>
        </div>
      </div>
    </div>
  );
}
