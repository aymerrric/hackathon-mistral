/**
 * Typed API client — the ONLY place the frontend talks to the backend.
 * Base URL comes from process.env.NEXT_PUBLIC_API_URL.
 *
 * TO IMPLEMENT: every function is fetch() + JSON parse + error handling.
 * On non-2xx, throw new Error(`${res.status}: ${await res.text()}`) so pages
 * can show the FastAPI error detail.
 */

import type {
  Call,
  CallAnalysis,
  GuidanceSession,
  Spec,
  Tree,
  TreeStructure,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// --- Specs -----------------------------------------------------------------

/** POST /api/specs — multipart: name + file (.pdf/.txt/.md). */
export async function uploadSpec(name: string, file: File): Promise<Spec> {
  throw new Error("not implemented");
}

/** GET /api/specs */
export async function listSpecs(): Promise<Spec[]> {
  throw new Error("not implemented");
}

/** POST /api/specs/{id}/generate-tree — slow (~10-30s), show a spinner. */
export async function generateTree(specId: string): Promise<Tree> {
  throw new Error("not implemented");
}

// --- Trees -----------------------------------------------------------------

/** GET /api/trees */
export async function listTrees(): Promise<Tree[]> {
  throw new Error("not implemented");
}

/** GET /api/trees/{id} */
export async function getTree(treeId: string): Promise<Tree> {
  throw new Error("not implemented");
}

/** PUT /api/trees/{id} — saves as a new version. */
export async function updateTree(
  treeId: string,
  structure: TreeStructure,
  title?: string
): Promise<Tree> {
  throw new Error("not implemented");
}

// --- Guidance sessions -----------------------------------------------------

/** POST /api/sessions */
export async function createSession(
  treeId: string,
  agentName: string
): Promise<GuidanceSession> {
  throw new Error("not implemented");
}

/** POST /api/sessions/{id}/step */
export async function takeStep(
  sessionId: string,
  nodeId: string,
  optionIndex: number
): Promise<GuidanceSession> {
  throw new Error("not implemented");
}

/** POST /api/sessions/{id}/finish */
export async function finishSession(sessionId: string): Promise<GuidanceSession> {
  throw new Error("not implemented");
}

// --- Calls & analysis ------------------------------------------------------

/** POST /api/calls — multipart: tree_id + audio file. Slow (transcription). */
export async function uploadCall(treeId: string, file: File): Promise<Call> {
  throw new Error("not implemented");
}

/** GET /api/calls/{id} */
export async function getCall(callId: string): Promise<Call> {
  throw new Error("not implemented");
}

/** POST /api/calls/{id}/analyze — slow (~10-30s), show a spinner. */
export async function analyzeCall(callId: string): Promise<CallAnalysis> {
  throw new Error("not implemented");
}

/** GET /api/calls/{id}/analysis — latest analysis, 404 if never analyzed. */
export async function getAnalysis(callId: string): Promise<CallAnalysis> {
  throw new Error("not implemented");
}
