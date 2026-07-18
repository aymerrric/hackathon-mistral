# CallTree

Decision-tree call guidance and auditing. Upload a procedure/spec document
(e.g. a police dispatch protocol or a customer-support playbook), let Mistral
generate a **ground-truth decision tree**, then:

1. **Guide** — an employee follows the tree live during a call through a big,
   simple step-by-step interface.
2. **Audit** — upload a recording of a past call; it is transcribed with
   **Voxtral** and judged by Mistral against the tree: which steps were
   followed, which were skipped or deviated from, with quotes and a 0-100
   adherence score.

## Architecture

```mermaid
flowchart LR
  subgraph Frontend [Next.js :3000]
    UI[Pages & components]
  end
  subgraph Backend [FastAPI :8000]
    API[REST routers]
    TG[tree_generator]
    TR[transcription]
    CA[call_analysis]
  end
  DB[(PostgreSQL :5432)]
  M[Mistral API<br/>chat + Voxtral]

  UI -- "fetch (lib/api.ts)" --> API
  API --> DB
  API --> TG & TR & CA
  TG & CA -- chat completions --> M
  TR -- audio transcription --> M
```

- **Frontend**: Next.js 14 (App Router, TypeScript). Talks to the backend
  only through the typed client `frontend/lib/api.ts`.
- **Backend**: FastAPI + SQLAlchemy 2 + Poetry. Three AI services wrap the
  Mistral API: tree generation, Voxtral transcription, call judging. Audio
  files are stored on local disk (`backend/media/`), not in the DB.
- **DB**: PostgreSQL 16 in Docker. Trees are stored as a JSONB document (see
  contract below) — always read/written whole, so no normalized nodes table.
- **Contracts**: `backend/app/schemas.py` (Pydantic) and
  `frontend/lib/types.ts` are mirrors — change both together.
  `db/schema.sql` and `backend/app/models.py` are mirrors too.

### Repository layout

```
├── docker-compose.yml        # PostgreSQL (schema auto-applied on first start)
├── db/schema.sql             # DB source of truth + JSONB shape docs
├── backend/
│   ├── pyproject.toml        # Poetry
│   └── app/
│       ├── main.py           # FastAPI wiring (done)
│       ├── config.py         # env settings (done)
│       ├── database.py       # SQLAlchemy session (done)
│       ├── models.py         # ORM models (done)
│       ├── schemas.py        # API contract (done)
│       ├── routers/          # specs, trees, sessions, calls — TO IMPLEMENT
│       └── services/         # tree_generator, transcription, call_analysis — TO IMPLEMENT
└── frontend/
    ├── lib/types.ts          # TS mirror of schemas.py (done)
    ├── lib/api.ts            # typed fetch client — TO IMPLEMENT
    ├── app/                  # pages — TO IMPLEMENT (specs in each file)
    └── components/           # TreeViewer, GuidePanel, AudioUploader, CallReport — TO IMPLEMENT
```

Every `TO IMPLEMENT` file contains a stub with a detailed docstring/comment
spec — that comment is the task description.

### Tree JSON contract

The one shape everything depends on (`trees.structure` in the DB,
`TreeStructure` in schemas.py/types.ts):

```json
{
  "root_id": "n1",
  "nodes": {
    "n1": {
      "id": "n1",
      "type": "question",
      "label": "Emergency?",
      "prompt": "Ask: 'Is anyone in immediate danger right now?'",
      "options": [
        { "label": "Yes", "next_id": "n2" },
        { "label": "No", "next_id": "n3" }
      ]
    },
    "n2": { "id": "n2", "type": "end", "label": "Dispatch", "prompt": "Say: 'Units are on the way. Stay on the line.'", "options": [] }
  }
}
```

Rules: `question` nodes have ≥2 options, `action` nodes exactly 1
("Continue"), `end` nodes none. Every `next_id` must resolve; every path must
reach an `end` node.

### API summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/specs` | Upload spec document (multipart) |
| GET | `/api/specs` | List specs |
| POST | `/api/specs/{id}/generate-tree` | Generate tree via Mistral (slow, ~10-30s) |
| GET | `/api/trees` · `/api/trees/{id}` | List / get trees |
| PUT | `/api/trees/{id}` | Save manual edits as a new version |
| POST | `/api/sessions` | Start a guided session |
| GET | `/api/sessions/{id}` | Get session + current node |
| POST | `/api/sessions/{id}/step` | Record a choice, advance |
| POST | `/api/sessions/{id}/finish` | Complete/abandon the session |
| POST | `/api/calls` | Upload audio + transcribe with Voxtral (slow) |
| GET | `/api/calls/{id}` | Get call + transcript |
| POST | `/api/calls/{id}/analyze` | Judge call vs. tree via Mistral (slow) |
| GET | `/api/calls/{id}/analysis` | Latest analysis |

Full request/response specs live in the router docstrings
(`backend/app/routers/*.py`); interactive docs at
`http://localhost:8000/docs` once running.

## Install & run

Prerequisites: **Docker**, **Python 3.11+** with **Poetry**, **Node 18+**,
and a **Mistral API key** (console.mistral.ai).

### 1. Database

```bash
docker compose up -d db
```

`db/schema.sql` is applied automatically on first start. To reset the DB:
`docker compose down -v && docker compose up -d db`.

### 2. Backend

```bash
cd backend
poetry install
cp .env.example .env        # then put your MISTRAL_API_KEY in .env
poetry run uvicorn app.main:app --reload --port 8000
```

Check: `curl http://localhost:8000/api/health` → `{"status":"ok"}`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

## Demo flow

1. Home page → upload a spec (PDF/txt/md) → tree is generated → tree view.
2. "Guide a call" → step through the tree with big buttons → finish.
3. "Audit a recording" → upload an mp3/wav of a (staged) call → transcript →
   "Analyze" → score, per-step verdicts with quotes, highlighted tree path.

Tip: record your own 2-minute fake call following (and deliberately breaking)
the tree — a call with one obvious deviation makes the best demo.

## Suggested split for 4 coders

- **A (backend core)**: routers `specs.py`, `trees.py`, `sessions.py` — pure
  CRUD + path logic, no AI. Unblocks everyone; start here.
- **B (backend AI)**: `services/` (tree_generator, transcription,
  call_analysis) + router `calls.py`. Owns the Mistral prompts.
- **C (frontend flows)**: `lib/api.ts`, home page, guided-call page,
  `GuidePanel`.
- **D (frontend viz)**: `TreeViewer`, audit page, `AudioUploader`,
  `CallReport`.

Ground rules: schemas.py / types.ts / schema.sql are frozen contracts —
changing one means changing its mirror in the same commit and telling the
team. B and D can develop against hardcoded fixture JSON before A finishes.
