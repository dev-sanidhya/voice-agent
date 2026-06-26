"""Mock TTS - no dependencies.

Returns mu-law silence sized to roughly match the spoken length, so the
streaming path can be tested without ffmpeg or network access.
"""
import logging

log = logging.getLogger("tts.mock")

_BYTES_PER_SEC = 8000  # mu-law 8kHz, 1 byte/sample


class MockTTS:
    def __init__(self, *_args, **_kwargs):
        pass

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        # ~150 words/min -> approximate duration from word count.
        words = max(1, len(text.split()))
        seconds = max(1.0, words / 2.5)
        log.info("mock tts: %.1fs of silence for: %s", seconds, text[:60])
        return b"\xff" * int(_BYTES_PER_SEC * seconds)
