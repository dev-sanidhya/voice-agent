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

# Pre-authored emotion -> rich steering instruction for gpt-4o-mini-tts.
# gpt-4o-mini-tts responds strongly to detailed affect/pacing/emphasis cues,
# so each instruction describes voice affect, pacing, and intonation to make
# the emotions clearly distinct from one another.
_EMOTION_INSTRUCTIONS = {
    "neutral": (
        "Voice: calm, even, and professional. Pace: steady and measured. "
        "Emotion: flat and matter-of-fact, like a clear announcement, no strong feeling."
    ),
    "friendly": (
        "Voice: warm, approachable, and personable, with a smile in your voice. "
        "Pace: relaxed and conversational. Intonation: gentle, with light upward lilts, "
        "like talking to a friend you're happy to help."
    ),
    "cheerful": (
        "Voice: bright, bubbly, and full of positive energy. Pace: lively and upbeat. "
        "Emotion: genuinely excited and joyful, with noticeable enthusiasm and a big smile, "
        "as if sharing great news."
    ),
    "empathetic": (
        "Voice: soft, gentle, and caring. Pace: slow and unhurried, with thoughtful pauses. "
        "Emotion: warm and deeply understanding, conveying genuine concern and reassurance, "
        "as if comforting someone going through a hard time."
    ),
    "apologetic": (
        "Voice: soft, sincere, and humble. Pace: slow and careful. "
        "Emotion: genuinely regretful and remorseful, with a gentle, contrite tone, "
        "as if offering a heartfelt apology."
    ),
}


class OpenAITTS:
    def __init__(self, api_key: str, voice: str = "alloy"):
        self.api_key = api_key
        self.voice = voice

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """Return raw mu-law 8kHz mono audio for the given text + emotion."""
        emo = _EMOTION_INSTRUCTIONS.get(emotion, _EMOTION_INSTRUCTIONS["neutral"])
        # Cue a fluent, native Hindi delivery so the Hindi tone sounds natural
        # rather than accented English-Hindi.
        instructions = (
            "Speak as a fluent, native Hindi speaker with a natural Indian accent "
            "and authentic Hindi pronunciation. " + emo
        )

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
