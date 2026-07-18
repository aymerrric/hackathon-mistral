"""Text -> speech via Mistral Voxtral TTS (voxtral-mini-tts).

The API returns base64 audio; we request WAV (24 kHz mono PCM16) and offer
two flavours:
  - synth_wav()      -> WAV bytes, played directly by the browser client.
  - synth_mulaw8k()  -> raw mu-law 8 kHz bytes, the Twilio Media Streams
                        wire format (no headers).

Preset voices are addressed by name (e.g. "Jane - Neutral") and resolved to
their id once via the Voices API, then cached for the process lifetime.
"""

import audioop  # audioop-lts on Python >= 3.13
import base64
import struct
import threading

from mistralai.client import Mistral

from app.config import settings

_voice_id_cache: dict[str, str] = {}
_voice_lock = threading.Lock()


def _client() -> Mistral:
    return Mistral(api_key=settings.mistral_api_key)


def _resolve_voice_id(client: Mistral, voice_name: str) -> str:
    """Preset voice name -> voice id, cached. Falls back to the first preset
    voice if the configured name is not found."""
    with _voice_lock:
        cached = _voice_id_cache.get(voice_name)
    if cached:
        return cached

    res = client.audio.voices.list(type_="preset", limit=100)
    items = res.items or []
    if not items:
        raise RuntimeError("No preset TTS voices available on this account")
    chosen = next((v for v in items if v.name == voice_name), items[0])
    with _voice_lock:
        _voice_id_cache[voice_name] = chosen.id
    return chosen.id


def _parse_wav(wav: bytes) -> tuple[bytes, int]:
    """Return (pcm16 mono frames, sample_rate) from a simple RIFF wav."""
    if len(wav) < 44 or wav[:4] != b"RIFF":
        raise RuntimeError("TTS did not return a RIFF wav")
    channels = struct.unpack_from("<H", wav, 22)[0]
    rate = struct.unpack_from("<I", wav, 24)[0]
    bits = struct.unpack_from("<H", wav, 34)[0]
    # Find the data chunk (usually at offset 36).
    off = 12
    data = b""
    while off + 8 <= len(wav):
        cid = wav[off : off + 4]
        size = struct.unpack_from("<I", wav, off + 4)[0]
        if cid == b"data":
            data = wav[off + 8 : off + 8 + size]
            break
        off += 8 + size + (size % 2)
    if not data:
        raise RuntimeError("TTS wav has no data chunk")
    if bits != 16:
        raise RuntimeError(f"Unexpected TTS bit depth: {bits}")
    if channels == 2:
        data = audioop.tomono(data, 2, 0.5, 0.5)
    return data, rate


async def synth_wav(text: str) -> bytes:
    """Text -> WAV bytes (as returned by the API, 24 kHz mono PCM16)."""
    client = _client()
    voice_id = _resolve_voice_id(client, settings.mistral_tts_voice)
    try:
        res = await client.audio.speech.complete_async(
            model=settings.mistral_tts_model,
            input=text,
            voice_id=voice_id,
            response_format="wav",
        )
    except Exception as e:
        raise RuntimeError(f"Voxtral TTS failed: {e}") from e
    return base64.b64decode(res.audio_data)


async def synth_mulaw8k(text: str) -> bytes:
    """Text -> raw mu-law 8 kHz mono bytes (Twilio Media Streams format)."""
    pcm, rate = _parse_wav(await synth_wav(text))
    if rate != 8000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 8000, None)
    return audioop.lin2ulaw(pcm, 2)
