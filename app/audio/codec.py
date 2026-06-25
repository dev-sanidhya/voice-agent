"""Audio format helpers.

Twilio Media Streams use 8 kHz, mono, 8-bit G.711 mu-law (a.k.a. PCMU),
sent as base64 in 20 ms frames (160 bytes each).

- Inbound caller audio is already mu-law/8k, which Deepgram accepts directly
  (encoding=mulaw, sample_rate=8000) - no conversion needed.
- Outbound TTS (edge-tts) produces MP3 at 24 kHz, so we transcode it to
  mu-law/8k with ffmpeg before sending it back to Twilio.
"""
import asyncio

FRAME_BYTES = 160          # 20 ms of mu-law @ 8 kHz
SILENCE_BYTE = b"\xff"     # mu-law digital silence


async def mp3_to_mulaw8k(mp3_bytes: bytes) -> bytes:
    """Transcode MP3 -> raw mu-law 8kHz mono using ffmpeg via stdin/stdout."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",
        "-ar", "8000", "-ac", "1",
        "-f", "mulaw", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(input=mp3_bytes)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {err.decode(errors='ignore')}")
    return out


def chunk_frames(data: bytes, size: int = FRAME_BYTES):
    """Yield fixed-size frames, padding the final one with mu-law silence."""
    for i in range(0, len(data), size):
        frame = data[i:i + size]
        if len(frame) < size:
            frame = frame + SILENCE_BYTE * (size - len(frame))
        yield frame
