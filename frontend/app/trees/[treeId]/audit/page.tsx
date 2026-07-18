"use client";

/**
 * Call audit page — upload a recording of a past call and judge it against
 * this tree. TO IMPLEMENT.
 *
 * Spec:
 *  - <AudioUploader/>: file input (.mp3/.wav/.m4a) + "Upload & transcribe"
 *    button -> api.uploadCall(treeId, file). Show a spinner ("Transcribing
 *    with Voxtral…"); this request is slow.
 *  - When the Call comes back with a transcript, show the transcript
 *    (speaker-labelled turns with timestamps) and an "Analyze call" button
 *    -> api.analyzeCall(call.id), spinner ("Judging against the tree…").
 *  - Render the result with <CallReport analysis={...} tree={...}
 *    transcript={...} />.
 *  - Keep call id in the URL query (?call=<id>) so a refresh can re-fetch
 *    via api.getCall / api.getAnalysis instead of losing state.
 */
export default function AuditPage({ params }: { params: { treeId: string } }) {
  return <p>TODO: implement audit flow for tree {params.treeId}</p>;
}
