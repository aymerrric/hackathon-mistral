/**
 * Typed API client — the ONLY place the frontend talks to the backend.
 * Base URL comes from process.env.NEXT_PUBLIC_API_URL.
 * On non-2xx, throws Error(`${status}: ${body}`) so pages can show the
 * FastAPI error detail.
 */

import type {
  Call,
  CallAnalysis,
  ChatMessage,
  GuidanceSession,
  Spec,
  Tree,
  TreeStructure,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// --- Specs -----------------------------------------------------------------

/** POST /api/specs — multipart: name + file (.pdf/.txt/.md). */
export async function uploadSpec(name: string, file: File): Promise<Spec> {
  const form = new FormData();
  form.append("name", name);
  form.append("file", file);
  return req<Spec>("/api/specs", { method: "POST", body: form });
}

/** GET /api/specs */
export async function listSpecs(): Promise<Spec[]> {
  return req<Spec[]>("/api/specs");
}

/** POST /api/specs/{id}/generate-tree — slow (~10-30s), show a spinner. */
export async function generateTree(specId: string): Promise<Tree> {
  return req<Tree>(`/api/specs/${specId}/generate-tree`, { method: "POST" });
}

// --- Trees -----------------------------------------------------------------

/** GET /api/trees */
export async function listTrees(): Promise<Tree[]> {
  return req<Tree[]>("/api/trees");
}

/** GET /api/trees/{id} */
export async function getTree(treeId: string): Promise<Tree> {
  return req<Tree>(`/api/trees/${treeId}`);
}

/** PUT /api/trees/{id} — saves as a new version. */
export async function updateTree(
  treeId: string,
  structure: TreeStructure,
  title?: string
): Promise<Tree> {
  return req<Tree>(`/api/trees/${treeId}`, json("PUT", { title, structure }));
}

/** POST /api/trees/{id}/select — make this version the employees' version. */
export async function selectTree(treeId: string): Promise<Tree> {
  return req<Tree>(`/api/trees/${treeId}/select`, { method: "POST" });
}

/** DELETE /api/trees/{id} — 409 if it is the only version of its spec. */
export async function deleteTree(treeId: string): Promise<void> {
  const res = await fetch(`${API}/api/trees/${treeId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

// --- Guidance sessions -----------------------------------------------------

/** POST /api/sessions */
export async function createSession(
  treeId: string,
  agentName: string
): Promise<GuidanceSession> {
  return req<GuidanceSession>(
    "/api/sessions",
    json("POST", { tree_id: treeId, agent_name: agentName })
  );
}

/** GET /api/sessions — all sessions, newest first. */
export async function listSessions(): Promise<GuidanceSession[]> {
  return req<GuidanceSession[]>("/api/sessions");
}

/** POST /api/sessions/{id}/step */
export async function takeStep(
  sessionId: string,
  nodeId: string,
  optionIndex: number
): Promise<GuidanceSession> {
  return req<GuidanceSession>(
    `/api/sessions/${sessionId}/step`,
    json("POST", { node_id: nodeId, option_index: optionIndex })
  );
}

/** POST /api/sessions/{id}/finish — completed if at an end node, else abandoned. */
export async function finishSession(sessionId: string): Promise<GuidanceSession> {
  return req<GuidanceSession>(`/api/sessions/${sessionId}/finish`, {
    method: "POST",
  });
}

// --- Assist (operator copilot) ---------------------------------------------

/** POST /api/assist — short grounded answer about the procedure. */
export async function assist(
  treeId: string,
  messages: ChatMessage[],
  nodeId?: string
): Promise<string> {
  const out = await req<{ reply: string }>(
    "/api/assist",
    json("POST", { tree_id: treeId, node_id: nodeId ?? null, messages })
  );
  return out.reply;
}

// --- Calls & analysis ------------------------------------------------------

/** POST /api/calls — multipart: tree_id + audio file. Slow (transcription). */
export async function uploadCall(treeId: string, file: File): Promise<Call> {
  const form = new FormData();
  form.append("tree_id", treeId);
  form.append("file", file);
  return req<Call>("/api/calls", { method: "POST", body: form });
}

/** GET /api/calls/{id} */
export async function getCall(callId: string): Promise<Call> {
  return req<Call>(`/api/calls/${callId}`);
}

/** POST /api/calls/{id}/analyze — slow (~10-30s), show a spinner. */
export async function analyzeCall(callId: string): Promise<CallAnalysis> {
  return req<CallAnalysis>(`/api/calls/${callId}/analyze`, { method: "POST" });
}

/** GET /api/calls/{id}/analysis — latest analysis, 404 if never analyzed. */
export async function getAnalysis(callId: string): Promise<CallAnalysis> {
  return req<CallAnalysis>(`/api/calls/${callId}/analysis`);
}
