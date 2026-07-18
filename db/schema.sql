-- CallTree database schema (PostgreSQL 16)
--
-- Design note: the decision tree itself is stored as a single JSONB document
-- (see "Tree JSON contract" in README.md) instead of a normalized nodes table.
-- This is a deliberate hackathon trade-off: the tree is always read/written as
-- a whole, and JSONB avoids recursive queries. Node ids are strings unique
-- WITHIN one tree (e.g. "n1", "n2").

CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- for gen_random_uuid()

-- An uploaded specification document (the source of truth text).
CREATE TABLE specs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    content_text  TEXT NOT NULL,            -- extracted plain text of the document
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A generated (and possibly hand-edited) decision tree for a spec.
-- Several versions per spec are allowed; the highest version is the active one.
CREATE TABLE trees (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spec_id       UUID NOT NULL REFERENCES specs(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    structure     JSONB NOT NULL,           -- Tree JSON contract (root_id + nodes map)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (spec_id, version)
);

-- A live guided session: an employee being walked through a tree during a call.
CREATE TABLE guidance_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tree_id       UUID NOT NULL REFERENCES trees(id) ON DELETE CASCADE,
    agent_name    TEXT NOT NULL,
    -- Ordered list of steps taken:
    -- [{"node_id": "n1", "option_index": 0, "at": "<iso8601>"}, ...]
    path          JSONB NOT NULL DEFAULT '[]',
    status        TEXT NOT NULL DEFAULT 'active',  -- active | completed | abandoned
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at      TIMESTAMPTZ
);

-- An uploaded call recording and its transcript.
CREATE TABLE calls (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tree_id       UUID NOT NULL REFERENCES trees(id) ON DELETE CASCADE,
    audio_path    TEXT NOT NULL,            -- path on disk under MEDIA_DIR
    -- Transcript with speaker turns:
    -- [{"speaker": "agent"|"caller", "start": 1.2, "end": 4.5, "text": "..."}]
    -- Null until transcription has run.
    transcript    JSONB,
    status        TEXT NOT NULL DEFAULT 'uploaded', -- uploaded | transcribed | analyzed | failed
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The LLM judgment of a call against its tree. One row per analysis run
-- (re-analysis inserts a new row; latest created_at wins).
CREATE TABLE call_analyses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id       UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    -- Node ids the agent actually followed, in order, as inferred from the
    -- transcript: ["n1", "n3", "n7"]
    matched_path  JSONB NOT NULL,
    -- Per-step verdicts:
    -- [{"node_id": "n3", "verdict": "followed"|"deviated"|"skipped",
    --   "transcript_excerpt": "...", "explanation": "..."}]
    step_verdicts JSONB NOT NULL,
    score         INTEGER NOT NULL,         -- 0-100 overall adherence score
    summary       TEXT NOT NULL,            -- short natural-language summary
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trees_spec_id ON trees(spec_id);
CREATE INDEX idx_sessions_tree_id ON guidance_sessions(tree_id);
CREATE INDEX idx_calls_tree_id ON calls(tree_id);
CREATE INDEX idx_analyses_call_id ON call_analyses(call_id);
