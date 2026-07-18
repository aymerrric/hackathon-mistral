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
    return f"""You are an expert at converting call-handling procedure documents into STRICT decision trees for call-center agents.

Your task: Convert the following procedure document into a decision tree JSON that FOLLOWS ALL CONSTRAINTS below. ANY violation will cause a 502 error.

=== ABSOLUTE REQUIREMENTS ===
The output MUST be a valid JSON object with EXACTLY these fields at the top level:
1. "root_id": string - the ID of the root node (MUST exist in nodes)
2. "nodes": object - dictionary mapping node IDs to node objects (MUST NOT be empty)

Each node object MUST have EXACTLY these fields:
1. "id": string - unique identifier (e.g., 'n1', 'n2', 'n3', ...)
2. "type": string - MUST be one of: "question", "action", "end" (no other values allowed)
3. "label": string - short title (2-8 words, describe the node purpose)
4. "prompt": string - EXACT wording the agent should say/ask/do, from the spec
5. "options": array - list of option objects

Each option object MUST have EXACTLY these fields:
1. "label": string - the text for this option/choice
2. "next_id": string - the ID of the node this option leads to (MUST exist in nodes)

=== STRICT CONSTRAINTS (VIOLATIONS CAUSE 502 ERRORS) ===

CORE STRUCTURE:
- The JSON MUST have BOTH "root_id" AND "nodes" at the top level. Missing either = 502 error.
- "nodes" MUST be a JSON object (dictionary), NOT an array. {{...}} not [...].
- Every node.id in nodes MUST be unique. Duplicates = 502 error.

NODE TYPE CONSTRAINTS:
- question nodes: options array MUST have 2 OR MORE items. Having 0 or 1 = 502 error.
- action nodes: options array MUST have EXACTLY 1 item. Having 0 or 2+ = 502 error.
- end nodes: options array MUST be EMPTY ([]). Having any items = 502 error.

REFERENCE INTEGRITY:
- root_id MUST be a key in the nodes object. If root_id is 'n1', nodes MUST have 'n1' key.
- Every option.next_id MUST be a key in the nodes object. Non-existent next_id = 502 error.
- NO option.next_id can be null, undefined, or empty string. All must reference valid node IDs.

PATH CONSTRAINTS:
- Every path starting from root_id MUST eventually reach an end node (type: "end").
- NO infinite loops allowed. All paths must terminate.
- NO unreachable nodes. Every node MUST be reachable from root_id through some path.

NODE ID FORMAT:
- Use simple sequential IDs: "n1", "n2", "n3", ..., "n50"
- Do NOT use: "node1", "step_1", UUIDs, or any other format.
- Do NOT skip numbers. If you have 5 nodes, use n1 through n5.

FIELD CONSTRAINTS:
- action nodes: The single option MUST have label exactly equal to "Continue" (case-sensitive).
- prompt field: MUST be a non-empty string. Use the EXACT wording from the spec document.
- label field: MUST be a non-empty string, 2-8 words maximum.
- id field: MUST match the key in the nodes dictionary. If node key is "n1", node.id MUST be "n1".

=== VALIDATION CHECKLIST (READ CAREFULLY) ===

BEFORE returning your JSON, verify ALL of these:
[ ] Top-level has "root_id" (string) AND "nodes" (object)
[ ] nodes is NOT empty (has at least one node)
[ ] root_id value exists as a key in nodes
[ ] Every node has: id, type, label, prompt, options
[ ] Every node.id matches its key in the nodes object
[ ] All node types are valid: "question", "action", or "end"
[ ] question nodes have 2+ options
[ ] action nodes have exactly 1 option with label="Continue"
[ ] end nodes have exactly 0 options (empty array [])
[ ] Every option has: label (string), next_id (string)
[ ] Every option.next_id exists as a key in nodes
[ ] No circular references (n1 -> n2 -> n3 -> n1 is FORBIDDEN)
[ ] All paths from root eventually reach an end node
[ ] No unreachable nodes exist in the tree

=== COMMON ERRORS TO AVOID ===

INVALID - Missing required fields:
{{
    "nodes": {{"n1": {{"id": "n1", "type": "question"}}}}  // MISSING root_id, label, prompt, options
}}

INVALID - question node with 1 option:
{{
    "root_id": "n1",
    "nodes": {{"n1": {{"id": "n1", "type": "question", "label": "Q", "prompt": "P?", "options": [{{"label": "A", "next_id": "n2"}}]}}}}  // Only 1 option!
}}

INVALID - action node with wrong label:
{{
    "root_id": "n1",
    "nodes": {{"n1": {{"id": "n1", "type": "action", "label": "Act", "prompt": "Do it", "options": [{{"label": "Next", "next_id": "n2"}}]}}}}  // Label must be "Continue"
}}

INVALID - end node with options:
{{
    "root_id": "n1",
    "nodes": {{"n1": {{"id": "n1", "type": "end", "label": "End", "prompt": "Done", "options": [{{"label": "X", "next_id": "n2"}}]}}}}  // end nodes must have []
}}

INVALID - non-existent next_id:
{{
    "root_id": "n1",
    "nodes": {{"n1": {{"id": "n1", "type": "question", "label": "Q", "prompt": "P?", "options": [{{"label": "A", "next_id": "n99"}}]}}}}  // n99 doesn't exist!
}}

=== JSON CONTRACT (STRICT) ===

The tree MUST be a valid JSON object with this EXACT structure:
{{
    "root_id": "n1",
    "nodes": {{
        "n1": {{
            "id": "n1",
            "type": "question",
            "label": "Emergency situation?",
            "prompt": "Ask: 'Is anyone in immediate danger right now?'",
            "options": [
                {{"label": "Yes", "next_id": "n2"}},
                {{"label": "No", "next_id": "n3"}}
            ]
        }},
        "n2": {{
            "id": "n2",
            "type": "action",
            "label": "Dispatch emergency",
            "prompt": "Say: 'Units are on the way. Stay on the line.'",
            "options": [{{"label": "Continue", "next_id": "n4"}}]
        }},
        "n3": {{
            "id": "n3",
            "type": "end",
            "label": "Emergency handled",
            "prompt": "End call after emergency dispatch.",
            "options": []
        }}
    }}
}}

=== EXAMPLE ===
{TREE_EXAMPLE}

=== SPEC DOCUMENT ===
{spec_text}

=== FINAL INSTRUCTIONS ===
Return ONLY the JSON object. No explanation, no markdown, no comments, no extra text.
The response MUST be parseable as pure JSON with response_format={{type: "json_object"}}.
If you violate ANY constraint above, it will cause a 502 error.
Follow ALL rules exactly. Double-check your output before returning.
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
        
        # Retry once with error feedback and STRICT reminders
        retry_prompt = f"""YOUR PREVIOUS ATTEMPT FAILED with this error:

