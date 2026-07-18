"""Transcript vs. tree judgment, via the Mistral chat API.

Reconstructs the path the agent actually took through the ground-truth tree
and issues a followed/deviated/skipped verdict per expected step, with
supporting quotes, an overall 0-100 adherence score and a short summary.
"""

import json

from mistralai import Mistral
from pydantic import BaseModel

from app.config import settings
from app.schemas import StepVerdict, TranscriptTurn, TreeStructure


class _AnalysisPayload(BaseModel):
    """Shape the LLM must return — validated before it touches the DB."""

    matched_path: list[str]
    step_verdicts: list[StepVerdict]
    score: int
    summary: str


def _render_transcript(transcript: list[TranscriptTurn]) -> str:
    return "\n".join(f"[{t.start:.1f}s] {t.speaker}: {t.text}" for t in transcript)


def _build_prompt(tree: TreeStructure, transcript: list[TranscriptTurn]) -> str:
    tree_json = json.dumps(tree.model_dump(), indent=2)
    return f"""You are auditing a call-center call against the ground-truth decision tree the agent was supposed to follow.

=== DECISION TREE (ground truth) ===
Each node has a `prompt` (what the agent must say/ask/do) and `options` (the branches; the chosen branch must match the caller's answer).
{tree_json}

=== CALL TRANSCRIPT ===
{_render_transcript(transcript)}

=== TASK ===
1. Reconstruct the path the agent ACTUALLY took through the tree, starting at "{tree.root_id}": the ordered list of node ids whose step the agent performed or should have performed at that point.
2. For each node on the EXPECTED path at that point in the call, output a verdict:
   - "followed" — the agent said/did essentially what the node's prompt requires (paraphrase is fine),
   - "deviated" — the agent did something at this step but materially different from the prompt (e.g. asked the wrong question), or chose a branch contradicting the caller's answer,
   - "skipped"  — the node was bypassed entirely.
   Each verdict must include a short supporting quote from the transcript (`transcript_excerpt`; for "skipped" quote the moment the agent jumped ahead) and a 1-2 sentence `explanation`.
3. Give an overall adherence `score` from 0 to 100 (100 = perfect adherence) and a 2-3 sentence `summary` naming the worst deviation first.

Return ONLY a JSON object with this exact shape (no markdown, no extra text):
{{
  "matched_path": ["n1", "n3", ...],
  "step_verdicts": [
    {{"node_id": "n1", "verdict": "followed", "transcript_excerpt": "...", "explanation": "..."}}
  ],
  "score": 85,
  "summary": "..."
}}
Every node_id MUST be an id that exists in the tree above."""


def analyze(
    tree: TreeStructure, transcript: list[TranscriptTurn]
) -> tuple[list[str], list[StepVerdict], int, str]:
    """Compare a call transcript against the ground-truth tree.

    Returns (matched_path, step_verdicts, score, summary).
    Raises ValueError after one retry (router maps to 502).
    """
    client = Mistral(api_key=settings.mistral_api_key)
    messages = [{"role": "user", "content": _build_prompt(tree, transcript)}]

    last_error: str | None = None
    for attempt in range(2):
        try:
            response = client.chat.complete(
                model=settings.mistral_chat_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=6000,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from Mistral API")

            payload = _AnalysisPayload.model_validate_json(content)

            # Post-check: drop node ids the tree does not contain, clamp score.
            known = set(tree.nodes)
            matched_path = [n for n in payload.matched_path if n in known]
            step_verdicts = [v for v in payload.step_verdicts if v.node_id in known]
            score = max(0, min(100, payload.score))
            return matched_path, step_verdicts, score, payload.summary

        except Exception as e:
            last_error = str(e)
            print(f"Call analysis attempt {attempt + 1} failed: {last_error}")
            # Feed the error back for one retry.
            messages = messages[:1] + [
                {
                    "role": "user",
                    "content": (
                        f"Your previous answer was invalid: {last_error}\n"
                        "Return ONLY the corrected JSON object with keys "
                        "matched_path, step_verdicts, score, summary — "
                        "matching the required shape exactly."
                    ),
                }
            ]

    raise ValueError(f"Call analysis failed after retry: {last_error}")
