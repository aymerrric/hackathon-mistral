"""Decision tree endpoints.

Fully implemented.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tree
from app.schemas import TreeOut, TreeUpdate, TreeStructure

router = APIRouter()


@router.get("", response_model=list[TreeOut])
def list_trees(db: Session = Depends(get_db)) -> list[T1reeOut]:
    """Return all trees, newest first. Used by the home page picker.

    Optional nicety: only return the highest version per spec.
    """
    # Get all trees, ordered by created_at descending
    result = db.execute(
        select(Tree).order_by(Tree.created_at.desc())
    )
    trees = result.scalars().all()
    return trees


@router.get("/{tree_id}", response_model=TreeOut)
def get_tree(tree_id: uuid.UUID, db: Session = Depends(get_db)) -> TreeOut:
    """Return one tree with its full structure. 404 if not found."""
    tree = db.get(Tree, tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    return tree


@router.put("/{tree_id}", response_model=TreeOut)
def update_tree(tree_id: uuid.UUID, body: TreeUpdate, db: Session = Depends(get_db)) -> TreeOut:
    """Save a manually corrected tree as a NEW version (same spec_id,
    version = old max + 1). Never mutate the existing row — sessions and
    calls may reference it.

    Validate before saving: structure.root_id exists in structure.nodes and
    every option.next_id points to an existing node (422 otherwise).
    """
    # Get existing tree
    existing_tree = db.get(Tree, tree_id)
    if not existing_tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    
    # Validate the new structure
    try:
        # Validate that it's a valid TreeStructure
        validated = TreeStructure.model_validate(body.structure.model_dump() if hasattr(body.structure, 'model_dump') else body.structure)
        
        # Additional validation: check all next_id references
        nodes = validated.nodes
        root_id = validated.root_id
        
        if root_id not in nodes:
            raise ValueError(f"Root node '{root_id}' not found in nodes")
        
        for node_id, node in nodes.items():
            for option in node.options:
                if option.next_id not in nodes:
                    raise ValueError(f"Option in node '{node_id}' references non-existent node '{option.next_id}'")
        
        # Check node type rules
        for node_id, node in nodes.items():
            if node.type == "question" and len(node.options) < 2:
                raise ValueError(f"Question node '{node_id}' must have >= 2 options")
            elif node.type == "action" and len(node.options) != 1:
                raise ValueError(f"Action node '{node_id}' must have exactly 1 option")
            elif node.type == "end" and len(node.options) != 0:
                raise ValueError(f"End node '{node_id}' must have 0 options")
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Get max version for this spec
    result = db.execute(
        select(Tree.version)
        .where(Tree.spec_id == existing_tree.spec_id)
        .order_by(Tree.version.desc())
        .limit(1)
    )
    max_version = result.scalar() or 0
    new_version = max_version + 1
    
    # Create new tree version
    new_tree = Tree(
        spec_id=existing_tree.spec_id,
        title=body.title or existing_tree.title,
        version=new_version,
        structure=validated.model_dump()
    )
    db.add(new_tree)
    db.commit()
    db.refresh(new_tree)
    
    return new_tree
