"""Provider factory - resolves the configured implementation for each layer.

Set STT_PROVIDER / TTS_PROVIDER / TELEPHONY_PROVIDER to "mock" to run the
entire pipeline with no cloud accounts.
"""
from .config import settings


def make_stt():
    if settings.stt_provider == "mock":
        from .stt.mock_stt import MockSTT
        return MockSTT()
    from .stt.deepgram_stt import DeepgramSTT
    return DeepgramSTT(settings.deepgram_api_key, settings.stt_language)


def make_tts():
    if settings.tts_provider == "mock":
        from .tts.mock_tts import MockTTS
        return MockTTS()
    if settings.tts_provider == "deepgram":
        from .tts.deepgram_tts import DeepgramTTS
        return DeepgramTTS(settings.deepgram_api_key, settings.tts_voice_deepgram)
    if settings.tts_provider == "siliconflow":
        from .tts.siliconflow_tts import SiliconFlowTTS
        return SiliconFlowTTS(settings.siliconflow_api_key, settings.tts_voice_siliconflow)
    if settings.tts_provider == "openai":
        from .tts.openai_tts import OpenAITTS
        return OpenAITTS(settings.openai_api_key, settings.tts_voice_openai)
    if settings.tts_provider == "smallest":
        from .tts.smallest_tts import SmallestTTS
        return SmallestTTS(settings.smallest_api_key, settings.tts_voice_smallest,
                           settings.tts_language_smallest)
    from .tts.edge_tts import EdgeTTS
    return EdgeTTS(settings.tts_voice)


def make_telephony():
    if settings.telephony_provider == "mock":
        return None  # outbound dialing is a no-op without a real carrier
    from .telephony.twilio_client import TwilioTelephony
    return TwilioTelephony(
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_phone_number,
    )
