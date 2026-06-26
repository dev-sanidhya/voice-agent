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
import sys
import traceback

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .config import settings
from .providers import make_stt, make_tts, make_telephony
from .flow.script_flow import ScriptFlow
from .flow.showcase_flow import ShowcaseFlow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Voice Agent")
telephony = make_telephony()

_last_error: str | None = None


@app.get("/debug/last-error")
async def last_error():
    return {"last_error": _last_error}


# --- Temporary: generate a Hindi sample from a smallest.ai voice (research) ---
# Runs from Render (which can reach smallest.ai's Mumbai endpoint reliably,
# unlike local). Separate from the live call path. Remove after voice pick.
_SAMPLE_TOKEN = "vgensample"
_SAMPLE_HINDI = "नमस्ते, मैं आपकी कॉल का जवाब देने के लिए यहाँ हूँ। बताइए, मैं आपकी कैसे मदद कर सकती हूँ?"


@app.get("/admin/smallest-sample")
async def smallest_sample(voice: str, t: str = ""):
    if t != _SAMPLE_TOKEN:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not settings.smallest_api_key:
        return JSONResponse({"error": "SMALLEST_API_KEY not set on server"}, status_code=400)
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(
                "https://waves-api.smallest.ai/api/v1/lightning/get_speech",
                headers={"Authorization": f"Bearer {settings.smallest_api_key}"},
                json={"text": _SAMPLE_HINDI, "voice_id": voice,
                      "sample_rate": 24000, "language": "hi", "output_format": "wav"},
            )
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)
    if r.status_code != 200:
        return JSONResponse({"error": r.text[:300], "status": r.status_code}, status_code=502)
    return Response(content=r.content, media_type="audio/wav")


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
        "flow_mode": settings.flow_mode,
        "python": sys.version,
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
        self.showcase = ShowcaseFlow()
        self._speaking = asyncio.Lock()   # one utterance at a time
        self._closed = False
        # Twilio echoes a "mark" event back once buffered audio has actually
        # finished playing - we use this to sequence speech with real pauses.
        self._pending_marks: dict[str, asyncio.Future] = {}
        self._mark_seq = 0

    async def on_message(self, data: dict) -> None:
        event = data.get("event")
        if event == "start":
            self.stream_sid = data["start"]["streamSid"]
            self.call_sid = data["start"].get("callSid")
            direction = data["start"].get("customParameters", {}).get("direction", "outbound")
            log.info("stream start sid=%s call=%s direction=%s mode=%s",
                     self.stream_sid, self.call_sid, direction, settings.flow_mode)
            if settings.flow_mode == "showcase":
                asyncio.create_task(self._run_showcase())
                return
            await self.stt.start(self._on_transcript)
            greeting = self.flow.greeting(direction)          # agent speaks first
            await self._say(greeting.reply, greeting.emotion)
        elif event == "media":
            payload = data["media"]["payload"]
            await self.stt.send_audio(base64.b64decode(payload))
        elif event == "mark":
            # Audio queued before this mark has finished playing on the call.
            name = data.get("mark", {}).get("name")
            fut = self._pending_marks.pop(name, None)
            if fut and not fut.done():
                fut.set_result(True)
        elif event == "stop":
            log.info("stream stop")
            await self.close()

    async def _run_showcase(self) -> None:
        """Auto-play every showcase line back-to-back, then hang up."""
        while True:
            line = self.showcase.next_line()
            if line is None:
                break
            text, emotion, is_last = line
            await self._say(text, emotion)
            await asyncio.sleep(0.8)  # real silent gap between lines
            if is_last:
                await self._hangup()

    async def _on_transcript(self, transcript: str) -> None:
        """STT finalized an utterance -> run the deterministic flow."""
        result = self.flow.handle(transcript)
        await self._say(result.reply, result.emotion)
        if result.end_call:
            await self._hangup()

    async def _say(self, text: str, emotion: str = "neutral") -> None:
        """Speak text (with its pre-authored emotion) and wait until it has
        actually finished playing on the call.

        If the TTS provider supports streaming (a `stream()` method), audio is
        forwarded to Twilio chunk-by-chunk as it's generated - the low-latency
        path. Otherwise we synthesize the full clip first, then send."""
        if self._closed:
            return
        async with self._speaking:
            total = 0
            try:
                streamer = getattr(self.tts, "stream", None)
                if streamer is not None:
                    async for chunk in streamer(text, emotion):
                        if self._closed:
                            break
                        total += len(chunk)
                        await self._send_audio(chunk)
                else:
                    audio = await self.tts.synthesize(text, emotion)
                    total = len(audio)
                    await self._send_audio(audio)
            except Exception:  # noqa: BLE001
                global _last_error
                _last_error = traceback.format_exc()
                log.exception("tts failed for: %s", text[:60])
                return
            # Block until Twilio confirms playback finished, so the next line
            # (or hang-up) doesn't overlap or truncate this one.
            await self._await_playback(total / 8000.0)

    async def _send_audio(self, mulaw: bytes) -> None:
        # Stream in 200ms frames into Twilio's buffer. No artificial pacing -
        # playback timing is handled by _await_playback via mark events.
        for i in range(0, len(mulaw), 1600):
            if self._closed:
                return
            chunk = mulaw[i:i + 1600]
            await self.ws.send_text(json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64.b64encode(chunk).decode("ascii")},
            }))

    async def _await_playback(self, duration_s: float) -> None:
        """Send a mark and wait for Twilio to echo it (= audio done playing).
        Falls back to a duration-based timeout if the echo never arrives."""
        if self._closed or self.stream_sid is None:
            return
        self._mark_seq += 1
        name = f"m{self._mark_seq}"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_marks[name] = fut
        await self.ws.send_text(json.dumps({
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {"name": name},
        }))
        try:
            await asyncio.wait_for(fut, timeout=duration_s + 5.0)
        except asyncio.TimeoutError:
            self._pending_marks.pop(name, None)
            log.warning("playback mark %s timed out", name)

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
