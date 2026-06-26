"""Generate the SAME Hindi sentence with every smallest.ai Hindi voice, so
clarity can be A/B compared. Saves mp3 files to a Desktop folder.

Standalone research script - not part of the voice-agent app.
"""
import time
import urllib.request
import urllib.error
import json
import os

API_KEY = "sk_79dd91b7a3bf1b02f649d5aaf5c2201c"
URL = "https://waves-api.smallest.ai/api/v1/lightning/get_speech"
OUT = r"C:\Users\shish\Desktop\smallest-voice-samples"

# Same sentence for every voice (varied sounds, conversational).
SENTENCE = "नमस्ते, मैं आपकी कॉल का जवाब देने के लिए यहाँ हूँ। बताइए, मैं आपकी कैसे मदद कर सकती हूँ?"

# Ordered: conversational picks first (most relevant for a phone agent).
VOICES = [
    "nisha", "kajal", "saina", "sushma", "shweta", "pragya",          # female conversational
    "raman", "arnav", "aarav", "ankur", "raj", "raghav",              # male conversational
    "diya", "ananya", "deepika", "mansi", "saina", "sanya",           # other female
    "chetan", "saurabh", "aravind", "ashish", "mithali", "pooja",     # other
]
# de-dupe preserving order
seen = set(); VOICES = [v for v in VOICES if not (v in seen or seen.add(v))]


def synth(voice: str) -> bytes | None:
    body = json.dumps({
        "text": SENTENCE,
        "voice_id": voice,
        "sample_rate": 24000,
        "language": "hi",
        "output_format": "wav",
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    })
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print(f"   attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    ok, fail = [], []
    for i, v in enumerate(VOICES, 1):
        print(f"[{i:02}/{len(VOICES)}] {v} ...", flush=True)
        audio = synth(v)
        if audio and len(audio) > 1000:
            path = os.path.join(OUT, f"{i:02}-{v}.wav")
            with open(path, "wb") as f:
                f.write(audio)
            print(f"   saved {len(audio)} bytes -> {path}")
            ok.append(v)
        else:
            fail.append(v)
    print("\n=== SUMMARY ===")
    print("saved:", ok)
    print("failed:", fail)
    print("folder:", OUT)


if __name__ == "__main__":
    main()
