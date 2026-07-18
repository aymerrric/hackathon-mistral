# CLAUDE.md

CallTree — hackathon project (Mistral hackathon). Upload a call-procedure
spec document → Mistral generates a ground-truth decision tree → employees
are guided through it live, and recorded calls are transcribed (Voxtral) and
judged against it. Full architecture, API table, and demo flow: see README.md.

## Commands

```bash
npm run setup      # first time: env files + all installs (root, no npm deps)
npm run dev        # DB (Docker) + FastAPI :8000 + Next.js :3000 together
npm run db:reset   # wipe and recreate Postgres (re-applies db/schema.sql)
cd backend && poetry run pytest          # backend tests
cd backend && poetry run uvicorn app.main:app --reload --port 8000  # backend only
cd frontend && npm run dev               # frontend only
```

Backend needs `MISTRAL_API_KEY` in `backend/.env` (copied from `.env.example`
by setup) for the AI endpoints; CRUD endpoints work without it.

## Three Python/JS environments — don't mix them

- `backend/` — **Poetry** (FastAPI app). Run things with `poetry run` from `backend/`.
- `frontend/` — npm (Next.js 14, App Router, TypeScript).
- repo root — **uv** project (`pyproject.toml` + `uv.lock`), only for the
  MultiWOZ data-download scripts in `notebooks/scripts/`. Not part of the app.
- root `package.json` is only launcher scripts; it has no dependencies.

## Frozen contracts (change = update the mirror in the same commit)

- `backend/app/schemas.py` (Pydantic) ⟷ `frontend/lib/types.ts` (TS)
- `db/schema.sql` ⟷ `backend/app/models.py` (ORM)
- The Tree JSON contract (`TreeStructure`: `root_id` + `nodes` map) is the
  core shape everything depends on — rules are documented in README.md and
  schemas.py.

## Conventions & design decisions

- **Stubs are specs**: files marked TO IMPLEMENT contain
  `NotImplementedError` / `throw` stubs whose docstring/comment is the full
  implementation spec (steps, status codes, validation). Implement to the
  spec; if the spec is wrong, fix the spec text too.
- Trees are **immutable per version**: edits/regeneration insert a new
  `trees` row with `version = max + 1`; never mutate `structure` in place
  (sessions/calls reference old versions).
- Slow AI calls (tree generation, transcription, analysis) are
  **synchronous** with frontend spinners — no task queue, hackathon choice.
- LLM calls: Mistral chat with `response_format json_object`, validate with
  Pydantic, retry once feeding the error back, then fail (router → 502).
- Audio files go to `backend/media/` on disk (gitignored), not the DB.
- Frontend talks to the backend **only** through `frontend/lib/api.ts`.
- Session `path` is append-only; `current_node_id` is always computed from
  the path, never stored.

## Gotchas

- `db/schema.sql` only auto-applies on a **fresh** Postgres volume — after
  changing it, run `npm run db:reset`.
- `frontend/lib/api.ts` reads `NEXT_PUBLIC_API_URL` from `.env.local`.
- Reference data: MultiWOZ 2.2 sample in `test-data/`; download tooling in
  `notebooks/scripts/` (see `.agents/access-multiwoz-data/SKILL.md`).
