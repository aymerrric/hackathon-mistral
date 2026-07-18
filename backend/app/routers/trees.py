"""Decision tree endpoints.

TO IMPLEMENT — each function body is a spec; replace NotImplementedError.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import TreeOut, TreeUpdate

router = APIRouter()


@router.get("", response_model=list[TreeOut])
def list_trees(db: Session = Depends(get_db)) -> list[TreeOut]:
    """Return all trees, newest first. Used by the home page picker.

    Optional nicety: only return the highest version per spec.
    """
    raise NotImplementedError


@router.get("/{tree_id}", response_model=TreeOut)
def get_tree(tree_id: uuid.UUID, db: Session = Depends(get_db)) -> TreeOut:
    """Return one tree with its full structure. 404 if not found."""
    raise NotImplementedError


@router.put("/{tree_id}", response_model=TreeOut)
def update_tree(tree_id: uuid.UUID, body: TreeUpdate, db: Session = Depends(get_db)) -> TreeOut:
    """Save a manually corrected tree as a NEW version (same spec_id,
    version = old max + 1). Never mutate the existing row — sessions and
    calls may reference it.

    Validate before saving: structure.root_id exists in structure.nodes and
    every option.next_id points to an existing node (422 otherwise).
    """
    raise NotImplementedError
