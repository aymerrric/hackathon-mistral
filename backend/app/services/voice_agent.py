"""AI voice agent that CONDUCTS a call by rigorously following the tree.

Unlike guide mode (a human operator clicks through the tree) the voice agent
IS the operator: it speaks the node prompts, listens to the caller, maps each
answer onto one of the current node's options, and advances the same
GuidanceSession path the human flow uses — so AI calls show up in the Log
like any other session.

Rigour model: the tree is a state machine advanced only by this module.
The LLM never picks the next node directly — it only (a) classifies the
caller's utterance into one of the current node's options (or none) and
(b) words the agent's next line, given the exact script it must cover.
Action chains are auto-traversed; end nodes complete the session.

On finish the full conversation is stored as a `calls` row (transcript,
status 'transcribed') so it can be judged by the existing audit flow.

Used by routers/voice.py (browser mic over WS) and routers/twilio_voice.py
(phone via Twilio Media Streams).
"""

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from mistralai.client import Mistral
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Call, GuidanceSession, Tree

# ---------------------------------------------------------------------------
# Pure tree-walking helpers
# ---------------------------------------------------------------------------

_META_PREFIX = re.compile(
    r"^\s*(ask|say|tell(?: the caller| them)?|inform(?: the caller)?|state|read|announce)\b[^:]*:\s*",
    re.IGNORECASE,
)


def speech_of(prompt: str) -> str:
    """Render a node prompt ("Ask: 'Are you safe?'") as speakable text."""
    text = _META_PREFIX.sub("", prompt.strip())
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        text = text[1:-1]
    return text.strip()


def walk_entry(structure: dict, node_id: str) -> tuple[list[dict], list[str], str, bool]:
    """Speak the node at node_id, auto-continuing through action nodes.

    Returns (path_entries_for_traversed_actions, prompt_lines, landing_node_id,
    landed_on_end). The landing node (question or end) gets no path entry —
    a question is answered later, an end node just closes the call.
    """
    entries: list[dict] = []
    lines: list[str] = []
    cur = node_id
    while structure["nodes"][cur]["type"] == "action":
        node = structure["nodes"][cur]
        lines.append(node["prompt"])
        entries.append({"node_id": cur, "option_index": 0})
        cur = node["options"][0]["next_id"]
    node = structure["nodes"][cur]
    lines.append(node["prompt"])
    return entries, lines, cur, node["type"] == "end"


def walk_option(
    structure: dict, node_id: str, option_index: int
) -> tuple[list[dict], list[str], str, bool]:
    """Take option option_index at node_id, then chain like walk_entry."""
    first = {"node_id": node_id, "option_index": option_index}
    next_id = structure["nodes"][node_id]["options"][option_index]["next_id"]
    entries, lines, landing, ends = walk_entry(structure, next_id)
    return [first, *entries], lines, landing, ends


# ---------------------------------------------------------------------------
# Call state
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    say: str
    node_id: str
    done: bool
    stepped: bool  # whether the tree advanced this turn


@dataclass
class VoiceCall:
    channel: str  # "web" | "phone"
    session_id: uuid.UUID
    tree_id: uuid.UUID
    tree_title: str
    structure: dict
    current_node_id: str
    history: list[dict] = field(default_factory=list)  # chat messages
    transcript: list[dict] = field(default_factory=list)  # TranscriptTurn dicts
    t0: float = field(default_factory=time.time)
    done: bool = False
    call_row_id: uuid.UUID | None = None

    def _offset(self) -> float:
        return round(time.time() - self.t0, 2)

    def _record(self, speaker: str, text: str, start: float | None = None) -> None:
        now = self._offset()
        self.transcript.append(
            {"speaker": speaker, "start": start if start is not None else now,
             "end": now, "text": text}
        )


# ---------------------------------------------------------------------------
# Session/DB plumbing (mirrors routers/sessions.py semantics)
# ---------------------------------------------------------------------------


def start_call(db: Session, tree: Tree, channel: str, agent_label: str) -> tuple[VoiceCall, str]:
    """Create the GuidanceSession and compose the deterministic greeting
    (opener + root prompt chain, spoken verbatim). Returns (call, greeting)."""
    sess = GuidanceSession(tree_id=tree.id, agent_name=agent_label, path=[])
    db.add(sess)
    db.commit()
    db.refresh(sess)

    structure = tree.structure
    entries, lines, landing, ends = walk_entry(structure, structure["root_id"])
    call = VoiceCall(
        channel=channel,
        session_id=sess.id,
        tree_id=tree.id,
        tree_title=tree.title,
        structure=structure,
        current_node_id=landing,
    )
    if entries:
        _append_steps(db, call, entries)

    greeting = "Hello, thank you for calling. You are speaking with an automated assistant. " + " ".join(
        speech_of(line) for line in lines
    )
    call.history.append({"role": "assistant", "content": greeting})
    call._record("agent", greeting)

    if ends:  # degenerate tree: root chain runs straight into an end node
        finish_call(db, call, completed=True)
    return call, greeting


def _append_steps(db: Session, call: VoiceCall, entries: list[dict]) -> None:
    sess = db.get(GuidanceSession, call.session_id)
    if sess is None or sess.status != "active":
        return
    at = datetime.now(timezone.utc).isoformat()
    sess.path = [*sess.path, *[{**e, "at": at} for e in entries]]
    db.commit()