{error_msg}

YOU MUST FIX ALL ISSUES. Common mistakes to check:

STRUCTURE ERRORS:
- MISSING "root_id" or "nodes" at top level? Both are REQUIRED.
- Is "nodes" an object {{...}} or array [...]? MUST be object {{...}}.
- Is root_id value present as a key in nodes? root_id must exist in nodes.

NODE ERRORS:
- Does a question node have less than 2 options? MUST have 2 or more.
- Does an action node NOT have exactly 1 option? MUST have exactly 1.
- Does an action node's option label NOT equal "Continue"? MUST be exactly "Continue" (case-sensitive).
- Does an end node have options? MUST have empty array [].

REFERENCE ERRORS:
- Does any option.next_id NOT exist in nodes? ALL next_id MUST reference existing node keys.
- Are there any null/undefined/empty next_id values? ALL MUST be valid node IDs.

PATH ERRORS:
- Are there unreachable nodes? ALL nodes MUST be reachable from root_id.
- Are there infinite loops? ALL paths MUST terminate at end nodes.

NODE ID ERRORS:
- Are node IDs unique? NO duplicates allowed.
- Do node IDs match their keys? If key is "n1", node.id MUST be "n1".
- Are IDs in format "n1", "n2", "n3"? Do NOT use other formats.

REMEMBER: ANY violation causes 502 error. Follow ALL constraints from the original prompt.

Return ONLY corrected JSON. No explanation, no markdown, no extra text.

Original spec:
{truncated_text}
"""
        
        try:
            response = client.chat(
                model=settings.mistral_chat_model,
                messages=[{"role": "user", "content": retry_prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,  # Even more deterministic on retry
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
                f"Retry error: {str(retry_error)}. "
                f"Common issues: question nodes must have >=2 options, action nodes must have exactly 1 option with label='Continue', "
                f"end nodes must have 0 options, all next_id must reference existing nodes, "
                f"root_id and nodes must both exist at top level."
            )
