"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listTrees } from "@/lib/api";
import UploadCard from "@/components/UploadCard";

/**
 * Entry point. No trees yet: explain the product in three lines and take a
 * procedure document. Trees exist: go straight to the workspace (last used
 * tree if known, otherwise the most recent one).
 */
export default function HomePage() {
  const router = useRouter();
  const [state, setState] = useState<"loading" | "empty" | "offline">("loading");

  useEffect(() => {
    let cancelled = false;
    listTrees()
      .then((trees) => {
        if (cancelled) return;
        if (trees.length === 0) {
          setState("empty");
          return;
        }
        const last = localStorage.getItem("calltree:last");
        const target = trees.find((t) => t.id === last) ??
          [...trees].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
        router.replace(`/trees/${target.id}/guide`);
      })
      .catch(() => !cancelled && setState("offline"));
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (state === "loading") {
    return (
      <div className="page-loading">
        <span className="spinner" /> Loading
      </div>
    );
  }

  return (
    <div className="container-narrow landing">
      <div className="eyebrow">Call guidance for support and dispatch teams</div>
      <h1 className="hero-title">
        Your procedure, turned into a decision tree your operators follow live.
      </h1>
      <p className="hero-sub">
        Upload a call procedure. CallTree extracts a decision tree from it,
        walks operators through it step by step during calls, and audits
        recordings against the same tree.
      </p>

      {state === "offline" && (
        <p className="error-text" style={{ marginBottom: 16 }}>
          Backend unreachable at {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}.
          Start it with npm run dev, then reload.
        </p>
      )}

      <UploadCard />

      <div className="steps">
        <div className="step">
          <div className="num">01</div>
          <div className="name">Upload</div>
          <div className="desc">A procedure document. PDF, TXT or MD.</div>
        </div>
        <div className="step">
          <div className="num">02</div>
          <div className="name">Review</div>
          <div className="desc">Inspect the generated tree, edit wording and branches.</div>
        </div>
        <div className="step">
          <div className="num">03</div>
          <div className="name">Operate</div>
          <div className="desc">Guide live calls. Audit recordings against the tree.</div>
        </div>
      </div>
    </div>
  );
}
