"""Call audio endpoints — upload, transcription, and tree-adherence analysis.

TO IMPLEMENT — each function body is a spec; replace NotImplementedError.
"""

import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CallAnalysisOut, CallOut

router = APIRouter()


@router.post("", response_model=CallOut, status_code=201)
def upload_call(tree_id: uuid.UUID, file: UploadFile, db: Session = Depends(get_db)) -> CallOut:
    """Upload a call recording AND transcribe it in one request.

    Input: multipart form — `tree_id` (query/form field), `file` (.mp3, .wav,
    .m4a; 400 on anything else; cap at ~25 MB with 413).
    Steps:
      1. 404 if tree not found.
      2. Save the file to settings.media_dir/<call_id>.<ext> (create dir).
      3. Insert `calls` row with status 'uploaded'.
      4. Call services.transcription.transcribe(path) — synchronous, the
         frontend shows a spinner. On success store the transcript JSON and
         set status 'transcribed'; on failure set status 'failed' and 502.
      5. Return CallOut.
    """
    raise NotImplementedError


@router.get("/{call_id}", response_model=CallOut)
def get_call(call_id: uuid.UUID, db: Session = Depends(get_db)) -> CallOut:
    """Return the call (with transcript if available). 404 if not found."""
    raise NotImplementedError


@router.post("/{call_id}/analyze", response_model=CallAnalysisOut, status_code=201)
def analyze_call(call_id: uuid.UUID, db: Session = Depends(get_db)) -> CallAnalysisOut:
    """Judge the call against its tree.

    Preconditions: call exists (404) and status is 'transcribed' or
    'analyzed' (409 otherwise — no transcript to analyze).
    Steps:
      1. Load the call's tree structure.
      2. Call services.call_analysis.analyze(tree_structure, transcript).
      3. Insert a `call_analyses` row (re-analysis inserts a new row) and
         set call status 'analyzed'.
      4. Return CallAnalysisOut (201).
    """
    raise NotImplementedError


@router.get("/{call_id}/analysis", response_model=CallAnalysisOut)
def get_analysis(call_id: uuid.UUID, db: Session = Depends(get_db)) -> CallAnalysisOut:
    """Return the LATEST analysis for the call (max created_at).
    404 if the call has never been analyzed."""
    raise NotImplementedError
