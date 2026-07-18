"""Call audio endpoints — upload, transcription, and tree-adherence analysis."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Call, CallAnalysis, Tree
from app.schemas import CallAnalysisOut, CallOut, TranscriptTurn, TreeStructure
from app.services import call_analysis, transcription

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.post("", response_model=CallOut, status_code=201)
def upload_call(
    tree_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> CallOut:
    """Upload a call recording AND transcribe it in one request.

    Input: multipart form — `tree_id`, `file` (.mp3, .wav, .m4a; 400 on
    anything else; capped at 25 MB with 413). Transcription is synchronous
    (the frontend shows a spinner); on Voxtral failure the call is marked
    'failed' and the request returns 502.
    """
    tree = db.get(Tree, tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type '{ext or file.filename}'. Use .mp3, .wav or .m4a.",
        )

    content = file.file.read()
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    call_id = uuid.uuid4()
    media_dir = Path(settings.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    audio_path = media_dir / f"{call_id}{ext}"
    audio_path.write_bytes(content)

    call = Call(id=call_id, tree_id=tree_id, audio_path=str(audio_path), status="uploaded")
    db.add(call)
    db.commit()
    db.refresh(call)

    try:
        turns = transcription.transcribe(str(audio_path))
    except RuntimeError as e:
        call.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=str(e))

    call.transcript = [t.model_dump() for t in turns]
    call.status = "transcribed"
    db.commit()
    db.refresh(call)
    return call


@router.get("/{call_id}", response_model=CallOut)
def get_call(call_id: uuid.UUID, db: Session = Depends(get_db)) -> CallOut:
    """Return the call (with transcript if available). 404 if not found."""
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.post("/{call_id}/analyze", response_model=CallAnalysisOut, status_code=201)
def analyze_call(call_id: uuid.UUID, db: Session = Depends(get_db)) -> CallAnalysisOut:
    """Judge the call against its tree. Re-analysis inserts a new row."""
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.status not in ("transcribed", "analyzed"):
        raise HTTPException(
            status_code=409,
            detail=f"Call has no transcript to analyze (status '{call.status}')",
        )

    tree = db.get(Tree, call.tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    structure = TreeStructure.model_validate(tree.structure)
    turns = [TranscriptTurn.model_validate(t) for t in call.transcript or []]

    try:
        matched_path, step_verdicts, score, summary = call_analysis.analyze(structure, turns)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    analysis = CallAnalysis(
        call_id=call_id,
        matched_path=matched_path,
        step_verdicts=[v.model_dump() for v in step_verdicts],
        score=score,
        summary=summary,
    )
    db.add(analysis)
    call.status = "analyzed"
    db.commit()
    db.refresh(analysis)
    return analysis


@router.get("/{call_id}/analysis", response_model=CallAnalysisOut)
def get_analysis(call_id: uuid.UUID, db: Session = Depends(get_db)) -> CallAnalysisOut:
    """Return the LATEST analysis for the call (max created_at).
    404 if the call has never been analyzed."""
    analysis = db.execute(
        select(CallAnalysis)
        .where(CallAnalysis.call_id == call_id)
        .order_by(CallAnalysis.created_at.desc())
        .limit(1)
    ).scalar()
    if not analysis:
        raise HTTPException(status_code=404, detail="Call has never been analyzed")
    return analysis
