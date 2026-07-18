"""Spec document endpoints.

TO IMPLEMENT — each function body is a spec; replace NotImplementedError.
"""

import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SpecOut, TreeOut

router = APIRouter()


@router.post("", response_model=SpecOut, status_code=201)
def upload_spec(name: str, file: UploadFile, db: Session = Depends(get_db)) -> SpecOut:
    """Upload a specification document and store its extracted text.

    Input: multipart form — `name` (display name), `file` (.pdf, .txt or .md).
    Steps:
      1. Read the file. If PDF, extract text with pypdf; otherwise decode UTF-8.
      2. 400 if extracted text is empty or file type unsupported.
      3. Insert a `specs` row (name, original_filename, content_text).
      4. Return the created SpecOut (201).
    Note: this does NOT generate the tree — that is a separate, explicit call
    so the UI can show a "generating…" state.
    """
    raise NotImplementedError


@router.get("", response_model=list[SpecOut])
def list_specs(db: Session = Depends(get_db)) -> list[SpecOut]:
    """Return all specs, newest first."""
    raise NotImplementedError


@router.post("/{spec_id}/generate-tree", response_model=TreeOut, status_code=201)
def generate_tree(spec_id: uuid.UUID, db: Session = Depends(get_db)) -> TreeOut:
    """Generate the ground-truth decision tree for a spec via Mistral.

    Steps:
      1. 404 if spec not found.
      2. Call services.tree_generator.generate_tree(spec.content_text).
      3. Validate the result against schemas.TreeStructure (the service
         already does this; a validation failure should surface as 502).
      4. Insert a `trees` row: title = spec.name, version = 1 + max existing
         version for this spec (so regeneration never overwrites).
      5. Return the created TreeOut (201).
    Synchronous on purpose (hackathon): generation takes ~10-30s, the
    frontend shows a spinner. No task queue.
    """
    raise NotImplementedError
