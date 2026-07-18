"""Pydantic schemas — the API contract shared with the frontend.

These are fully defined and mirrored by frontend/lib/types.ts. If you change
a schema here, update types.ts in the same commit.

The Tree JSON contract (TreeStructure below) is the single most important
shape in the project: the LLM must produce it, the frontend renders it, and
the analyzer compares transcripts against it.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Tree JSON contract
# ---------------------------------------------------------------------------

NodeType = Literal["question", "action", "end"]


class TreeOption(BaseModel):
    """One selectable branch out of a question node."""

    label: str  # e.g. "Yes", "Caller is in immediate danger"
    next_id: str  # id of the node this option leads to


class TreeNode(BaseModel):
    id: str  # unique within the tree, e.g. "n1"
    type: NodeType
    label: str  # short title shown in the tree view
    prompt: str  # exact wording the agent should say/ask/do
    # question nodes: >= 2 options. action nodes: exactly 1 option
    # ("Continue"). end nodes: empty list.
    options: list[TreeOption] = Field(default_factory=list)


class TreeStructure(BaseModel):
    root_id: str
    nodes: dict[str, TreeNode]  # keyed by node id; must contain root_id


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------


class SpecOut(BaseModel):
    id: uuid.UUID
    name: str
    original_filename: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------


class TreeOut(BaseModel):
    id: uuid.UUID
    spec_id: uuid.UUID
    title: str
    version: int
    structure: TreeStructure
    # True on the one version per spec that employees are guided with.
    is_main: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class TreeUpdate(BaseModel):
    """Manual correction of a generated tree (saved as a new version)."""

    title: str | None = None
    structure: TreeStructure


# ---------------------------------------------------------------------------
# Guidance sessions
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    tree_id: uuid.UUID
    agent_name: str


class SessionStep(BaseModel):
    node_id: str
    option_index: int  # index into that node's options list


class PathEntry(BaseModel):
    node_id: str
    option_index: int
    at: datetime


class SessionOut(BaseModel):
    id: uuid.UUID
    tree_id: uuid.UUID
    agent_name: str
    path: list[PathEntry]
    status: Literal["active", "completed", "abandoned"]
    current_node_id: str  # computed: root if path empty, else last chosen next_id
    started_at: datetime
    ended_at: datetime | None


# ---------------------------------------------------------------------------
# Assist (operator copilot chat)
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistRequest(BaseModel):
    tree_id: uuid.UUID
    # Node the operator is currently on in guided mode, if any — lets the
    # model answer relative to "where we are" in the procedure.
    node_id: str | None = None
    messages: list[ChatMessage]  # full history, oldest first


class AssistReply(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# Calls & analysis
# ---------------------------------------------------------------------------


class TranscriptTurn(BaseModel):
    speaker: Literal["agent", "caller", "unknown"]
    start: float  # seconds from start of audio
    end: float
    text: str


class CallOut(BaseModel):
    id: uuid.UUID
    tree_id: uuid.UUID
    transcript: list[TranscriptTurn] | None
    status: Literal["uploaded", "transcribed", "analyzed", "failed"]
    created_at: datetime

    model_config = {"from_attributes": True}


class StepVerdict(BaseModel):
    node_id: str
    verdict: Literal["followed", "deviated", "skipped"]
    transcript_excerpt: str  # quote from the transcript supporting the verdict
    explanation: str  # one or two sentences


class CallAnalysisOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    matched_path: list[str]  # ordered node ids the agent actually followed
    step_verdicts: list[StepVerdict]
    score: int  # 0-100 overall adherence
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}
