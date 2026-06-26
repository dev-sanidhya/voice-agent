"""OpenAI gpt-4o-mini-tts - emotional, no AI in the decision loop.

The flow (app/flow/script_flow.py) pre-authors a fixed emotion tag per
scripted line - the model only renders that emotion in *speech* via a
steering instruction, it does not decide *what* to say.

OpenAI's "pcm" response is fixed at 24kHz/16-bit/mono (no sample_rate param),
so we downsample to 8kHz with stdlib audioop before mu-law encoding - no
ffmpeg needed (Render free tier has none).
"""
import audioop
import logging

import httpx

log = logging.getLogger("tts.openai")

_URL = "https://api.openai.com/v1/audio/speech"
_SRC_RATE = 24000
_DST_RATE = 8000

# Pre-authored emotion -> steering instruction for gpt-4o-mini-tts.
_EMOTION_INSTRUCTIONS = {
    "friendly": "Speak in a warm, friendly tone.",
    "cheerful": "Speak with cheerfulness and enthusiasm.",
    "empathetic": "Speak in an empathetic, understanding tone.",
    "apologetic": "Speak in a soft, apologetic tone.",
    "neutral": "Speak in a clear, neutral tone.",
}


class OpenAITTS:
    def __init__(self, api_key: str, voice: str = "alloy"):
        self.api_key = api_key
        self.voice = voice

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """Return raw mu-law 8kHz mono audio for the given text + emotion."""
        instructions = _EMOTION_INSTRUCTIONS.get(emotion, _EMOTION_INSTRUCTIONS["neutral"])

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini-tts",
                    "voice": self.voice,
                    "input": text,
                    "instructions": instructions,
                    "response_format": "pcm",
                },
            )
            resp.raise_for_status()
            pcm24k = resp.content

        pcm8k, _ = audioop.ratecv(pcm24k, 2, 1, _SRC_RATE, _DST_RATE, None)
        mulaw = audioop.lin2ulaw(pcm8k, 2)
        log.info("tts (%s) synthesized %d mulaw bytes for: %s", emotion, len(mulaw), text[:60])
        return mulaw