def finish_call(db: Session, call: VoiceCall, completed: bool) -> None:
    """Finish the session and persist the conversation as a transcribed Call.
    Idempotent."""
    if call.done:
        return
    call.done = True
    sess = db.get(GuidanceSession, call.session_id)
    if sess is not None and sess.status == "active":
        sess.status = "completed" if completed else "abandoned"
        sess.ended_at = datetime.now(timezone.utc)
        db.commit()
    if call.transcript and call.call_row_id is None:
        row = Call(
            tree_id=call.tree_id,
            audio_path="",  # live AI call — no recording file
            transcript=call.transcript,
            status="transcribed",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        call.call_row_id = row.id


# ---------------------------------------------------------------------------
# The LLM turn
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = """You are an AI call-center agent on a LIVE VOICE call, conducting the procedure "{title}".
You must follow the procedure's decision tree RIGOROUSLY: never invent steps, never skip steps, never promise anything the procedure does not cover.

FULL PROCEDURE TREE (ground truth, JSON):
{tree_json}

CURRENT POSITION: node "{node_id}" — {node_label}
The question you have already asked the caller is: {node_prompt}

The caller's latest reply is the last user message. Decide which option it maps to:
{options_block}

Respond with ONLY a JSON object:
{{"option_index": <int or null>, "say": "<what you say next, plain spoken language>"}}

Rules for "option_index":
- Pick the option index ONLY if the caller's reply clearly selects it. Paraphrases and implicit answers count ("my house is on fire" clearly means an emergency).
- Use null if the reply is ambiguous, off-topic, inaudible, or a question.

Rules for "say":
- If you picked an option: briefly acknowledge the answer, then deliver EVERY line of that option's script above, in order, faithfully. You may reword instructions into natural first-person speech, but keep all facts, questions and instructions intact. End with the script's final question if there is one.
- If option_index is null: politely handle it — answer questions using ONLY the procedure tree above (if the tree does not cover it, say you cannot help with that on this call), then repeat the current question so the call moves forward.
- Spoken style: short sentences, no lists, no markdown, no emojis. This text is read aloud by TTS.
- Reply in the language the caller is speaking.
"""


def _options_block(structure: dict, node_id: str) -> str:
    node = structure["nodes"][node_id]
    parts = []
    for i, opt in enumerate(node["options"]):
        _, lines, _, ends = walk_option(structure, node_id, i)
        script = "\n".join(f"     - {line}" for line in lines)
        suffix = "\n     - (this ends the call)" if ends else ""
        parts.append(f"  [{i}] \"{opt['label']}\" -> script to deliver:\n{script}{suffix}")
    return "\n".join(parts)


async def _decide(call: VoiceCall, utterance: str) -> dict:
    """One Mistral chat call (json_object); retry once feeding the error back."""
    node = call.structure["nodes"][call.current_node_id]
    system = _SYSTEM_TEMPLATE.format(
        title=call.tree_title,
        tree_json=json.dumps(call.structure, ensure_ascii=False),
        node_id=node["id"],
        node_label=node["label"],
        node_prompt=node["prompt"],
        options_block=_options_block(call.structure, call.current_node_id),
    )
    messages = [
        {"role": "system", "content": system},
        *call.history[-16:],
        {"role": "user", "content": utterance},
    ]
    client = Mistral(api_key=settings.mistral_api_key)
    n_options = len(node["options"])
    last_error = ""
    for attempt in range(2):
        try:
            res = await client.chat.complete_async(
                model=settings.mistral_chat_model,
                messages=messages
                if attempt == 0
                else [
                    *messages,
                    {
                        "role": "user",
                        "content": f"Your previous reply was invalid ({last_error}). "
                        'Return ONLY {"option_index": <int or null>, "say": "..."}.',
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=600,
            )
            out = json.loads(res.choices[0].message.content)
            idx = out.get("option_index")
            say = (out.get("say") or "").strip()
            if idx is not None:
                idx = int(idx)
                if not 0 <= idx < n_options:
                    raise ValueError(f"option_index {idx} out of range 0..{n_options - 1}")
            if not say:
                raise ValueError("empty 'say'")
            return {"option_index": idx, "say": say}
        except Exception as e:  # noqa: BLE001 — feed anything back once, then fail
            last_error = str(e)
    raise RuntimeError(f"Voice agent LLM turn failed: {last_error}")


async def agent_turn(db: Session, call: VoiceCall, utterance: str, heard_at: float | None = None) -> TurnResult:
    """Process one finalized caller utterance and produce the agent's reply.

    Advances the session path when the LLM maps the reply to an option;
    finishes the session (and persists the transcript Call) on an end node.
    """
    call._record("caller", utterance, start=heard_at)
    call.history.append({"role": "user", "content": utterance})

    if call.done:
        say = "This call is already complete. Thank you, goodbye."
        call.history.append({"role": "assistant", "content": say})
        call._record("agent", say)
        return TurnResult(say=say, node_id=call.current_node_id, done=True, stepped=False)

    decision = await _decide(call, utterance)
    say = decision["say"]
    stepped = False

    if decision["option_index"] is not None:
        entries, _lines, landing, ends = walk_option(
            call.structure, call.current_node_id, decision["option_index"]
        )
        _append_steps(db, call, entries)
        call.current_node_id = landing
        stepped = True
        if ends:
            call.history.append({"role": "assistant", "content": say})
            call._record("agent", say)
            finish_call(db, call, completed=True)
            return TurnResult(say=say, node_id=landing, done=True, stepped=True)

    call.history.append({"role": "assistant", "content": say})
    call._record("agent", say)
    return TurnResult(say=say, node_id=call.current_node_id, done=False, stepped=stepped)
