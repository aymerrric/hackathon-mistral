/**
 * API contract types — the TypeScript mirror of backend/app/schemas.py.
 * If a Pydantic schema changes, change this file in the same commit.
 * Fully defined — nothing to implement here.
 */

export type NodeType = "question" | "action" | "end";

export interface TreeOption {
  label: string;
  next_id: string;
}

export interface TreeNode {
  id: string;
  type: NodeType;
  label: string;
  /** Exact wording the agent should say/ask/do at this step. */
  prompt: string;
  /** question: >=2 options; action: exactly 1 ("Continue"); end: []. */
  options: TreeOption[];
}

export interface TreeStructure {
  root_id: string;
  nodes: Record<string, TreeNode>;
}

export interface Spec {
  id: string;
  name: string;
  original_filename: string;
  created_at: string;
}

export interface Tree {
  id: string;
  spec_id: string;
  title: string;
  version: number;
  structure: TreeStructure;
  /** True on the one version per spec that employees are guided with. */
  is_main: boolean;
  created_at: string;
}

export interface PathEntry {
  node_id: string;
  option_index: number;
  at: string;
}

export interface GuidanceSession {
  id: string;
  tree_id: string;
  agent_name: string;
  path: PathEntry[];
  status: "active" | "completed" | "abandoned";
  current_node_id: string;
  started_at: string;
  ended_at: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface TranscriptTurn {
  speaker: "agent" | "caller" | "unknown";
  start: number;
  end: number;
  text: string;
}

export interface Call {
  id: string;
  tree_id: string;
  transcript: TranscriptTurn[] | null;
  status: "uploaded" | "transcribed" | "analyzed" | "failed";
  created_at: string;
}

export interface StepVerdict {
  node_id: string;
  verdict: "followed" | "deviated" | "skipped";
  transcript_excerpt: string;
  explanation: string;
}

export interface CallAnalysis {
  id: string;
  call_id: string;
  matched_path: string[];
  step_verdicts: StepVerdict[];
  /** 0-100 overall adherence. */
  score: number;
  summary: string;
  created_at: string;
}
