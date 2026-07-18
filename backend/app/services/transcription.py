"""Audio file -> speaker-turned transcript, via Mistral Voxtral.

Strategy (spec option b, upgraded): Voxtral is asked to diarize
(`diarize=True`), which tags every segment with a `speaker_id`. One extra
Mistral chat call then decides which diarized speaker is the 'agent' and
which is the 'caller' (the agent is the one asking the scripted questions).
If diarization or the labeling call fails, speakers fall back to 'unknown'
and the analyzer works from raw text.
"""

import json
from pathlib import Path

from mistralai import Mistral

from app.config import settings
from app.schemas import TranscriptTurn

_ROLE_PROMPT = """You are labeling speakers in a call-center recording.

Below is a diarized transcript. Each line starts with a speaker id in
brackets. Exactly one speaker is the call-center AGENT (asks the scripted
questions, gives instructions, follows a procedure); the others are the
CALLER (describes their problem, answers the questions).

Return ONLY a JSON object mapping every speaker id to "agent" or "caller",
e.g. {{"0": "agent", "1": "caller"}}.

Transcript:
{transcript}
"""


def _label_speakers(client: Mistral, turns: list[dict]) -> dict[str, str]:
    """Map diarized speaker ids to 'agent'/'caller' via one chat call.

    Returns {} on any failure so the caller can fall back to 'unknown'.
    """
    speaker_ids = {t["sid"] for t in turns if t["sid"] is not None}
    if not speaker_ids:
        return {}

    rendered = "\n".join(f"[{t['sid']}] {t['text']}" for t in turns if t["sid"] is not None)
    try:
        response = client.chat.complete(
            model=settings.mistral_chat_model,
            messages=[{"role": "user", "content": _ROLE_PROMPT.format(transcript=rendered)}],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=500,
        )
        raw = json.loads(response.choices[0].message.content)
        labels = {
            str(sid): role
            for sid, role in raw.items()
            if role in ("agent", "caller")
        }
        # Only trust the mapping if it covers every diarized speaker.
        if all(str(sid) in labels for sid in speaker_ids):
            return labels
    except Exception as e:
        print(f"Speaker labeling failed, falling back to 'unknown': {e}")
    return {}


def transcribe(audio_path: str) -> list[TranscriptTurn]:
    """Transcribe a call recording into speaker turns.

    Raises RuntimeError on API failure (router maps to 502 and marks the
    call 'failed').
    """
    client = Mistral(api_key=settings.mistral_api_key)
    path = Path(audio_path)

    try:
        with path.open("rb") as f:
            response = client.audio.transcriptions.complete(
                model=settings.mistral_audio_model,
                file={"file_name": path.name, "content": f},
                diarize=True,
                timestamp_granularities=["segment"],
            )
    except Exception as e:
        raise RuntimeError(f"Voxtral transcription failed: {e}") from e

    segments = response.segments or []
    if not segments:
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Voxtral returned an empty transcript")
        return [TranscriptTurn(speaker="unknown", start=0.0, end=0.0, text=text)]

    # Merge consecutive segments from the same diarized speaker into turns.
    turns: list[dict] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        sid = getattr(seg, "speaker_id", None)
        if turns and sid is not None and turns[-1]["sid"] == sid:
            turns[-1]["end"] = float(seg.end or turns[-1]["end"])
            turns[-1]["text"] += " " + text
        else:
            turns.append(
                {
                    "sid": sid,
                    "start": float(seg.start or 0.0),
                    "end": float(seg.end or 0.0),
                    "text": text,
                }
            )

    if not turns:
        raise RuntimeError("Voxtral returned an empty transcript")

    role_by_sid = _label_speakers(client, turns)
    return [
        TranscriptTurn(
            speaker=role_by_sid.get(str(t["sid"]), "unknown"),
            start=t["start"],
            end=t["end"],
            text=t["text"],
        )
        for t in turns
    ]
