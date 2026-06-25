"""Twilio telephony.

Two responsibilities:
1. Place outbound calls (REST API).
2. Produce the TwiML that tells Twilio to open a bidirectional Media Stream
   to our websocket, so call audio flows both ways.

Inbound calls hit the same /voice webhook and reuse the same TwiML.
"""
import logging

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect

log = logging.getLogger("telephony.twilio")


class TwilioTelephony:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._client = Client(account_sid, auth_token)
        self.from_number = from_number

    def place_call(self, to_number: str, answer_url: str) -> str:
        """Start an outbound call. Twilio fetches `answer_url` for TwiML when
        the callee picks up. Returns the call SID."""
        call = self._client.calls.create(
            to=to_number,
            from_=self.from_number,
            url=answer_url,
        )
        log.info("placed outbound call %s -> %s (%s)", self.from_number, to_number, call.sid)
        return call.sid

    @staticmethod
    def stream_twiml(ws_url: str, direction: str = "outbound") -> str:
        """TwiML: open a bidirectional media stream to our websocket.

        The call direction is passed as a Stream <Parameter> so the websocket
        handler can tailor the greeting (inbound vs outbound).
        """
        response = VoiceResponse()
        connect = Connect()
        stream = connect.stream(url=ws_url)
        stream.parameter(name="direction", value=direction)
        response.append(connect)
        return str(response)
