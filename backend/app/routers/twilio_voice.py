"""Twilio Programmable Voice integration — call the AI agent by phone.

Setup (no Twilio SDK or credentials needed server-side):
  1. Expose the backend publicly, e.g.  ngrok http 8000
  2. On your Twilio number, set "A call comes in" to
     POST https://<public-host>/api/twilio/voice
     (optionally ?tree_id=<uuid> to pin a tree; defaults to the newest
     main tree).

Flow: the webhook answers with <Connect><Stream> TwiML, pointing Twilio's
bidirectional Media Stream at /api/twilio/media on the same host. Audio is
mu-law 8 kHz both ways — fed straight into Voxtral realtime STT (which
accepts pcm_mulaw natively) and synthesized back with Voxtral TTS. The same
tree-following agent as the web voice mode drives the call, so phone calls
land in the session Log and the audit flow too.

Barge-in: if the caller starts talking while agent audio is playing, we send
Twilio a "clear" message to drop the buffered playback.
"""

import asyncio
import audioop  # audioop-lts on Python >= 3.13
import base64
import json
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Tree
from app.services import tts, voice_agent
from app.services.stt import VoicePipeline

router = APIRouter()

_CHUNK_BYTES = 4000  # mu-law 8 kHz -> 500 ms per outbound media message


def _twiml(body: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
        media_type="text/xml",
    )


def _pick_tree_id(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    with SessionLocal() as db:
        tree = db.execute(
            select(Tree).order_by(Tree.is_main.desc(), Tree.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        return str(tree.id) if tree else None


@router.api_route("/voice", methods=["GET", "POST"])
async def incoming_call(request: Request, tree_id: str | None = None) -> Response:
    """Twilio "A call comes in" webhook. Returns TwiML connecting the call
    to our media-stream WebSocket."""
    form = {}
    if request.method == "POST":
        try:
            form = dict(await request.form())
        except Exception:  # noqa: BLE001
            form = {}
    caller = form.get("From") or request.query_params.get("From") or "unknown"

    chosen = _pick_tree_id(tree_id)
    if chosen is None:
        return _twiml(
            "<Say>No call procedure is configured yet. Goodbye.</Say><Hangup/>"
        )

    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    ws_url = f"wss://{host}/api/twilio/media"
    return _twiml(
        f'<Connect><Stream url="{escape(ws_url, {chr(34): "&quot;"})}">'
        f'<Parameter name="tree_id" value="{escape(chosen, {chr(34): "&quot;"})}"/>'
        f'<Parameter name="caller" value="{escape(caller, {chr(34): "&quot;"})}"/>'
        f"</Stream></Connect>"
    )


@router.websocket("/media")
async def media_stream(ws: WebSocket) -> None:
    """Twilio bidirectional Media Stream endpoint."""
    await ws.accept()

    stream_sid: str | None = None
    call: voice_agent.VoiceCall | None = None
    pipeline: VoicePipeline | None = None
    playing = False  # agent audio queued on Twilio's side
    mark_seq = 0
    send_lock = asyncio.Lock()

    async def send_json(payload: dict) -> None:
        async with send_lock:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:  # noqa: BLE001
                pass

    async def speak(text: str) -> None:
        """TTS -> chunked mu-law media messages -> mark (echoed on playback end)."""
        nonlocal playing, mark_seq
        if stream_sid is None:
            return
        try:
            mulaw = await tts.synth_mulaw8k(text)
        except Exception as e:  # noqa: BLE001
            print(f"[twilio] TTS failed: {e}")
            return
        playing = True
        for i in range(0, len(mulaw), _CHUNK_BYTES):
            await send_json(
                {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": base64.b64encode(mulaw[i : i + _CHUNK_BYTES]).decode("ascii")
                    },
                }
            )
        mark_seq += 1
        await send_json(
            {"event": "mark", "streamSid": stream_sid, "mark": {"name": f"utt-{mark_seq}"}}
        )

    async def on_partial(_text: str) -> None:
        # Caller is talking. If agent audio is still queued, barge in: drop it.
        nonlocal playing
        if playing and stream_sid is not None:
            playing = False
            await send_json({"event": "clear", "streamSid": stream_sid})

    async def on_turn(utterance: str, heard_at: float) -> None:
        if call is None:
            return
        with SessionLocal() as db:
            result = await voice_agent.agent_turn(db, call, utterance, heard_at)
        await speak(result.say)
        if result.done:
            # Give Twilio a moment to flush the goodbye audio, then close the
            # stream — with <Connect>, closing the socket ends the call. The
            # main receive loop unwinds via WebSocketDisconnect.
            await asyncio.sleep(max(1.0, len(result.say) * 0.06))
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass

    async def on_error(detail: str) -> None:
        print(f"[twilio] {detail}")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            event = msg.get("event")

            if event == "start":
                start = msg.get("start", {})
                stream_sid = start.get("streamSid") or msg.get("streamSid")
                params = start.get("customParameters", {}) or {}
                tree_id = params.get("tree_id")
                caller = params.get("caller", "unknown")
                with SessionLocal() as db:
                    tree = db.get(Tree, tree_id) if tree_id else None
                    if tree is None:
                        print(f"[twilio] tree {tree_id} not found, dropping call")
                        break
                    call, greeting = voice_agent.start_call(
                        db, tree, "phone", f"AI voice agent (phone · {caller})"
                    )
                pipeline = VoicePipeline(
                    encoding="pcm_mulaw",
                    sample_rate=8000,
                    on_partial=on_partial,
                    on_turn=on_turn,
                    on_error=on_error,
                )
                await pipeline.start()
                await speak(greeting)

            elif event == "media" and pipeline is not None:
                payload = msg.get("media", {}).get("payload")
                if payload:
                    await pipeline.feed(base64.b64decode(payload))

            elif event == "mark":
                playing = False

            elif event == "stop":
                break

    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError: receive after the socket was closed from on_turn.
        pass
    finally:
        if pipeline is not None:
            await pipeline.close()
        if call is not None:
            with SessionLocal() as db:
                voice_agent.finish_call(db, call, completed=call.done)
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
