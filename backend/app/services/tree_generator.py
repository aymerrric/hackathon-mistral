"""Spec document -> ground-truth decision tree, via the Mistral chat API.

Fully implemented service for generating decision trees from call center
procedure documents (PDF, text, markdown).
"""

import json
import re

from mistralai.client import MistralClient

from app.config import settings
from app.schemas import TreeStructure


# JSON contract example for the prompt
TREE_EXAMPLE = json.dumps({
    "root_id": "n1",
    "nodes": {
        "n1": {
            "id": "n1",
            "type": "question",
            "label": "Emergency situation?",
            "prompt": "Ask: 'Is anyone in immediate danger right now?'",
            "options": [
                {"label": "Yes", "next_id": "n2"},
                {"label": "No", "next_id": "n3"}
            ]
        },
        "n2": {
            "id": "n2",
            "type": "action",
            "label": "Dispatch emergency",
            "prompt": "Say: 'Units are on the way. Stay on the line.'",
            "options": [{"label": "Continue", "next_id": "n4"}]
        },
        "n3": {
            "id": "n3",
            "type": "question",
            "label": "Account holder?",
            "prompt": "Ask: 'Are you the account holder?'",
            "options": [
                {"label": "Yes", "next_id": "n5"},
                {"label": "No", "next_id": "n6"}
            ]
        },
        "n4": {
            "id": "n4",
            "type": "end",
            "label": "Emergency handled",
            "prompt": "End call after emergency dispatch.",
            "options": []
        },
        "n5": {
            "id": "n5",
            "type": "end",
            "label": "Verified",
            "prompt": "Proceed with verified user.",
            "options": []
        },
        "n6": {
            "id": "n6",
            "type": "end",
            "label": "Not verified",
            "prompt": "Cannot proceed without verification.",
            "options": []
        }
    }
}, indent=2)


def _build_prompt(spec_text: str) -> str:
    """Build the prompt for the Mistral LLM to generate a decision tree."""
    return f"""You are an expert at converting call-handling procedure documents into strict decision trees for call-center agents.

Your task: Convert the following procedure document into a decision tree JSON that follows the exact contract below.

=== JSON CONTRACT (STRICT) ===

The tree MUST be a valid JSON object with this structure:
{{
    "root_id": "string (id of the root node)",
    "nodes": {{
        "node_id": {{
            "id": "string (unique, e.g. 'n1', 'n2', ...)",
            "type": "question" | "action" | "end",
            "label": "string (short title, 2-8 words)",
            "prompt": "string (exact wording the agent should say/ask/do)",
            "options": [
                {{"label": "string (option text)", "next_id": "string (id of next node)"}},
                ...
            ]
        }},
        ...
    }}
}}

RULES (MUST FOLLOW):
1. Node IDs must be unique strings like "n1", "n2", "n3", etc.
2. root_id must be a key in the nodes dictionary.
3. question nodes: >= 2 options
4. action nodes: exactly 1 option (with label "Continue" and next_id pointing to next step)
5. end nodes: empty options list ([])
6. Every option.next_id MUST reference an existing node id in the nodes dictionary.
7. Every path from root_id MUST eventually reach an end node (no infinite loops).
8. The "prompt" field must contain the EXACT wording from the spec document where possible.
9. Aim for 10-40 nodes total. Break complex sections into logical decision points.
10. Use the spec's natural flow: Greeting -> Verification -> Issue Identification -> Resolution -> Close.
11. For routing decisions, create question nodes with options for each route.
12. Include all major steps from the spec: identity verification, issue categorization, escalation paths, etc.

=== EXAMPLE ===
{TREE_EXAMPLE}

=== SPEC DOCUMENT ===
{spec_text}

=== INSTRUCTIONS ===
Return ONLY the JSON object. Do not include any explanation, markdown, or other text. The response must be parseable as pure JSON with response_format={{type: "json_object"}}.
"""


