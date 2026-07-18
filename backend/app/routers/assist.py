"""Operator copilot chat — answers questions about the active procedure.

TO IMPLEMENT — the function body is a spec; replace NotImplementedError.

Used by the small chat bar in guided mode. Must stay grounded in the tree:
it explains the procedure, it never invents steps that are not in it.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AssistReply, AssistRequest

router = APIRouter()


@router.post("", response_model=AssistReply)
def assist(body: AssistRequest, db: Session = Depends(get_db)) -> AssistReply:
    """Answer an operator question about the procedure tree.

    Steps:
      1. Load the tree (404 if body.tree_id not found).
      2. Build a system prompt containing:
         - the full tree structure as JSON,
         - if body.node_id is set and exists in the tree: "the operator is
           currently at node <id>: <label> — <prompt>",
         - instructions: answer in at most 3 short sentences, plain text,
           grounded ONLY in the procedure; if the procedure does not cover
           the question, say so explicitly instead of guessing; never tell
           the operator to skip steps.
      3. Call Mistral chat (settings.mistral_chat_model) with the system
         prompt + body.messages. Plain text output, NO json_object mode.
      4. Return AssistReply(reply=...). On Mistral API failure -> 502.

    Synchronous like the other AI endpoints; typical latency 1-3s, the chat
    bar shows a pending state.
    """
    raise NotImplementedError
