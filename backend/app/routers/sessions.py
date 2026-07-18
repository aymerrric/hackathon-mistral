"""Guided call session endpoints — the live "walk the employee through the
tree" flow.

TO IMPLEMENT — each function body is a spec; replace NotImplementedError.

Shared helper to write (suggested, in this module or a service):
  compute_current_node(tree_structure, path) -> str
    root_id if path is empty, else nodes[last.node_id].options[last.option_index].next_id
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SessionCreate, SessionOut, SessionStep

router = APIRouter()


@router.post("", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db)) -> SessionOut:
    """Start a guided session on a tree.

    404 if tree not found. Insert a guidance_sessions row (empty path,
    status 'active'). current_node_id in the response = tree root.
    """
    raise NotImplementedError


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> SessionOut:
    """Return the session with computed current_node_id. 404 if not found."""
    raise NotImplementedError


@router.post("/{session_id}/step", response_model=SessionOut)
def take_step(session_id: uuid.UUID, body: SessionStep, db: Session = Depends(get_db)) -> SessionOut:
    """Record one choice and advance the session.

    Validation (422 on failure):
      - session is 'active'
      - body.node_id == the session's current node (no skipping around)
      - option_index is in range for that node
    Append {node_id, option_index, at: now} to path. If the option's next_id
    is an 'end' node, ALSO append nothing further but leave the session
    active — the UI shows the end node and calls /finish explicitly.
    Return the updated SessionOut.
    """
    raise NotImplementedError


@router.post("/{session_id}/finish", response_model=SessionOut)
def finish_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> SessionOut:
    """Mark the session 'completed' (or 'abandoned' if current node is not an
    end node) and set ended_at = now. Idempotent: finishing a finished
    session returns it unchanged."""
    raise NotImplementedError
