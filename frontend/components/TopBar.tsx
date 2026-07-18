"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { listTrees } from "@/lib/api";
import type { Tree } from "@/lib/types";

/**
 * Top navigation: wordmark, tree switcher (account-switcher style dropdown,
 * one entry per spec at its latest version, plus "New tree"), and the
 * Guide / Tree mode tabs when a tree is open.
 */
export default function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [trees, setTrees] = useState<Tree[]>([]);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const match = pathname.match(/^\/trees\/([^/]+)/);
  const treeId = match?.[1] ?? null;
  const inGuide = pathname.endsWith("/guide");

  useEffect(() => {
    listTrees()
      .then(setTrees)
      .catch(() => setTrees([]));
  }, [pathname]);

  useEffect(() => {
    if (treeId) localStorage.setItem("calltree:last", treeId);
  }, [treeId]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Latest version per spec, newest spec first.
  const latest = new Map<string, Tree>();
  for (const t of trees) {
    const cur = latest.get(t.spec_id);
    if (!cur || t.version > cur.version) latest.set(t.spec_id, t);
  }
  const entries = [...latest.values()].sort((a, b) =>
    b.created_at.localeCompare(a.created_at)
  );

  const current = treeId ? trees.find((t) => t.id === treeId) : null;

  const switchTo = useCallback(
    (id: string) => {
      setOpen(false);
      router.push(`/trees/${id}${inGuide ? "/guide" : ""}`);
    },
    [router, inGuide]
  );

  return (
    <header className="topbar">
      <a className="wordmark" href="/">
        <span className="wordmark-dot" />
        CallTree
      </a>

      {entries.length > 0 && (
        <>
          <span className="topbar-sep" />
          <div className="switcher" ref={menuRef}>
            <button
              className="switcher-btn"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
            >
              <span className="title">
                {current ? current.title : "Select a tree"}
              </span>
              {current && (
                <span className="version-pill">v{current.version}</span>
              )}
              <span className="chev">▾</span>
            </button>
            {open && (
              <div className="switcher-menu">
                <div className="menu-head">Trees</div>
                {entries.map((t) => (
                  <button
                    key={t.id}
                    className="menu-item"
                    onClick={() => switchTo(t.id)}
                  >
                    <span className="grow">{t.title}</span>
                    <span className="version-pill">v{t.version}</span>
                    {current?.spec_id === t.spec_id && (
                      <span className="check">●</span>
                    )}
                  </button>
                ))}
                <button
                  className="menu-item new"
                  onClick={() => {
                    setOpen(false);
                    router.push("/new");
                  }}
                >
                  + New tree
                </button>
              </div>
            )}
          </div>
        </>
      )}

      <span style={{ flex: 1 }} />

      {treeId && (
        <nav className="mode-tabs" aria-label="Mode">
          <button
            className={`tab ${inGuide ? "active" : ""}`}
            onClick={() => router.push(`/trees/${treeId}/guide`)}
          >
            Guide
          </button>
          <button
            className={`tab ${!inGuide ? "active" : ""}`}
            onClick={() => router.push(`/trees/${treeId}`)}
          >
            Tree
          </button>
        </nav>
      )}
    </header>
  );
}
