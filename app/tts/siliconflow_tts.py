"""SiliconFlow TTS (CosyVoice2) - emotional, no AI in the decision loop.

The flow (app/flow/script_flow.py) pre-authors a fixed emotion tag per
scripted line - the model only renders that emotion in *speech*, it does not
decide *what* to say. We request raw PCM at 8kHz directly (CosyVoice2
supports this natively) and convert PCM16 -> mu-law with stdlib audioop,
so no ffmpeg is required on the host (Render free tier has none).
"""
import audioop
import logging

import httpx

log = logging.getLogger("tts.siliconflow")

_URL = "https://api.siliconflow.com/v1/audio/speech"

# Pre-authored emotion -> natural-language instruction CosyVoice2 understands.
_EMOTION_INSTRUCTIONS = {
    "friendly": "Can you say this in a warm, friendly tone?",
    "cheerful": "Can you say this with cheerfulness and enthusiasm?",
    "empathetic": "Can you say this in an empathetic, understanding tone?",
    "apologetic": "Can you say this in a soft, apologetic tone?",
    "neutral": None,
}


class SiliconFlowTTS:
    def __init__(self, api_key: str, voice: str = "FunAudioLLM/CosyVoice2-0.5B:anna"):
        self.api_key = api_key
        self.voice = voice
        self.model = voice.split(":")[0]

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """Return raw mu-law 8kHz mono audio for the given text + emotion."""
        instruction = _EMOTION_INSTRUCTIONS.get(emotion)
        prompt = f"{instruction}<|endofprompt|>{text}" if instruction else text

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "voice": self.voice,
                    "input": prompt,
                    "response_format": "pcm",
                    "sample_rate": 8000,
                },
            )
            resp.raise_for_status()
            pcm16 = resp.content

        mulaw = audioop.lin2ulaw(pcm16, 2)  # 2 bytes/sample = 16-bit PCM
        log.info("tts (%s) synthesized %d mulaw bytes for: %s", emotion, len(mulaw), text[:60])
        return mulaw
