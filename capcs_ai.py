"""
capcs_ai.py — All Gemini AI Calls for CAPCS Voice
===================================================
Four functions: bias, question, transcription, closing analysis.
All prompts are designed to be conversational and short — this is a
voice-first app, so responses must be speakable.
"""

import base64
import google.generativeai as genai

_model = None

def _get_model():
    global _model
    if _model is None:
        import streamlit as st
        import os
        api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config={"temperature": 0.8, "max_output_tokens": 8192}
        )
    return _model


def _ask(prompt: str, max_tokens: int = 800) -> str:
    """Core Gemini call with safe fallback."""
    try:
        model = _get_model()
        resp  = model.generate_content(
            prompt,
            generation_config={"temperature": 0.8, "max_output_tokens": max_tokens}
        )
        return resp.text.strip()
    except Exception:
        return ""


# ── PROFILE STRING ─────────────────────────────────────────────────────────────

def build_profile_str(profile: dict) -> str:
    return (
        f"- Current situation: {profile.get('situation', '—')}\n"
        f"- Decision-making style: {profile.get('decision_style', '—')}\n"
        f"- Known blind spot: {profile.get('known_bias', '—')}"
    )


# ── ROUND HISTORY ──────────────────────────────────────────────────────────────

def build_history(rounds: list) -> str:
    if not rounds:
        return "No previous rounds."
    lines = []
    for r in rounds:
        lines.append(f"Round {r['round']}:")
        lines.append(f"  Bias identified: {r.get('bias', '—')}")
        lines.append(f"  Question asked: {r.get('question', '—')}")
        lines.append(f"  User answered: {r.get('transcript', '—')}")
        sig = r.get("signals", {})
        if sig.get("dominant"):
            lines.append(f"  Social signal: {sig['dominant']}")
    return "\n".join(lines)


# ── 1. BIAS DETECTION ──────────────────────────────────────────────────────────

def get_bias(decision: str, profile_str: str, history: str, signal_note: str = "") -> str:
    """
    Identify the single most relevant cognitive bias active right now.
    Returns one sentence: "[Bias name] — because [evidence], you may be [manifestation]."
    """
    signal_block = f"\n{signal_note}\n" if signal_note else ""

    prompt = f"""You are a cognitive scientist. Identify the SINGLE most relevant cognitive bias active right now.
{signal_block}
Write ONE complete sentence, max 35 words:
"[Bias name] — because [specific evidence from profile or answer], you may be [how this manifests in this decision]."

Rules:
- One sentence only. Output nothing else.
- Ground it in the user's actual profile or what they said — not generic.
- Do NOT repeat a bias already used this session (see history).
- Choose the bias most relevant to THIS moment, not the most dramatic one.

USER PROFILE:
{profile_str}

DECISION: {decision}

SESSION HISTORY (avoid repeating these biases):
{history}"""

    return _ask(prompt, 2048)


# ── 2. PERSPECTIVE ─────────────────────────────────────────────────────────────

def get_perspective(decision: str, profile_str: str, bias: str,
                    history: str, signal_note: str = "") -> str:
    """
    Offer one genuinely different reframe or option.
    Returns two lines: OPTION: ... / WHY: ...
    """
    signal_block = f"\n{signal_note}\n" if signal_note else ""

    prompt = f"""You are a Socratic thinking partner. Offer ONE genuinely different perspective.
{signal_block}
Format — exactly two lines:
OPTION: [3-8 word specific named perspective]
WHY: [one sentence connecting to their bias and situation]

Rules:
- Must be meaningfully different from what they are already considering
- Specific and concrete — not "consider all your options"
- Counter the identified bias directly
- Do NOT repeat a perspective already offered (see history)

USER PROFILE:
{profile_str}

DECISION: {decision}
BIAS IDENTIFIED: {bias}

SESSION HISTORY:
{history}"""

    result = _ask(prompt, 1024)

    # Parse the two lines
    option, why = "", ""
    for line in result.split("\n"):
        line = line.strip()
        if line.startswith("OPTION:"):
            option = line.replace("OPTION:", "").strip()
        elif line.startswith("WHY:"):
            why = line.replace("WHY:", "").strip()

    if not option:
        option = result.split(".")[0].strip()

    return option, why


