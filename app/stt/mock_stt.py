"""Mock STT - no account required.

Ignores the audio and emits a scripted sequence of transcripts on a timer so
the rest of the pipeline (flow -> TTS -> telephony) can be exercised end to
end with zero cloud credentials. Useful for local development and CI.
"""
import asyncio
import logging

from .base import OnTranscript

log = logging.getLogger("stt.mock")

_SCRIPT = ["yes", "pricing", "business hours", "no thanks"]


class MockSTT:
    def __init__(self, *_args, **_kwargs):
        self._task: asyncio.Task | None = None
        self._on_transcript: OnTranscript | None = None

    async def start(self, on_transcript: OnTranscript) -> None:
        self._on_transcript = on_transcript
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            for line in _SCRIPT:
                await asyncio.sleep(4)
                if self._on_transcript:
                    log.info("mock transcript: %s", line)
                    await self._on_transcript(line)
        except asyncio.CancelledError:
            pass

    async def send_audio(self, mulaw_chunk: bytes) -> None:
        return  # mock ignores real audio

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
