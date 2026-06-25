"""Edge-TTS - free Microsoft neural voices, no API key, no account.

Produces MP3, which we transcode to mu-law/8k (see audio.codec) so it can be
streamed straight into a Twilio call.
"""
import logging

import edge_tts

from ..audio.codec import mp3_to_mulaw8k

log = logging.getLogger("tts.edge")


class EdgeTTS:
    def __init__(self, voice: str = "en-US-AriaNeural"):
        self.voice = voice

    async def synthesize(self, text: str) -> bytes:
        """Return raw mu-law 8kHz mono audio for the given text."""
        communicate = edge_tts.Communicate(text, self.voice)
        mp3 = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3.extend(chunk["data"])
        log.info("tts synthesized %d mp3 bytes for: %s", len(mp3), text[:60])
        return await mp3_to_mulaw8k(bytes(mp3))
