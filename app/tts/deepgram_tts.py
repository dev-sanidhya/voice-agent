"""Deepgram Aura TTS.

Unlike edge-tts (which returns MP3 and needs ffmpeg), Aura can emit raw
mu-law/8k directly - exactly Twilio's format - so the app stays pure-Python
and deploys with no system binaries. Uses the same Deepgram API key / free
credit as STT.
"""
import asyncio
import json
import logging
import urllib.request

log = logging.getLogger("tts.deepgram")

_ENDPOINT = (
    "https://api.deepgram.com/v1/speak"
    "?model={model}&encoding=mulaw&sample_rate=8000&container=none"
)


class DeepgramTTS:
    def __init__(self, api_key: str, model: str = "aura-asteria-en"):
        self._api_key = api_key
        self._model = model

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        return await asyncio.to_thread(self._sync_synthesize, text)

    def _sync_synthesize(self, text: str) -> bytes:
        url = _ENDPOINT.format(model=self._model)
        req = urllib.request.Request(
            url,
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={
                "Authorization": f"Token {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            audio = resp.read()
        log.info("aura synthesized %d mu-law bytes for: %s", len(audio), text[:60])
        return audio
