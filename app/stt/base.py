"""STT provider interface.

A provider is a streaming sink: feed it raw audio bytes, and it invokes a
callback with finalized transcript text. Implementations: Deepgram (real),
Mock (no account needed).
"""
from typing import Awaitable, Callable, Protocol

# Called with (transcript_text) whenever a final utterance is recognized.
OnTranscript = Callable[[str], Awaitable[None]]


class STTProvider(Protocol):
    async def start(self, on_transcript: OnTranscript) -> None: ...
    async def send_audio(self, mulaw_chunk: bytes) -> None: ...
    async def stop(self) -> None: ...
