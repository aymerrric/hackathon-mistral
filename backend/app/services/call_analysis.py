"""Transcript vs. tree judgment, via the Mistral chat API.

TO IMPLEMENT.
"""

from app.schemas import StepVerdict, TranscriptTurn, TreeStructure


def analyze(
    tree: TreeStructure, transcript: list[TranscriptTurn]
) -> tuple[list[str], list[StepVerdict], int, str]:
    """Compare a call transcript against the ground-truth tree.

    Returns (matched_path, step_verdicts, score, summary) — exactly the
    fields the router stores in call_analyses.

    Implementation spec:
      1. Build a prompt containing:
         - the full tree JSON (ids, prompts, options),
         - the transcript rendered as "[12.3s] agent: ..." lines,
         - instructions: reconstruct the path the agent actually took
           through the tree (ordered node ids); for each node on the
           EXPECTED path at that point, output a verdict:
             'followed'  — agent said/did essentially what the node's prompt
                           requires (paraphrase is fine),
             'deviated'  — agent did something at this step but materially
                           different from the prompt, or chose a branch
                           contradicting the caller's answer,
             'skipped'   — the node was bypassed entirely;
           each verdict must include a short supporting transcript quote and
           a 1-2 sentence explanation;
         - overall score 0-100 (100 = perfect adherence) and a 2-3 sentence
           summary naming the worst deviation first.
      2. Ask for a single JSON object:
         {"matched_path": [...], "step_verdicts": [...], "score": int,
          "summary": "..."} via response_format json_object; validate
         step_verdicts with StepVerdict.
      3. Post-check: every node_id in matched_path/step_verdicts exists in
         the tree (drop unknown ids); clamp score to [0, 100].
      4. Retry once on invalid JSON, then raise ValueError (router -> 502).
    """
    raise NotImplementedError
