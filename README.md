# Voice Agent (STT + TTS + Telephony)

A standalone voice-agent that places **outbound** and answers **inbound** phone
calls. It transcribes the caller in real time, decides what to say with a
**deterministic script (no AI/LLM)**, and speaks back over the call.

Three API layers, each swappable:

| Layer | Default provider | Free? |
|---|---|---|
| Telephony (numbers + media) | **Twilio** (free trial credit, no card) | yes |
| Speech-to-Text | **Deepgram** ($200 credit, no card) | yes |
| Text-to-Speech | **edge-tts** (no key, no account) | yes |

Every layer can be set to `mock` to run the whole pipeline with **zero
accounts** (see `.env`).

## Architecture

```
 Phone call <--Twilio Media Stream (WS)--> /stream
                                              |
        caller mu-law/8k audio  ----------->  STT  (Deepgram, streaming)
                                              |
                          final transcript -> ScriptFlow  (rules, NO AI)
                                              |
                              reply text   -> TTS (edge-tts) -> mu-law/8k
                                              |
                                              -> streamed back to the call
```

- `app/main.py` - FastAPI server, `/outbound`, `/voice` (TwiML), `/stream` (WS).
- `app/flow/script_flow.py` - the deterministic state machine (the "brain").
- `app/stt/`, `app/tts/`, `app/telephony/` - provider implementations + mocks.
- `app/audio/codec.py` - mu-law / MP3 conversion (ffmpeg).
- `run.py` - launches ngrok + the server and prints the URLs.

## Setup

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env        # then fill in the keys
```

Fill `.env` with the Twilio, Deepgram, and ngrok values. Requires **ffmpeg**
on PATH (already installed on this machine).

## Run

```bash
python run.py
```

This opens an ngrok tunnel and prints:
- the **inbound webhook** URL -> set it on your Twilio number's *A Call Comes In*
  (Voice Configuration) as an HTTP POST.
- the **outbound** curl command.

### Make an outbound call
```bash
curl -X POST https://<your-ngrok-host>/outbound
```
Twilio rings `MY_VERIFIED_NUMBER`; on answer, the agent greets you and follows
the script.

### Receive an inbound call
Set the number's inbound webhook to `https://<host>/voice` and call your Twilio
number from your verified phone.

## Run with no accounts (mock everything)
In `.env`:
```
STT_PROVIDER=mock
TTS_PROVIDER=mock
TELEPHONY_PROVIDER=mock
```
Then `python run.py --no-tunnel` and exercise the flow logic locally.

## The "no AI" guarantee
The decision logic lives entirely in `app/flow/script_flow.py` as keyword rules
over a finite state machine. No LLM is called anywhere in the request path.
STT and TTS are API services (the required components), not decision-makers.
