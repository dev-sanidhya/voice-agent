"""Emotion showcase - NOT the business script, a comparison demo.

Speaks the *same* sentence multiple times, each with a different
pre-authored emotion tag, back-to-back with no caller input needed. This
isolates emotion as the only variable so two TTS providers (or two emotion
settings) can be A/B compared cleanly on one call.
"""
from dataclasses import dataclass

# A single fixed sentence with enough emotional latitude to be delivered
# convincingly in any mood - so emotion is the only thing that changes.
_SENTENCE = "I just got your message about the order, and I really wanted to reach out to you about it."

# Each emotion is announced by name (spoken in that emotion), then the same
# sentence follows - making the contrast between providers obvious.
LINES = [
    ("Let's compare emotions. I'll say the same line five times, each with a different feeling.", "friendly"),
    (f"Neutral. {_SENTENCE}", "neutral"),
    (f"Friendly. {_SENTENCE}", "friendly"),
    (f"Cheerful! {_SENTENCE}", "cheerful"),
    (f"Empathetic. {_SENTENCE}", "empathetic"),
    (f"Apologetic. {_SENTENCE}", "apologetic"),
    ("That's the showcase. Goodbye!", "cheerful"),
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
