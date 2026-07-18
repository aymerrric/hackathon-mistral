"use client";

/**
 * Tree view page — inspect (and lightly edit) the ground-truth tree.
 * TO IMPLEMENT.
 *
 * Spec:
 *  - Load api.getTree(params.treeId); render <TreeViewer structure={...} />.
 *  - Header: tree title, version badge, spec name, buttons:
 *      "Guide a call"      -> /trees/<id>/guide
 *      "Audit a recording" -> /trees/<id>/audit
 *  - Stretch goal (only if time permits): click a node to edit its prompt
 *    text in a side panel, then api.updateTree() (creates a new version —
 *    navigate to the returned tree id).
 */
export default function TreePage({ params }: { params: { treeId: string } }) {
  return <p>TODO: implement tree view for {params.treeId}</p>;
}
