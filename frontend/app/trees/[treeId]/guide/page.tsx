"use client";

/**
 * Guided call page — the employee-facing flow used DURING a live call.
 * TO IMPLEMENT. This is the demo centerpiece: keep it big, calm, obvious.
 *
 * Spec:
 *  - On mount: api.getTree(treeId). Before starting, ask for the agent's
 *    name (small form) then api.createSession(treeId, name).
 *  - Render <GuidePanel/> with the current node (session.current_node_id):
 *      * node.prompt in large text ("say this"),
 *      * one big button per option; clicking calls api.takeStep(session.id,
 *        nodeId, optionIndex) and re-renders with the response,
 *      * action nodes show a single "Done — continue" button,
 *      * end nodes show the closing prompt + a "Finish call" button that
 *        calls api.finishSession() and shows a "Call completed" state with
 *        the breadcrumb of the path taken.
 *  - Breadcrumb of past steps (labels of visited nodes) always visible.
 *  - A "Back" affordance is OUT OF SCOPE (the backend path is append-only).
 */
export default function GuidePage({ params }: { params: { treeId: string } }) {
  return <p>TODO: implement guided mode for tree {params.treeId}</p>;
}
