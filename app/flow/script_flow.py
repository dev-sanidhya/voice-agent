"""Deterministic conversation flow - NO AI / NO LLM.

The "agent" is a small finite state machine. It looks at the transcript
returned by STT and chooses the next line to speak via plain keyword
matching. This is the part the task requires to be free of AI: the brain
is a lookup table, not a model.

Swap/extend the STATES table to change the script.
"""
from dataclasses import dataclass, field


@dataclass
class FlowResult:
    reply: str          # text to send to TTS
    end_call: bool = False


# Simple keyword buckets used for branching. Lowercased substring match.
_AFFIRM = ("yes", "yeah", "yep", "sure", "okay", "ok", "correct", "haan", " haa")
_DENY = ("no", "nope", "not", "don't", "stop", "nahi")
_BYE = ("bye", "goodbye", "that's all", "nothing", "no thanks", "we're done")


def _contains(text: str, words) -> bool:
    t = f" {text.lower()} "
    return any(w in t for w in words)


@dataclass
class ScriptFlow:
    """One instance per call. Tracks which step of the script we're on."""
    step: str = "greeting"
    turns: int = field(default=0)

    def greeting(self) -> str:
        """First thing the agent says when the call connects."""
        self.step = "await_help"
        return (
            "Hello! Thanks for taking the call. This is an automated voice "
            "assistant. Can you hear me clearly? Please say yes or no."
        )

    def handle(self, transcript: str) -> FlowResult:
        """Given what the caller said, decide the next line. Pure rules."""
        self.turns += 1
        text = (transcript or "").strip()

        # Global hang-up intent works from any step.
        if _contains(text, _BYE):
            self.step = "done"
            return FlowResult("No problem. Thank you for your time. Goodbye!", end_call=True)

        if self.step == "await_help":
            if _contains(text, _AFFIRM):
                self.step = "menu"
                return FlowResult(
                    "Great, the audio is working. "
                    "You can ask about pricing, support, or business hours. "
                    "Which one would you like?"
                )
            if _contains(text, _DENY):
                return FlowResult(
                    "Sorry about that. Let me try again - can you hear me now? "
                    "Please say yes or no."
                )
            return FlowResult("I didn't quite catch that. Please say yes or no - can you hear me?")

        if self.step == "menu":
            if "pricing" in text.lower() or "price" in text.lower() or "cost" in text.lower():
                return FlowResult(
                    "Our plans start at nineteen dollars per month. "
                    "Anything else - support or business hours?"
                )
            if "support" in text.lower() or "help" in text.lower():
                return FlowResult(
                    "Support is available twenty four seven by email and chat. "
                    "Anything else - pricing or business hours?"
                )
            if "hour" in text.lower() or "time" in text.lower() or "open" in text.lower():
                return FlowResult(
                    "We are open Monday to Friday, nine to six. "
                    "Anything else - pricing or support?"
                )
            return FlowResult(
                "I can tell you about pricing, support, or business hours. "
                "Which one?"
            )

        # Fallback
        return FlowResult("I'm not sure I understood. Could you repeat that?")
