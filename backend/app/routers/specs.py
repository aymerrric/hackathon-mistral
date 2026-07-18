"""Spec document endpoints.

Fully implemented.
"""

import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Spec, Tree
from app.schemas import SpecOut, TreeOut
from app.services import tree_generator

router = APIRouter()


def _extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def _extract_text_from_file(file: UploadFile) -> str:
    """Extract text from uploaded file (PDF, txt, or md)."""
    filename = Path(file.filename or "").suffix.lower()
    
    # Read file content
    content = file.file.read()
    file.file.seek(0)  # Reset file pointer
    
    if filename == ".pdf":
        return _extract_text_from_pdf(content)
    elif filename in (".txt", ".md", ".markdown"):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("File is not valid UTF-8 text")
    else:
        raise ValueError(f"Unsupported file type: {filename}")


@router.post("", response_model=SpecOut, status_code=201)
def upload_spec(
    name: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
) -> SpecOut:
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
    # Extract text from file
    try:
        text_content = _extract_text_from_file(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not text_content or not text_content.strip():
        raise HTTPException(status_code=400, detail="Extracted text is empty")
    
    # Create spec in database
    spec = Spec(
        name=name,
        original_filename=file.filename,
        content_text=text_content
    )
    db.add(spec)
    db.commit()
    db.refresh(spec)
    
    return spec


@router.get("", response_model=list[SpecOut])
def list_specs(db: Session = Depends(get_db)) -> list[SpecOut]:
    """Return all specs, newest first."""
    result = db.execute(
        select(Spec).order_by(Spec.created_at.desc())
    )
    specs = result.scalars().all()
    return specs


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
    # Get spec
    spec = db.get(Spec, spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    
    # Generate tree
    try:
        tree_structure = tree_generator.generate_tree(spec.content_text)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tree generation failed: {str(e)}")
    
    # Get max version for this spec
    result = db.execute(
        select(Tree.version)
        .where(Tree.spec_id == spec_id)
        .order_by(Tree.version.desc())
        .limit(1)
    )
    max_version = result.scalar() or 0
    new_version = max_version + 1
    
    # Create tree. The first version of a spec (or a regeneration when no
    # main version exists) becomes the employees' version automatically;
    # after that, selection is explicit via POST /api/trees/{id}/select.
    # has_main = db.execute(
    #     select(Tree.id).where(Tree.spec_id == spec_id, Tree.is_main).limit(1)
    # ).scalar() is not None
    has_main = False  # Always False when is_main column is commented out
    tree = Tree(
        spec_id=spec_id,
        title=spec.name,
        version=new_version,
        structure=tree_structure.model_dump(),
        # is_main=not has_main,  # Commented out - uncomment when DB has the column
    )
    db.add(tree)
    db.commit()
    db.refresh(tree)
    
    return tree
