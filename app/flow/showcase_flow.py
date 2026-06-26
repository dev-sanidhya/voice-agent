"""Emotion showcase - NOT the business script, a comparison demo.

Speaks the *same* sentence multiple times, each with a different
pre-authored emotion tag, back-to-back with no caller input needed. This
isolates emotion as the only variable so two TTS providers (or two emotion
settings) can be A/B compared cleanly on one call.
"""
from dataclasses import dataclass

# (text, emotion) - identical text across emotions to isolate the variable.
LINES = [
    ("Here is the same sentence, spoken in a neutral tone.", "neutral"),
    ("Here is the same sentence, spoken in a friendly tone.", "friendly"),
    ("Here is the same sentence, spoken in a cheerful tone!", "cheerful"),
    ("Here is the same sentence, spoken in an empathetic tone.", "empathetic"),
    ("Here is the same sentence, spoken in an apologetic tone.", "apologetic"),
    ("That concludes the emotion showcase. Goodbye!", "cheerful"),
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
