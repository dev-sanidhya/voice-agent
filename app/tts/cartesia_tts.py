"""Cartesia Sonic 3.5 TTS - ultra-low-latency (sub-90ms), WebSocket streaming.

Sonic returns mu-law @ 8kHz natively (output_format encoding=pcm_mulaw,
sample_rate=8000), so it drops straight into Twilio - no resampling.

Emotion: Sonic exposes generation_config (speed, volume); we map our
pre-authored emotion tags to those (brisker/louder for cheerful, slower/softer
for empathetic/apologetic). The decision of WHAT to say stays in the
deterministic flow - no AI in the loop.
"""
import base64
import json
import logging
import uuid

import httpx
import websockets

log = logging.getLogger("tts.cartesia")

_VERSION = "2024-11-13"
_WS_URL = f"wss://api.cartesia.ai/tts/websocket?cartesia_version={_VERSION}"
_REST_URL = "https://api.cartesia.ai/tts/bytes"
_MODEL = "sonic-3.5"

# Emotion -> (speed 0.6-1.5, volume 0.5-2.0). No native emotion enum we rely
# on; speed/volume is our proxy alongside the voice's own character.
_EMOTION_PARAMS = {
    "neutral":    (1.0, 1.0),
    "friendly":   (1.0, 1.05),
    "cheerful":   (1.1, 1.15),
    "empathetic": (0.92, 0.95),
    "apologetic": (0.9, 0.9),
}


class CartesiaTTS:
    def __init__(self, api_key: str, voice: str = "95d51f79-c397-46f9-b49a-23763d3eaa2d",
                 language: str = "hi"):
        self.api_key = api_key
        self.voice = voice          # default: "Arushi - Hinglish Speaker"
        self.language = language

    def _payload(self, text: str, emotion: str) -> dict:
        speed, volume = _EMOTION_PARAMS.get(emotion, (1.0, 1.0))
        return {
            "model_id": _MODEL,
            "transcript": text,
            "voice": {"mode": "id", "id": self.voice},
            "language": self.language,
            "output_format": {"container": "raw", "encoding": "pcm_mulaw", "sample_rate": 8000},
            "generation_config": {"speed": speed, "volume": volume},
        }

    async def stream(self, text: str, emotion: str = "neutral"):
        """Yield raw mu-law 8kHz chunks as Sonic generates them (low latency)."""
        payload = self._payload(text, emotion)
        payload["context_id"] = uuid.uuid4().hex
        payload["continue"] = False
        async with websockets.connect(
            _WS_URL, additional_headers={"X-API-Key": self.api_key}
        ) as ws:
            await ws.send(json.dumps(payload))
            async for raw in ws:
                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "chunk":
                    data = msg.get("data")
                    if data:
                        yield base64.b64decode(data)
                    if msg.get("done"):
                        break
                elif mtype == "done":
                    break
                elif mtype == "error":
                    log.error("cartesia ws error: %s", msg.get("error") or msg)
                    break

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """REST fallback - returns the full mu-law clip in one shot."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _REST_URL,
                headers={"X-API-Key": self.api_key, "Cartesia-Version": _VERSION},
                json=self._payload(text, emotion),
            )
            resp.raise_for_status()
            audio = resp.content
        log.info("tts (%s) synthesized %d mulaw bytes for: %s", emotion, len(audio), text[:60])
        return audio
