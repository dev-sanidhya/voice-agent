"""Offline smoke test: exercises every layer except a live phone call.

- ScriptFlow: deterministic conversation logic.
- edge-tts -> ffmpeg: text becomes mu-law/8k audio.
- Deepgram: live websocket connect + auth check (no audio billed).
- Twilio: credential check + TwiML generation.
"""
import asyncio

from app.config import settings
from app.flow.script_flow import ScriptFlow
from app.tts.edge_tts import EdgeTTS


async def test_flow():
    print("\n[1] Deterministic flow (no AI)")
    flow = ScriptFlow()
    print("   agent:", flow.greeting())
    for caller in ["yes", "what's the pricing", "business hours", "no thanks"]:
        res = flow.handle(caller)
        print(f"   caller: {caller!r} -> agent: {res.reply!r} end={res.end_call}")


async def test_tts():
    print("\n[2] TTS (edge-tts) -> mu-law/8k via ffmpeg")
    tts = EdgeTTS(settings.tts_voice)
    audio = await tts.synthesize("Hello, this is a test of the voice agent.")
    print(f"   produced {len(audio)} bytes of mu-law ({len(audio)/8000:.1f}s)")
    assert len(audio) > 8000, "TTS output too short"


async def test_deepgram():
    print("\n[3] Deepgram live websocket connect")
    import websockets
    from app.stt.deepgram_stt import _URL
    try:
        ws = await websockets.connect(
            _URL, additional_headers={"Authorization": f"Token {settings.deepgram_api_key}"}
        )
        await ws.close()
        print("   connected + authenticated OK")
    except Exception as e:
        print(f"   FAILED: {e}")
        raise


def test_twilio():
    print("\n[4] Twilio credentials + TwiML")
    from app.telephony.twilio_client import TwilioTelephony
    client = TwilioTelephony(settings.twilio_account_sid, settings.twilio_auth_token,
                             settings.twilio_phone_number)
    acct = client._client.api.accounts(settings.twilio_account_sid).fetch()
    print(f"   account status: {acct.status}")
    twiml = TwilioTelephony.stream_twiml("wss://example.ngrok-free.app/stream")
    print("   TwiML:", twiml)
    assert "<Stream" in twiml


async def main():
    await test_flow()
    await test_tts()
    await test_deepgram()
    test_twilio()
    print("\nALL SMOKE TESTS PASSED\n")


if __name__ == "__main__":
    asyncio.run(main())
