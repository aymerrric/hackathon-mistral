"""Live AI voice agent over WebSocket — the browser leg.

WS /api/voice/ws?tree_id=<uuid>&operator=<name>

Client -> server:
  - binary frames: raw PCM16 mono audio at 16 kHz (little-endian)
  - {"type": "end"}: hang up

Server -> client (JSON):
  - {"type": "ready", "session_id", "node_id", "greeting"}
  - {"type": "audio", "wav": <base64>}          agent speech (Voxtral TTS)
  - {"type": "partial", "text"}                 live caller transcript
  - {"type": "user", "text"}                    finalized caller turn
  - {"type": "agent", "text", "node_id", "done", "stepped", "call_id"}
  - {"type": "error", "detail"}

The pipeline is: Voxtral realtime STT (silence-based turn taking, see
services/stt.py) -> tree-following agent (services/voice_agent.py) ->
Voxtral TTS. The client mutes its mic while agent audio plays, so no
barge-in handling is needed here.
"""

import base64
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.models import Tree
from app.services import tts, voice_agent
from app.services.stt import VoicePipeline

router = APIRouter()


async def _send(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:  # noqa: BLE001 — client already gone
        pass


async def _send_speech(ws: WebSocket, text: str) -> None:
    """TTS the text and ship it; on TTS failure the client falls back to
    browser speech synthesis (it already has the text)."""
    try:
        wav = await tts.synth_wav(text)
        await ws.send_text(
            json.dumps({"type": "audio", "wav": base64.b64encode(wav).decode("ascii")})
        )
    except Exception as e:  # noqa: BLE001
        await _send(ws, {"type": "error", "detail": f"TTS failed: {e}"})


@router.websocket("/ws")
async def voice_ws(ws: WebSocket, tree_id: uuid.UUID, operator: str = "") -> None:
    await ws.accept()

    with SessionLocal() as db:
        tree = db.get(Tree, tree_id)
        if tree is None:
            await _send(ws, {"type": "error", "detail": "Tree not found"})
            await ws.close(code=4404)
            return
        label = f"AI voice agent (web{' · ' + operator.strip() if operator.strip() else ''})"
        call, greeting = voice_agent.start_call(db, tree, "web", label)

    await _send(
        ws,
        {
            "type": "ready",
            "session_id": str(call.session_id),
            "node_id": call.current_node_id,
            "greeting": greeting,
        },
    )
    await _send_speech(ws, greeting)

    async def on_partial(text: str) -> None:
        await _send(ws, {"type": "partial", "text": text})

    async def on_turn(utterance: str, heard_at: float) -> None:
        await _send(ws, {"type": "user", "text": utterance})
        with SessionLocal() as db:
            result = await voice_agent.agent_turn(db, call, utterance, heard_at)
        await _send(
            ws,
            {
                "type": "agent",
                "text": result.say,
                "node_id": result.node_id,
                "done": result.done,
                "stepped": result.stepped,
                "call_id": str(call.call_row_id) if call.call_row_id else None,
            },
        )
        await _send_speech(ws, result.say)

    async def on_error(detail: str) -> None:
        await _send(ws, {"type": "error", "detail": detail})

    pipeline = VoicePipeline(
        encoding="pcm_s16le",
        sample_rate=16000,
        on_partial=on_partial,
        on_turn=on_turn,
        on_error=on_error,
    )
    try:
        await pipeline.start()
    except Exception as e:  # noqa: BLE001
        await _send(ws, {"type": "error", "detail": f"Could not start transcription: {e}"})
        with SessionLocal() as db:
            voice_agent.finish_call(db, call, completed=False)
        await ws.close(code=1011)
        return

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                await pipeline.feed(message["bytes"])
            elif message.get("text"):
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "end":
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await pipeline.close()
        with SessionLocal() as db:
            voice_agent.finish_call(db, call, completed=call.done)
        await _send(
            ws,
            {
                "type": "agent",
                "text": "",
                "node_id": call.current_node_id,
                "done": True,
                "stepped": False,
                "call_id": str(call.call_row_id) if call.call_row_id else None,
            },
        )
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