def _validate_tree_structure(tree: TreeStructure) -> TreeStructure:
    """Post-validate the tree structure: check all next_id references exist,
    remove unreachable nodes, ensure all paths terminate.
    
    Raises ValueError if validation fails.
    """
    nodes = tree.nodes
    root_id = tree.root_id
    
    # Check root exists
    if root_id not in nodes:
        raise ValueError(f"Root node '{root_id}' not found in nodes")
    
    # Build adjacency list and find reachable nodes
    reachable = set()
    stack = [root_id]
    
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        
        if node_id not in nodes:
            continue
        
        node = nodes[node_id]
        for option in node.options:
            if option.next_id not in nodes:
                raise ValueError(
                    f"Option in node '{node_id}' references non-existent node '{option.next_id}'"
                )
            stack.append(option.next_id)
    
    # Remove unreachable nodes (optional: we could also raise an error)
    # For now, we'll just remove them to be safe
    original_count = len(nodes)
    tree.nodes = {k: v for k, v in nodes.items() if k in reachable}
    
    if len(tree.nodes) < original_count:
        removed = original_count - len(tree.nodes)
        print(f"Warning: Removed {removed} unreachable nodes")
    
    # Validate node types and option counts
    for node_id, node in tree.nodes.items():
        if node.type == "question":
            if len(node.options) < 2:
                raise ValueError(f"Question node '{node_id}' must have >= 2 options, got {len(node.options)}")
        elif node.type == "action":
            if len(node.options) != 1:
                raise ValueError(f"Action node '{node_id}' must have exactly 1 option, got {len(node.options)}")
            if node.options[0].label != "Continue":
                print(f"Warning: Action node '{node_id}' option label should be 'Continue', got '{node.options[0].label}'")
        elif node.type == "end":
            if len(node.options) != 0:
                raise ValueError(f"End node '{node_id}' must have 0 options, got {len(node.options)}")
    
    # Check all paths terminate (no cycles, all reach end nodes)
    # Do a DFS to check for cycles and ensure end nodes are reachable
    visited = set()
    recursion_stack = set()
    has_end_node = False
    
    def check_node(node_id: str):
        nonlocal has_end_node
        if node_id in recursion_stack:
            raise ValueError(f"Cycle detected involving node '{node_id}'")
        if node_id in visited:
            return
        
        visited.add(node_id)
        recursion_stack.add(node_id)
        
        node = nodes[node_id]
        if node.type == "end":
            has_end_node = True
            recursion_stack.remove(node_id)
            return
        
        for option in node.options:
            check_node(option.next_id)
        
        recursion_stack.remove(node_id)
    
    check_node(root_id)
    
    if not has_end_node:
        raise ValueError("No end node is reachable from root")
    
    return tree


def _truncate_spec_text(text: str, max_length: int = 30000) -> str:
    """Truncate spec text if too long, preserving structure."""
    if len(text) <= max_length:
        return text
    
    # Try to truncate at paragraph boundaries
    paragraphs = re.split(r'\n\n+', text)
    truncated = []
    current_length = 0
    
    for para in paragraphs:
        para_length = len(para)
        if current_length + para_length > max_length:
            # Add as much as we can of this paragraph
            remaining = max_length - current_length
            if remaining > 0:
                truncated.append(para[:remaining])
            break
        truncated.append(para)
        current_length += para_length + 2  # +2 for the newlines we'll add
    
    result = '\n\n'.join(truncated)
    if len(result) > max_length:
        result = result[:max_length]
    
    result += f"\n\n... [TRUNCATED: original was {len(text)} chars]"
    return result


def generate_tree(spec_text: str) -> TreeStructure:
    """Turn a plain-text spec document into a validated TreeStructure.
    
    Args:
        spec_text: The extracted text from the spec document (PDF, txt, md)
        
    Returns:
        Validated TreeStructure instance
        
    Raises:
        ValueError: If tree generation or validation fails after retries
    """
    # Truncate if too long
    truncated_text = _truncate_spec_text(spec_text)
    
    # Build prompt
    prompt = _build_prompt(truncated_text)
    
    # Initialize Mistral client
    client = MistralClient(api_key=settings.mistral_api_key)
    
    # First attempt
    try:
        response = client.chat(
            model=settings.mistral_chat_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for deterministic output
            max_tokens=8000,
        )
        
        # Extract the JSON
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("No response content from Mistral API")
        
        json_str = response.choices[0].message.content
        
        # Parse with Pydantic
        tree = TreeStructure.model_validate_json(json_str)
        
        # Post-validate
        tree = _validate_tree_structure(tree)
        
        return tree
        
    except (json.JSONDecodeError, Exception) as e:
        error_msg = str(e)
        print(f"First attempt failed: {error_msg}")
        
        # Retry once with error feedback
        retry_prompt = f"""Your previous attempt to generate a decision tree failed with this error:

{error_msg}

Please fix the issues and return a corrected JSON. Remember:
- All node IDs must be unique and referenced correctly
- root_id must exist in nodes
- Every option.next_id must point to an existing node
- question nodes: >= 2 options
- action nodes: exactly 1 option with label "Continue"
- end nodes: 0 options
- All paths must terminate at an end node
- Return ONLY valid JSON, no explanation

Original spec:
{truncated_text}
"""
        
        try:
            response = client.chat(
                model=settings.mistral_chat_model,
                messages=[{"role": "user", "content": retry_prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=8000,
            )
            
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("No response content from Mistral API on retry")
            
            json_str = response.choices[0].message.content
            tree = TreeStructure.model_validate_json(json_str)
            tree = _validate_tree_structure(tree)
            
            return tree
            
        except Exception as retry_error:
            raise ValueError(
                f"Tree generation failed after retry. First error: {error_msg}. "
                f"Retry error: {str(retry_error)}"
            )
