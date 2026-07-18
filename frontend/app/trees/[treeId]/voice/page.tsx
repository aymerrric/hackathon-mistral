"use client";

import { useEffect, useState } from "react";
import { getTree } from "@/lib/api";
import type { Tree } from "@/lib/types";
import VoiceAgent from "@/components/VoiceAgent";

/**
 * Voice mode: talk to the AI agent. The agent conducts the call — it follows
 * the tree rigorously (asks the questions, advances on your answers, helps
 * with side questions) while you play the caller. Sessions land in the Log
 * and finished conversations are stored as transcribed calls for Audit.
 */
export default function VoicePage({ params }: { params: { treeId: string } }) {
  const [tree, setTree] = useState<Tree | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTree(params.treeId)
      .then(setTree)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [params.treeId]);

  if (error) {
    return (
      <div className="container-narrow">
        <p className="error-text">{error}</p>
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

  return (
    <div className="container-narrow" style={{ paddingTop: 40 }}>
      <div className="eyebrow">
        {tree.title} · v{tree.version}
      </div>
      <h1 className="hero-title" style={{ fontSize: 26 }}>
        Talk to the AI agent
      </h1>
      <VoiceAgent tree={tree} />
    </div>
  );
}
