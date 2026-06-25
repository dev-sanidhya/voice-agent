"""Voice-agent server.

Pipeline (both call directions):

    Twilio call  <--media stream-->  /stream websocket
                                          |
                  caller mu-law audio --> STT (Deepgram)
                                          |
                            transcript --> ScriptFlow (deterministic, no AI)
                                          |
                            reply text --> TTS (edge-tts) --> mu-law
                                          |
                                          --> back over the websocket to Twilio

HTTP endpoints:
    POST /outbound   - place an outbound call to MY_VERIFIED_NUMBER
    POST /voice      - TwiML webhook (inbound calls + outbound answer); opens the stream
    WS   /stream     - bidirectional Twilio Media Stream
    GET  /health     - liveness
"""
import asyncio
import base64
import json
import logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from .config import settings
from .providers import make_stt, make_tts, make_telephony
from .flow.script_flow import ScriptFlow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Voice Agent")
telephony = make_telephony()


def _public_host(request: Request) -> str:
    """Host (no scheme) used to build callback URLs. Prefers configured/ngrok."""
    return settings.public_host or request.url.hostname or "localhost"


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "stt": settings.stt_provider,
        "tts": settings.tts_provider,
        "telephony": settings.telephony_provider,
    }


@app.post("/outbound")
async def outbound(request: Request):
    """Trigger an outbound call to the verified number."""
    if telephony is None:
        return JSONResponse({"error": "telephony provider is mock; no real call placed"}, status_code=400)
    host = _public_host(request)
    answer_url = f"https://{host}/voice"
    call_sid = telephony.place_call(settings.my_verified_number, answer_url)
    return {"call_sid": call_sid, "to": settings.my_verified_number, "answer_url": answer_url}


@app.post("/voice")
async def voice(request: Request):
    """TwiML webhook for both inbound calls and outbound answer."""
    host = _public_host(request)
    ws_url = f"wss://{host}/stream"
    # Twilio sends Direction=inbound for incoming calls, outbound-api for
    # calls we placed via REST.
    form = await request.form()
    direction = "inbound" if form.get("Direction") == "inbound" else "outbound"
    from .telephony.twilio_client import TwilioTelephony
    twiml = TwilioTelephony.stream_twiml(ws_url, direction)
    return HTMLResponse(content=twiml, media_type="application/xml")


@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    session = CallSession(ws)
    try:
        while True:
            raw = await ws.receive_text()
            await session.on_message(json.loads(raw))
    except WebSocketDisconnect:
        log.info("websocket disconnected")
    finally:
        await session.close()


class CallSession:
    """Per-call state: wires STT -> flow -> TTS -> Twilio for one media stream."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.stt = make_stt()
        self.tts = make_tts()
        self.flow = ScriptFlow()
        self._speaking = asyncio.Lock()   # one utterance at a time
        self._closed = False

    async def on_message(self, data: dict) -> None:
        event = data.get("event")
        if event == "start":
            self.stream_sid = data["start"]["streamSid"]
            self.call_sid = data["start"].get("callSid")
            direction = data["start"].get("customParameters", {}).get("direction", "outbound")
            log.info("stream start sid=%s call=%s direction=%s",
                     self.stream_sid, self.call_sid, direction)
            await self.stt.start(self._on_transcript)
            await self._say(self.flow.greeting(direction))   # agent speaks first
        elif event == "media":
            payload = data["media"]["payload"]
            await self.stt.send_audio(base64.b64decode(payload))
        elif event == "stop":
            log.info("stream stop")
            await self.close()

    async def _on_transcript(self, transcript: str) -> None:
        """STT finalized an utterance -> run the deterministic flow."""
        result = self.flow.handle(transcript)
        await self._say(result.reply)
        if result.end_call:
            await self._hangup()

    async def _say(self, text: str) -> None:
        """Synthesize text and stream it back to the caller."""
        if self._closed:
            return
        async with self._speaking:
            audio = await self.tts.synthesize(text)
            await self._send_audio(audio)

    async def _send_audio(self, mulaw: bytes) -> None:
        # Send in ~1s chunks so playback starts quickly and supports barge-in.
        for i in range(0, len(mulaw), 8000):
            if self._closed:
                return
            chunk = mulaw[i:i + 8000]
            await self.ws.send_text(json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64.b64encode(chunk).decode("ascii")},
            }))
            await asyncio.sleep(0.18)  # pace ~ realtime to avoid overrunning buffer

    async def _hangup(self) -> None:
        # Let the goodbye finish, then end the call via REST (Connect/Stream
        # keeps the call up otherwise).
        await asyncio.sleep(0.5)
        if telephony is not None and self.call_sid:
            try:
                telephony._client.calls(self.call_sid).update(status="completed")
            except Exception as e:  # noqa: BLE001
                log.warning("hangup failed: %s", e)
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self.stt.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            await self.ws.close()
        except Exception:  # noqa: BLE001
            pass
