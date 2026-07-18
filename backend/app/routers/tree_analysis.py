"""API endpoints for tree analysis and refinement.

Provides programmatic access to tree analysis and LLM-powered refinement.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tree, Spec
from app.schemas import TreeStructure, TreeOut
from app.services.tree_analyzer import (
    TreeAnalyzer, 
    TreeAnalysisReport, 
    analyze_tree, 
    refine_tree,
    Severity
)

router = APIRouter(prefix="/analysis", tags=["tree_analysis"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class TreeAnalysisRequest(BaseModel):
    """Request to analyze a tree."""
    tree: TreeStructure
    spec_text: str | None = None  # Optional: for coverage analysis


class TreeAnalysisResponse(BaseModel):
    """Response from tree analysis."""
    tree_id: uuid.UUID | None
    is_valid: bool
    issues: list[dict]
    metrics: dict
    suggestions: list[dict]
    coverage_score: float | None
    confidence_score: float | None
    summary: str
    
    model_config = {"from_attributes": True}


class TreeRefinementRequest(BaseModel):
    """Request to refine a tree using LLM."""
    tree: TreeStructure
    spec_text: str
    max_iterations: int = 3


class TreeRefinementResponse(BaseModel):
    """Response from tree refinement."""
    final_tree: TreeStructure
    reports: list[dict]  # Analysis reports from each iteration
    iteration_count: int
    success: bool


class IssueFilter(BaseModel):
    """Filter for issues in analysis."""
    severity: list[Severity] | None = None
    code: list[str] | None = None
    node_id: str | None = None


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/analyze", response_model=TreeAnalysisResponse)
def analyze_tree_endpoint(
    request: TreeAnalysisRequest,
    db: Session = Depends(get_db)
) -> TreeAnalysisResponse:
    """Analyze a decision tree for issues and quality metrics.
    
    This endpoint performs comprehensive analysis including:
    - Structural validation (references, node types, etc.)
    - Path validation (cycles, unreachable nodes, termination)
    - Node quality checks (labels, prompts, etc.)
    - Tree metrics (depth, branching, path counts)
    - Spec coverage analysis (if spec_text provided)
    - Automatic fix suggestions
    
    Returns a detailed report that can be used for:
    - Validating generated trees before use
    - Identifying areas for improvement
    - Feeding into LLM refinement workflows
    """
    # Convert to dict for analyzer
    tree_dict = request.tree.model_dump() if hasattr(request.tree, 'model_dump') else request.tree
    
    # Run analysis
    report = analyze_tree(tree_dict, request.spec_text)
    
    # Convert report to response
    return TreeAnalysisResponse(
        tree_id=None,  # Could link to DB tree if we had an ID
        is_valid=report.is_valid,
        issues=[i.to_dict() for i in report.issues],
        metrics=report.metrics.to_dict(),
        suggestions=[s.to_dict() for s in report.suggestions],
        coverage_score=report.coverage_score,
        confidence_score=report.confidence_score,
        summary=report.get_summary()
    )


@router.post("/analyze/{tree_id}", response_model=TreeAnalysisResponse)
def analyze_existing_tree(
    tree_id: uuid.UUID,
    spec_id: uuid.UUID | None = None,
    db: Session = Depends(get_db)
) -> TreeAnalysisResponse:
    """Analyze an existing tree from the database.
    
    Fetches the tree (and optionally its spec) from the database and analyzes it.
    """
    # Get tree
    tree = db.get(Tree, tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    
    # Get spec text if requested
    spec_text = None
    if spec_id:
        spec = db.get(Spec, spec_id)
        if spec:
            spec_text = spec.content_text
    
    # Analyze
    report = analyze_tree(tree.structure, spec_text)
    
    return TreeAnalysisResponse(
        tree_id=tree.id,
        is_valid=report.is_valid,
        issues=[i.to_dict() for i in report.issues],
        metrics=report.metrics.to_dict(),
        suggestions=[s.to_dict() for s in report.suggestions],
        coverage_score=report.coverage_score,
        confidence_score=report.confidence_score,
        summary=report.get_summary()
    )


@router.post("/refine", response_model=TreeRefinementResponse)
def refine_tree_endpoint(
    request: TreeRefinementRequest,
    db: Session = Depends(get_db)
) -> TreeRefinementResponse:
    """Refine a tree using LLM feedback.
    
    This endpoint:
    1. Analyzes the input tree
    2. Identifies issues and suggestions
    3. Uses the Mistral LLM to iteratively improve the tree
    4. Returns the refined tree and all intermediate reports
    
    Requires MISTRAL_API_KEY to be configured.
    
    The refinement process:
    - Iteration 1: Fix structural errors
    - Iteration 2: Address warnings and improve quality
    - Iteration 3+: Fine-tune and optimize
    """
    from app.config import settings
    
    if not settings.mistral_api_key:
        raise HTTPException(
            status_code=500,
            detail="MISTRAL_API_KEY not configured. Cannot refine without LLM access."
        )
    
    # Convert tree
    tree_dict = request.tree.model_dump() if hasattr(request.tree, 'model_dump') else request.tree
    
    # Run refinement
    try:
        final_tree, reports = refine_tree(
            tree_dict,
            request.spec_text,
            max_iterations=request.max_iterations
        )
        
        return TreeRefinementResponse(
            final_tree=final_tree,
            reports=[r.to_dict() for r in reports],
            iteration_count=len(reports),
            success=all(r.is_valid for r in reports[-1:])  # Last report is valid
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Refinement failed: {str(e)}"
        )


@router.post("/refine/{tree_id}", response_model=TreeRefinementResponse)
def refine_existing_tree(
    tree_id: uuid.UUID,
    request: Annotated[
        TreeRefinementRequest,
        Body(..., embed=True)
    ],
    db: Session = Depends(get_db)
) -> TreeRefinementResponse:
    """Refine an existing tree from the database.
    
    Similar to POST /refine but starts from a stored tree.
    The spec_text in the request overrides the stored spec.
    """
    from app.config import settings
    
    if not settings.mistral_api_key:
        raise HTTPException(
            status_code=500,
            detail="MISTRAL_API_KEY not configured."
        )
    
    # Get tree
    tree = db.get(Tree, tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    
    # Use provided spec_text or fall back to tree's spec
    spec_text = request.spec_text
    if not spec_text and tree.spec_id:
        spec = db.get(Spec, tree.spec_id)
        if spec:
            spec_text = spec.content_text
    
    if not spec_text:
        raise HTTPException(
            status_code=400,
            detail="spec_text is required in request or tree must have associated spec"
        )
    
    # Run refinement
    try:
        final_tree, reports = refine_tree(
            tree.structure,
            spec_text,
            max_iterations=request.max_iterations
        )
        
        return TreeRefinementResponse(
            final_tree=final_tree,
            reports=[r.to_dict() for r in reports],
            iteration_count=len(reports),
            success=all(r.is_valid for r in reports[-1:])
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Refinement failed: {str(e)}"
        )


@router.post("/validate", response_model=dict)
def validate_tree(
    tree: TreeStructure
) -> dict:
    """Quick validation endpoint - returns only errors or success.
    
    Simpler than full analysis, just checks if tree is structurally valid.
    Useful for client-side validation before saving.
    """
    tree_dict = tree.model_dump() if hasattr(tree, 'model_dump') else tree
    report = analyze_tree(tree_dict)
    
    errors = [i.to_dict() for i in report.issues if i.severity == Severity.ERROR]
    
    return {
        "is_valid": report.is_valid,
        "errors": errors,
        "error_count": len(errors)
    }


@router.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    from app.config import settings
    return {
        "status": "ok",
        "llm_available": bool(settings.mistral_api_key),
        "version": "1.0.0"
    }
