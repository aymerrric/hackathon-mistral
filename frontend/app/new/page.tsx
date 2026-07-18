"use client";

import UploadCard from "@/components/UploadCard";

/** Add a tree from a new procedure document. Reached from the tree switcher. */
export default function NewTreePage() {
  return (
    <div className="container-narrow" style={{ paddingTop: 48 }}>
      <div className="eyebrow">New tree</div>
      <h1 className="hero-title" style={{ fontSize: 26 }}>
        Add a procedure
      </h1>
      <p className="hero-sub">
        The document is converted into a new decision tree. Existing trees are
        not affected.
      </p>
      <UploadCard />
    </div>
  );
}
