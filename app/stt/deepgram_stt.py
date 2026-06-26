"""Deepgram streaming STT over a raw websocket.

We talk to Deepgram's live endpoint directly with the `websockets` library
instead of the SDK - the SDK's API churns between majors, while the wire
protocol is stable. Twilio's mu-law/8k audio is forwarded as-is (Deepgram
accepts encoding=mulaw, sample_rate=8000), and finalized utterances are
pushed to the callback for the deterministic flow.
"""
import asyncio
import json
import logging
from urllib.parse import urlencode

import websockets

from .base import OnTranscript

log = logging.getLogger("stt.deepgram")

def _build_url(language: str) -> str:
    params = {
        "model": "nova-2",
        "language": language,
        "encoding": "mulaw",
        "sample_rate": "8000",
        "channels": "1",
        "punctuate": "true",
        "interim_results": "true",
        "endpointing": "300",        # ms of silence => end of utterance
        "utterance_end_ms": "1000",
    }
    return "wss://api.deepgram.com/v1/listen?" + urlencode(params)


class DeepgramSTT:
    def __init__(self, api_key: str, language: str = "en-US"):
        self._api_key = api_key
        self._language = language
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._on_transcript: OnTranscript | None = None

    async def start(self, on_transcript: OnTranscript) -> None:
        self._on_transcript = on_transcript
        self._ws = await websockets.connect(
            _build_url(self._language), additional_headers={"Authorization": f"Token {self._api_key}"}
        )
        self._recv_task = asyncio.create_task(self._receive_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        log.info("deepgram stream started")

    async def _receive_loop(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if msg.get("type") != "Results":
                    continue
                alt = msg["channel"]["alternatives"][0]
                sentence = alt.get("transcript", "")
                # Act only on finalized speech segments, not partials.
                if sentence and msg.get("is_final") and msg.get("speech_final"):
                    log.info("transcript: %s", sentence)
                    if self._on_transcript:
                        await self._on_transcript(sentence)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:  # noqa: BLE001
            log.error("deepgram receive error: %s", e)

    async def _keepalive_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(8)
                if self._ws:
                    await self._ws.send(json.dumps({"type": "KeepAlive"}))
        except (asyncio.CancelledError, websockets.ConnectionClosed):
            pass

    async def send_audio(self, mulaw_chunk: bytes) -> None:
        if self._ws:
            try:
                await self._ws.send(mulaw_chunk)
            except websockets.ConnectionClosed:
                pass

    async def stop(self) -> None:
        for task in (self._keepalive_task, self._recv_task):
            if task:
                task.cancel()
        if self._ws:
            try:
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None
