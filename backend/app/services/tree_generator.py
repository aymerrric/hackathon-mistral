"""Spec document -> ground-truth decision tree, via the Mistral chat API.

TO IMPLEMENT.
"""

from app.schemas import TreeStructure


def generate_tree(spec_text: str) -> TreeStructure:
    """Turn a plain-text spec document into a validated TreeStructure.

    Implementation spec:
      1. Build a prompt containing:
         - role: "You convert call-handling procedure documents into strict
           decision trees for call-center agents."
         - the JSON contract (paste the TreeStructure/TreeNode shape and the
           node-type rules from schemas.py, plus a small example).
         - rules: every option.next_id must reference an existing node; the
           tree must be reachable from root_id; every path must terminate in
           an 'end' node; 'prompt' fields must contain the exact wording the
           agent should say, lifted from the spec where possible; aim for
           10-40 nodes.
         - the spec_text (truncate to ~30k chars if huge).
      2. Call Mistral chat completions with model settings.mistral_chat_model
         and response_format={"type": "json_object"}.
      3. Parse with TreeStructure.model_validate_json.
      4. Post-validate: root_id in nodes; all next_id resolve; no orphan
         nodes unreachable from root (drop them if present).
      5. On parse/validation failure, retry ONCE feeding the error message
         back to the model; if it fails again raise ValueError (router maps
         this to 502).
    """
    raise NotImplementedError
