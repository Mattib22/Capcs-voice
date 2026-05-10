"""
interhuman.py — Interhuman Social Signal API Client
====================================================
Fill in the 3 marked placeholders once you have your API docs.
Everything else is wired and ready.
"""

import requests
import base64
import os

# ── FILL IN 1: Your Interhuman API base URL ────────────────────────────────────
INTERHUMAN_BASE_URL = "https://api.interhuman.ai/v1"  # ← confirm from docs

# ── FILL IN 2: The social signals endpoint path ────────────────────────────────
INTERHUMAN_ENDPOINT = "/social-signals"  # ← confirm from docs

# Signal threshold — only act on signals above this confidence score
SIGNAL_THRESHOLD = 0.45

# ── SIGNAL → CAPCS PROMPT NOTES ───────────────────────────────────────────────
SIGNAL_NOTES = {
    "hesitation":    "SOCIAL SIGNAL — HESITATION: User is pausing and uncertain. Do NOT introduce new angles. Probe what is blocking commitment. Ask what they are afraid to say out loud.",
    "uncertainty":   "SOCIAL SIGNAL — UNCERTAINTY: User sounds self-doubting. Acknowledge the ambiguity before challenging. Start from what they DO know.",
    "stress":        "SOCIAL SIGNAL — STRESS: User sounds anxious. Significantly reduce challenge intensity. Ask one grounding question that identifies something they are certain about. Do not add complexity.",
    "confidence":    "SOCIAL SIGNAL — CONFIDENCE: User sounds assured. Challenge more directly. Test whether this confidence is warranted or masking overconfidence.",
    "disengagement": "SOCIAL SIGNAL — DISENGAGEMENT: User sounds flat. Reframe the question in terms of what they care about most. Make it personally relevant.",
    "confusion":     "SOCIAL SIGNAL — CONFUSION: User sounds puzzled. Simplify completely. One clear insight, plain language, concrete example.",
    "engagement":    "SOCIAL SIGNAL — ENGAGEMENT: User is present and curious. Go deeper. Values-based or philosophical questions will land well.",
    "interest":      "SOCIAL SIGNAL — INTEREST: User sounds genuinely curious. Push more expansive thinking about what this decision reveals about them.",
    "frustration":   "SOCIAL SIGNAL — FRUSTRATION: User sounds tense. Acknowledge the difficulty explicitly before anything else. Do not add complexity this round.",
    "agreement":     "SOCIAL SIGNAL — AGREEMENT: User is being agreeable. Push for their OWN reasoning. Ask why THEY believe it, not just if they agree.",
    "skepticism":    "SOCIAL SIGNAL — SKEPTICISM: User is pushing back. Meet them with specific reasoning. Explore what they are skeptical about.",
    "disagreement":  "SOCIAL SIGNAL — DISAGREEMENT: User is disagreeing. Explore what they are pushing back on — this often reveals the real tension.",
}

SIGNAL_EMOJI = {
    "hesitation": "⏸️", "uncertainty": "🤔", "stress": "😰",
    "confidence": "💪", "disengagement": "😑", "confusion": "😕",
    "engagement": "🎯", "interest": "👀", "frustration": "😤",
    "agreement": "✅", "skepticism": "🤨", "disagreement": "🙅",
}


def _get_api_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("INTERHUMAN_API_KEY", "")
    except Exception:
        return os.getenv("INTERHUMAN_API_KEY", "")


def analyse_audio(wav_bytes: bytes) -> dict:
    """
    Send a WAV file to Interhuman → return normalised signal data.

    Returns:
        {
            "dominant": "hesitation",
            "scores":   {"hesitation": 0.82, "confidence": 0.11, ...},
            "cqi":      0.67,    # or None if not returned
            "error":    None     # or error string if call failed
        }
    """
    empty = {"dominant": None, "scores": {}, "cqi": None, "error": None}
    api_key = _get_api_key()

    if not api_key:
        empty["error"] = "No INTERHUMAN_API_KEY in secrets — signals disabled."
        return empty
    if not wav_bytes:
        empty["error"] = "No audio provided."
        return empty

    audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # ── FILL IN 3: Adjust payload keys to match your API docs ─────────────────
    payload = {
        "audio":      audio_b64,
        "media_type": "audio/wav",
        "signals":    list(SIGNAL_NOTES.keys()),
        "modalities": ["tone_of_voice", "social_signals"],
    }
    # If your API uses multipart upload instead of JSON, replace the
    # requests.post call below with:
    #   files = {"audio": ("answer.wav", wav_bytes, "audio/wav")}
    #   data  = {"signals": ",".join(SIGNAL_NOTES.keys())}
    #   headers = {"Authorization": f"Bearer {api_key}"}
    #   response = requests.post(url, headers=headers, files=files, data=data, timeout=12)

    try:
        url = f"{INTERHUMAN_BASE_URL}{INTERHUMAN_ENDPOINT}"
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        response.raise_for_status()
        return _parse_response(response.json())
    except requests.exceptions.Timeout:
        empty["error"] = "Interhuman timed out — continuing without signals."
        return empty
    except requests.exceptions.HTTPError as e:
        empty["error"] = f"Interhuman API error {e.response.status_code}."
        return empty
    except Exception as e:
        empty["error"] = f"Interhuman error: {str(e)}"
        return empty


def _parse_response(raw: dict) -> dict:
    """
    Map Interhuman's response JSON to our normalised dict.
    Handles 3 common response shapes — update to match your actual docs.
    """
    scores = {}

    # Pattern A: flat  { "hesitation": 0.8, "confidence": 0.3 }
    if any(k in raw for k in SIGNAL_NOTES):
        scores = {k: float(v) for k, v in raw.items()
                  if k in SIGNAL_NOTES and isinstance(v, (int, float))}

    # Pattern B: nested  { "results": { "hesitation": 0.8 } }
    elif "results" in raw and isinstance(raw["results"], dict):
        scores = {k: float(v) for k, v in raw["results"].items()
                  if k in SIGNAL_NOTES and isinstance(v, (int, float))}

    # Pattern C: list  { "signals": [{"name": "hesitation", "score": 0.8}] }
    elif "signals" in raw and isinstance(raw["signals"], list):
        for s in raw["signals"]:
            name  = s.get("name") or s.get("label", "")
            score = s.get("score") or s.get("confidence") or s.get("value", 0)
            if name in SIGNAL_NOTES:
                scores[name] = float(score)

    above    = {k: v for k, v in scores.items() if v >= SIGNAL_THRESHOLD}
    dominant = max(above, key=above.get) if above else None
    cqi      = raw.get("cqi") or raw.get("conversation_quality_index")

    return {
        "dominant": dominant,
        "scores":   scores,
        "cqi":      float(cqi) if cqi is not None else None,
        "error":    None,
    }


def get_signal_note(signal_data: dict) -> str:
    """Return the prompt injection note for the dominant signal."""
    dominant = signal_data.get("dominant")
    return SIGNAL_NOTES.get(dominant, "") if dominant else ""


def format_signal_display(signal_data: dict) -> str:
    """Short human-readable indicator for the UI."""
    if signal_data.get("error") or not signal_data.get("dominant"):
        return ""
    dominant = signal_data["dominant"]
    score    = signal_data.get("scores", {}).get(dominant, 0)
    emoji    = SIGNAL_EMOJI.get(dominant, "📊")
    cqi      = signal_data.get("cqi")
    cqi_str  = f"  ·  CQI {cqi:.0%}" if cqi is not None else ""
    return f"{emoji} **{dominant.capitalize()}** detected ({score:.0%}){cqi_str}"
