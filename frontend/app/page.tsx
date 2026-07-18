"use client";

/**
 * Home page — spec upload + tree list. TO IMPLEMENT.
 *
 * Spec:
 *  - "Upload a spec" card: name text input + file input (.pdf/.txt/.md) +
 *    submit. On submit: api.uploadSpec(), then api.generateTree(spec.id)
 *    with a "Generating tree…" spinner (10-30s), then router.push to
 *    /trees/<tree.id>.
 *  - Below, list of existing trees (api.listTrees()): title, version,
 *    created date; each row links to /trees/<id>. Each row also has two
 *    action links: "Guide a call" -> /trees/<id>/guide and "Audit a
 *    recording" -> /trees/<id>/audit.
 *  - Show API errors inline (red text), not with alert().
 */
export default function HomePage() {
  return <p>TODO: implement home page (see spec in this file)</p>;
}
