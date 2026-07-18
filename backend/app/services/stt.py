"""Voxtral realtime transcription with silence-based turn taking.

One VoicePipeline per live call. Audio chunks are fed in (browser PCM16 or
Twilio mu-law — Voxtral accepts both natively via AudioFormat), transcript
deltas stream back, and a watchdog finalizes a caller "turn" once no new
delta has arrived for voice_turn_silence_ms. The on_turn callback is awaited
inline, so at most one agent turn runs at a time; speech that arrives while
the agent is thinking simply accumulates into the next turn.
"""

import asyncio
import time
from typing import Awaitable, Callable, Optional

from mistralai.client import Mistral
from mistralai.client.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    TranscriptionStreamTextDelta,
)

from app.config import settings

OnText = Callable[[str], Awaitable[None]]
OnTurn = Callable[[str, float], Awaitable[None]]  # (utterance, heard_at_offset_s)


class VoicePipeline:
    def __init__(
        self,
        *,
        encoding: str,
        sample_rate: int,
        on_partial: Optional[OnText],
        on_turn: OnTurn,
        on_error: Optional[OnText] = None,
    ) -> None:
        self._encoding = encoding
        self._sample_rate = sample_rate
        self._on_partial = on_partial
        self._on_turn = on_turn
        self._on_error = on_error
        self._conn = None
        self._tasks: list[asyncio.Task] = []
        self._buffer = ""
        self._buffer_started: float | None = None  # offset of first delta of turn
        self._last_delta: float | None = None
        self._t0 = time.monotonic()
        self._closed = False

    async def start(self) -> None:
        client = Mistral(api_key=settings.mistral_api_key)
        self._conn = await client.audio.realtime.connect(
            model=settings.mistral_realtime_model,
            audio_format=AudioFormat(
                encoding=self._encoding, sample_rate=self._sample_rate
            ),
            target_streaming_delay_ms=settings.voice_streaming_delay_ms,
        )
        self._tasks = [
            asyncio.create_task(self._consume_events()),
            asyncio.create_task(self._turn_watchdog()),
        ]

    async def feed(self, chunk: bytes) -> None:
        if self._conn is not None and not self._conn.is_closed:
            await self._conn.send_audio(chunk)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------

    def _offset(self) -> float:
        return time.monotonic() - self._t0

    async def _consume_events(self) -> None:
        assert self._conn is not None
        try:
            async for event in self._conn:
                if isinstance(event, TranscriptionStreamTextDelta):
                    if not event.text:
                        continue
                    if self._buffer_started is None:
                        self._buffer_started = self._offset()
                    self._buffer += event.text
                    self._last_delta = self._offset()
                    if self._on_partial is not None:
                        await self._on_partial(self._buffer.strip())
                elif isinstance(event, RealtimeTranscriptionError):
                    if self._on_error is not None:
                        await self._on_error(str(event.error))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — surface, don't crash the call
            if self._on_error is not None and not self._closed:
                await self._on_error(f"transcription stream failed: {e}")

    async def _turn_watchdog(self) -> None:
        silence = settings.voice_turn_silence_ms / 1000.0
        flushed_at: float | None = None
        while True:
            await asyncio.sleep(0.15)
            if (
                self._buffer.strip()
                and self._last_delta is not None
                and self._offset() - self._last_delta >= silence
            ):
                # The transcriber holds the tail of an utterance back by the
                # streaming delay — flush once per candidate turn and give
                # late deltas a moment to land before finalizing.
                if flushed_at is None or flushed_at < self._last_delta:
                    flushed_at = self._offset()
                    try:
                        if self._conn is not None and not self._conn.is_closed:
                            await self._conn.flush_audio()
                    except Exception:  # noqa: BLE001
                        pass
                    await asyncio.sleep(0.4)
                    continue  # re-check silence; new deltas reset the clock
                utterance = self._buffer.strip()
                heard_at = self._buffer_started or self._offset()
                self._buffer = ""
                self._buffer_started = None
                try:
                    await self._on_turn(utterance, heard_at)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001
                    if self._on_error is not None:
                        await self._on_error(f"agent turn failed: {e}")
