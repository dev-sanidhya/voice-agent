"""Dev launcher: opens an ngrok tunnel, writes the public host into the running
config, prints the URLs to paste into Twilio, then serves the app.

    python run.py            # start server + tunnel
    python run.py --no-tunnel  # server only (e.g. when deployed with a real host)
"""
import sys
import logging

import uvicorn

from app.config import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("run")


def start_tunnel() -> str:
    from pyngrok import ngrok, conf
    if settings.ngrok_authtoken:
        conf.get_default().auth_token = settings.ngrok_authtoken
    tunnel = ngrok.connect(settings.port, "http")
    host = tunnel.public_url.replace("https://", "").replace("http://", "")
    log.info("ngrok tunnel: https://%s -> localhost:%d", host, settings.port)
    return host


def main() -> None:
    if "--no-tunnel" not in sys.argv and not settings.public_host:
        settings.public_host = start_tunnel()

    host = settings.public_host or f"localhost:{settings.port}"
    print("\n" + "=" * 64)
    print("  Voice agent ready")
    print(f"  Providers: stt={settings.stt_provider} tts={settings.tts_provider} "
          f"telephony={settings.telephony_provider}")
    print(f"  Inbound webhook (set on your Twilio number):")
    print(f"      https://{host}/voice   (HTTP POST)")
    print(f"  Place an outbound call:")
    print(f"      curl -X POST https://{host}/outbound")
    print("=" * 64 + "\n")

    uvicorn.run(app="app.main:app", host="0.0.0.0", port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
