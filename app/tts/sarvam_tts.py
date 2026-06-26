"""Sarvam Bulbul TTS - Hindi-native, with low-latency WebSocket streaming.

Two paths:
- stream(): opens a WebSocket, sends config+text+flush, and yields mu-law
  chunks as they're generated. This is the low-latency path - audio starts
  playing on the call as soon as the first chunk arrives, instead of waiting
  for the whole clip.
- synthesize(): a REST fallback that returns the full mu-law clip.

Sarvam returns mu-law @ 8kHz natively (output_audio_codec="mulaw",
speech_sample_rate="8000"), so it drops straight into Twilio - no resampling.

Emotion: Bulbul has no explicit per-request emotion field, so we approximate
it with pace (brisker for cheerful, slower for empathetic/apologetic) plus a
temperature nudge for expressiveness. The decision of WHAT to say stays in the
deterministic flow - no AI in the loop.
"""
import base64
import json
import logging

import httpx
import websockets

log = logging.getLogger("tts.sarvam")

_WS_URL = "wss://api.sarvam.ai/text-to-speech/ws?model=bulbul:v3&send_completion_event=true"
_REST_URL = "https://api.sarvam.ai/text-to-speech"

# Emotion -> (pace, temperature). No native emotion param; this is our proxy.
_EMOTION_PARAMS = {
    "neutral":    (1.0, 0.5),
    "friendly":   (1.05, 0.7),
    "cheerful":   (1.12, 0.9),
    "empathetic": (0.92, 0.6),
    "apologetic": (0.9, 0.55),
}


class SarvamTTS:
    def __init__(self, api_key: str, voice: str = "priya", language: str = "hi-IN"):
        self.api_key = api_key
        self.voice = voice
        self.language = language

    def _config(self, emotion: str) -> dict:
        pace, temperature = _EMOTION_PARAMS.get(emotion, (1.0, 0.6))
        return {
            "target_language_code": self.language,
            "speaker": self.voice,
            "speech_sample_rate": "8000",
            "output_audio_codec": "mulaw",
            "pace": pace,
            "temperature": temperature,
        }

    async def stream(self, text: str, emotion: str = "neutral"):
        """Yield raw mu-law 8kHz chunks as Sarvam generates them (low latency)."""
        async with websockets.connect(
            _WS_URL, additional_headers={"api-subscription-key": self.api_key}
        ) as ws:
            await ws.send(json.dumps({"type": "config", "data": self._config(emotion)}))
            await ws.send(json.dumps({"type": "text", "data": {"text": text}}))
            await ws.send(json.dumps({"type": "flush"}))
            async for raw in ws:
                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "audio":
                    audio_b64 = msg.get("data", {}).get("audio")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                elif mtype == "event" and msg.get("data", {}).get("event_type") == "final":
                    break
                elif mtype == "error":
                    log.error("sarvam ws error: %s", msg.get("data"))
                    break

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """REST fallback - returns the full mu-law clip in one shot."""
        cfg = self._config(emotion)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _REST_URL,
                headers={"api-subscription-key": self.api_key},
                json={"text": text, "model": "bulbul:v3", **cfg},
            )
            resp.raise_for_status()
            data = resp.json()
        audio = b"".join(base64.b64decode(a) for a in data.get("audios", []))
        log.info("tts (%s) synthesized %d mulaw bytes for: %s", emotion, len(audio), text[:60])
        return audio
