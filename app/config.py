"""Central configuration, loaded from environment / .env.

Every provider is selected by a string ("twilio"/"deepgram"/"edge" or "mock")
so the whole pipeline can run with zero cloud accounts during development.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telephony (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    my_verified_number: str = ""

    # STT (Deepgram)
    deepgram_api_key: str = ""

    # TTS (SiliconFlow)
    siliconflow_api_key: str = ""

    # TTS (OpenAI)
    openai_api_key: str = ""

    # Tunnel
    ngrok_authtoken: str = ""

    # Provider selection
    stt_provider: str = "deepgram"
    tts_provider: str = "edge"
    telephony_provider: str = "twilio"

    # TTS
    tts_voice: str = "en-US-AriaNeural"          # edge-tts voice
    tts_voice_deepgram: str = "aura-asteria-en"  # Deepgram Aura model
    tts_voice_siliconflow: str = "FunAudioLLM/CosyVoice2-0.5B:anna"
    tts_voice_openai: str = "alloy"

    # Server
    public_host: str = ""   # e.g. "abc123.ngrok-free.app" (no scheme); auto-filled if blank
    port: int = 5050


settings = Settings()
