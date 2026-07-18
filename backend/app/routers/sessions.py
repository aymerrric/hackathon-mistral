"""Guided call session endpoints — the live "walk the employee through the
tree" flow.

Fully implemented. The session path is append-only; current_node_id is
always computed from the path, never stored.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GuidanceSession, Tree
from app.schemas import SessionCreate, SessionOut, SessionStep

router = APIRouter()


def _compute_current_node(structure: dict, path: list[dict]) -> str:
    """root_id if the path is empty, else the next_id of the last choice."""
    if not path:
        return structure["root_id"]
    last = path[-1]
    node = structure["nodes"][last["node_id"]]
    return node["options"][last["option_index"]]["next_id"]


def _to_out(sess: GuidanceSession, structure: dict) -> SessionOut:
    return SessionOut(
        id=sess.id,
        tree_id=sess.tree_id,
        agent_name=sess.agent_name,
        path=sess.path,
        status=sess.status,
        current_node_id=_compute_current_node(structure, sess.path),
        started_at=sess.started_at,
        ended_at=sess.ended_at,
    )


def _load(session_id: uuid.UUID, db: Session) -> tuple[GuidanceSession, Tree]:
    sess = db.get(GuidanceSession, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    tree = db.get(Tree, sess.tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree for this session not found")
    return sess, tree


@router.post("", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db)) -> SessionOut:
    """Start a guided session on a tree.

    404 if tree not found. Inserts a guidance_sessions row (empty path,
    status 'active'). current_node_id in the response = tree root.
    """
    tree = db.get(Tree, body.tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    sess = GuidanceSession(tree_id=body.tree_id, agent_name=body.agent_name, path=[])
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return _to_out(sess, tree.structure)


@router.get("", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)) -> list[SessionOut]:
    """All sessions, newest first. Used by the call log; the frontend
    filters by tree family (spec) client-side."""
    sessions = (
        db.execute(select(GuidanceSession).order_by(GuidanceSession.started_at.desc()))
        .scalars()
        .all()
    )
    trees: dict[uuid.UUID, Tree] = {}
    out: list[SessionOut] = []
    for sess in sessions:
        tree = trees.get(sess.tree_id) or db.get(Tree, sess.tree_id)
        if not tree:
            continue
        trees[sess.tree_id] = tree
        out.append(_to_out(sess, tree.structure))
    return out


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> SessionOut:
    """Return the session with computed current_node_id. 404 if not found."""
    sess, tree = _load(session_id, db)
    return _to_out(sess, tree.structure)


@router.post("/{session_id}/step", response_model=SessionOut)
def take_step(session_id: uuid.UUID, body: SessionStep, db: Session = Depends(get_db)) -> SessionOut:
    """Record one choice and advance the session.

    422 if the session is not active, body.node_id is not the current node
    (no skipping around), or option_index is out of range. Appends
    {node_id, option_index, at} to the path; reaching an end node leaves the
    session active — the UI calls /finish explicitly.
    """
    sess, tree = _load(session_id, db)
    structure = tree.structure

    if sess.status != "active":
        raise HTTPException(status_code=422, detail="Session is not active")

    current = _compute_current_node(structure, sess.path)
    if body.node_id != current:
        raise HTTPException(
            status_code=422,
            detail=f"node_id must be the current node ({current}), got {body.node_id}",
        )
    node = structure["nodes"].get(body.node_id)
    if node is None:
        raise HTTPException(status_code=422, detail=f"Node {body.node_id} not in tree")
    if not 0 <= body.option_index < len(node["options"]):
        raise HTTPException(
            status_code=422,
            detail=f"option_index {body.option_index} out of range for node {body.node_id}",
        )

    entry = {
        "node_id": body.node_id,
        "option_index": body.option_index,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    # Reassign (don't mutate in place) so SQLAlchemy detects the JSONB change.
    sess.path = [*sess.path, entry]
    db.commit()
    db.refresh(sess)
    return _to_out(sess, structure)


@router.post("/{session_id}/finish", response_model=SessionOut)
def finish_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> SessionOut:
    """Mark the session 'completed' (or 'abandoned' if the current node is
    not an end node) and set ended_at. Idempotent: finishing a finished
    session returns it unchanged."""
    sess, tree = _load(session_id, db)
    if sess.status == "active":
        current = _compute_current_node(tree.structure, sess.path)
        node = tree.structure["nodes"].get(current)
        sess.status = "completed" if node and node["type"] == "end" else "abandoned"
        sess.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(sess)
    return _to_out(sess, tree.structure)
