"""Inworld TTS-2 - Hindi-capable, low-latency, real emotion steering.

Emotion is genuine here (unlike Sarvam/smallest.ai): Inworld TTS-2 takes a
natural-language steering instruction wrapped in square brackets, prepended to
the text - it's NOT spoken, it directs the delivery. Long descriptive prompts
work better than short labels.

Inworld returns mu-law @ 8kHz natively (audio_encoding=MULAW), so it drops
straight into Twilio - no resampling. The decision of WHAT to say stays in the
deterministic flow - no AI in the loop.
"""
import base64
import json
import logging

import httpx

log = logging.getLogger("tts.inworld")

_BASE = "https://api.inworld.ai/tts/v1/voice"
_STREAM = "https://api.inworld.ai/tts/v1/voice:stream"
_MODEL = "inworld-tts-2"

# Emotion -> natural-language steering instruction (bracketed, prepended).
_EMOTION_STEER = {
    "neutral":    "[speak in a clear, neutral, matter-of-fact tone]",
    "friendly":   "[speak in a warm, friendly, welcoming tone, like greeting a familiar customer]",
    "cheerful":   "[speak in a bright, cheerful, enthusiastic tone with a big smile in your voice]",
    "empathetic": "[speak in a soft, caring, empathetic tone, slowly and reassuringly, as if comforting someone]",
    "apologetic": "[speak in a sincere, gentle, apologetic tone, as if offering a heartfelt apology]",
}


class InworldTTS:
    def __init__(self, api_key: str, voice: str = "Riya"):
        self.api_key = api_key      # already base64 key:secret, used as Basic auth
        self.voice = voice          # default: "Riya" (Hindi, call-center tagged)

    def _body(self, text: str, emotion: str) -> dict:
        steer = _EMOTION_STEER.get(emotion, "")
        prompt = f"{steer} {text}".strip()
        return {
            "text": prompt,
            "voiceId": self.voice,
            "modelId": _MODEL,
            "audio_config": {"audio_encoding": "MULAW", "sample_rate_hertz": 8000},
        }

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Basic {self.api_key}", "Content-Type": "application/json"}

    async def stream(self, text: str, emotion: str = "neutral"):
        """Yield raw mu-law 8kHz chunks as Inworld generates them (low latency)."""
        async with httpx.AsyncClient(timeout=45) as client:
            async with client.stream("POST", _STREAM, headers=self._headers,
                                     json=self._body(text, emotion)) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    audio_b64 = msg.get("result", {}).get("audioContent") or msg.get("audioContent")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """REST fallback - returns the full mu-law clip in one shot."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_BASE, headers=self._headers, json=self._body(text, emotion))
            resp.raise_for_status()
            data = resp.json()
        audio = base64.b64decode(data.get("audioContent", ""))
        log.info("tts (%s) synthesized %d mulaw bytes for: %s", emotion, len(audio), text[:60])
        return audio