# ── 3. SOCRATIC QUESTION ───────────────────────────────────────────────────────

def get_question(decision: str, profile_str: str, bias: str,
                 perspective: str, history: str, signal_note: str = "") -> str:
    """
    Generate ONE short Socratic question.
    Must be speakable — plain conversational language, max 20 words.
    """
    signal_block = f"\n{signal_note}\n" if signal_note else ""

    prompt = f"""You are a Socratic thinking partner. Ask ONE short question.
{signal_block}
Rules:
- Max 20 words. Shorter is better.
- Plain conversational language — no jargon, no academic terms.
- Cannot be answered yes or no.
- Must engage with something specific from the user's situation or recent answer.
- Must NOT repeat a question already asked (see history).
- Output ONLY the question, nothing else.

Good examples:
- "What would you regret more — trying and failing, or never finding out?"
- "What's actually stopping you from deciding right now?"
- "If your best friend had this choice, what would you tell them?"

USER PROFILE:
{profile_str}

DECISION: {decision}
BIAS: {bias}
PERSPECTIVE OFFERED: {perspective}

SESSION HISTORY (do not repeat these questions):
{history}"""

    return _ask(prompt, 512)


# ── 4. TRANSCRIPTION ───────────────────────────────────────────────────────────

def transcribe_audio(wav_bytes: bytes) -> str:
    """
    Transcribe a WAV audio file using Gemini's native audio understanding.
    Returns the transcript as plain text.
    """
    if not wav_bytes:
        return ""
    try:
        model = _get_model()
        audio_part = {
            "mime_type": "audio/wav",
            "data": base64.b64encode(wav_bytes).decode("utf-8")
        }
        response = model.generate_content([
            "Transcribe this audio response exactly as spoken. "
            "Return only the transcription — no labels, no commentary.",
            audio_part
        ])
        return response.text.strip()
    except Exception:
        return ""


# ── 5. CLOSING ANALYSIS ────────────────────────────────────────────────────────

def get_closing_analysis(decision: str, profile_str: str, rounds: list) -> str:
    """
    Short closing analysis after the user decides they're done.
    3-4 sentences: pattern revealed, which option fits, one next step.
    """
    biases     = [r.get("bias", "") for r in rounds if r.get("bias")]
    answers    = [r.get("transcript", "") for r in rounds if r.get("transcript")]
    signals    = [r.get("signals", {}).get("dominant", "") for r in rounds
                  if r.get("signals", {}).get("dominant")]
    questions  = [r.get("question", "") for r in rounds if r.get("question")]

    prompt = f"""You are analysing the results of a Socratic decision-making session.
Write a warm, honest analysis — 3 to 4 sentences only.

Cover:
1. The pattern you noticed in how they reason (cite the specific biases and signals)
2. What their answers reveal about what they actually want
3. One concrete next step — specific, not vague encouragement

Rules:
- Second person ("you", "your")
- Plain prose — no bullets, no headers
- Every sentence must be grounded in the actual data below — nothing generic
- Final sentence must be complete

USER PROFILE:
{profile_str}

DECISION: {decision}

BIASES DETECTED ACROSS ROUNDS:
{chr(10).join(f"- {b}" for b in biases) if biases else "None recorded"}

QUESTIONS ASKED:
{chr(10).join(f"- {q}" for q in questions) if questions else "None recorded"}

USER'S ANSWERS (transcripts):
{chr(10).join(f"- {a}" for a in answers) if answers else "None recorded"}

SOCIAL SIGNALS DETECTED:
{chr(10).join(f"- {s}" for s in signals) if signals else "None detected"}"""

    return _ask(prompt, 4096)
