"""smallest.ai Lightning TTS - low-latency, Hindi-native, no AI in the loop.

Built for Indian languages (language="hi") with Indian-accent voices, which
makes it the strongest fit for Delhi/NCR Hinglish. The flow pre-authors a
fixed emotion tag per line; Lightning's REST `get_speech` has no direct
emotion field, so we approximate emotion with a per-line speed adjustment
(slower for empathetic/apologetic, brisker for cheerful) and rely on the
voice's natural expressiveness.

The API returns WAV (24kHz); we parse it with the stdlib `wave` module,
downmix/resample to 8kHz, and mu-law encode for Twilio - no ffmpeg needed.
"""
import audioop
import io
import logging
import wave

import httpx

log = logging.getLogger("tts.smallest")

_URL = "https://waves-api.smallest.ai/api/v1/lightning/get_speech"

# Emotion -> speech speed (Lightning has no emotion param; speed is our proxy).
_EMOTION_SPEED = {
    "neutral": 1.0,
    "friendly": 1.0,
    "cheerful": 1.08,
    "empathetic": 0.9,
    "apologetic": 0.88,
}


class SmallestTTS:
    def __init__(self, api_key: str, voice: str = "diya", language: str = "hi"):
        self.api_key = api_key
        self.voice = voice
        self.language = language

    async def synthesize(self, text: str, emotion: str = "neutral") -> bytes:
        """Return raw mu-law 8kHz mono audio for the given text + emotion."""
        speed = _EMOTION_SPEED.get(emotion, 1.0)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "text": text,
                    "voice_id": self.voice,
                    "sample_rate": 24000,
                    "speed": speed,
                    "language": self.language,
                    "output_format": "wav",
                },
            )
            resp.raise_for_status()
            wav_bytes = resp.content

        # Robustly parse the WAV container (handles header size, rate, channels).
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            sw = w.getsampwidth()
            pcm = w.readframes(w.getnframes())

        if nch == 2:
            pcm = audioop.tomono(pcm, sw, 0.5, 0.5)
        if sr != 8000:
            pcm, _ = audioop.ratecv(pcm, sw, 1, sr, 8000, None)
        mulaw = audioop.lin2ulaw(pcm, sw)
        log.info("tts (%s) synthesized %d mulaw bytes for: %s", emotion, len(mulaw), text[:60])
        return mulaw
