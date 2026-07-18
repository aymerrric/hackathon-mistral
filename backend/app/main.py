"""FastAPI app entrypoint. Wiring is done; routers contain the stubs.

Run with:  poetry run uvicorn app.main:app --reload --port 8000
Docs at:   http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import calls, sessions, specs, trees
from app.routers import tree_analysis

app = FastAPI(title="CallTree API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(specs.router, prefix="/api/specs", tags=["specs"])
app.include_router(trees.router, prefix="/api/trees", tags=["trees"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(tree_analysis.router, prefix="/api", tags=["analysis"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
