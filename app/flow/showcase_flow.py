"""Emotion showcase - NOT the business script, a comparison demo.

Speaks the *same* sentence multiple times, each with a different
pre-authored emotion tag, back-to-back with no caller input needed. This
isolates emotion as the only variable so two TTS providers (or two emotion
settings) can be A/B compared cleanly on one call.
"""
from dataclasses import dataclass

# A single fixed sentence with enough emotional latitude to be delivered
# convincingly in any mood - so emotion is the only thing that changes.
# Written in natural Delhi/NCR Hinglish (Hindi grammar + everyday English
# loanwords in Devanagari - "message", "order" etc as commonly spoken there),
# not literary/Sanskritized Hindi.
_SENTENCE = "मुझे आपका मैसेज मिल गया था ऑर्डर के बारे में, और मैं सच में इस बारे में आपसे बात करना चाहती थी।"

# Each emotion is announced by name (spoken in that emotion), then the same
# sentence follows - making the contrast between providers obvious.
LINES = [
    ("चलिए इमोशन्स कंपेयर करते हैं। मैं एक ही लाइन को पांच बार बोलूंगी, हर बार एक अलग फीलिंग के साथ।", "friendly"),
    (f"न्यूट्रल। {_SENTENCE}", "neutral"),
    (f"फ्रेंडली। {_SENTENCE}", "friendly"),
    (f"चीयरफुल! {_SENTENCE}", "cheerful"),
    (f"एम्पैथेटिक। {_SENTENCE}", "empathetic"),
    (f"सॉरी वाले अंदाज़ में। {_SENTENCE}", "apologetic"),
    ("ये रहा हमारा शोकेस। अलविदा!", "cheerful"),
]


@dataclass
class ShowcaseFlow:
    """Plays through LINES once, then signals end_call. No branching."""
    index: int = 0

    def next_line(self):
        """Returns (text, emotion, is_last) or None if exhausted."""
        if self.index >= len(LINES):
            return None
        text, emotion = LINES[self.index]
        self.index += 1
        is_last = self.index >= len(LINES)
        return text, emotion, is_last
