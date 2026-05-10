"""
CAPCS × Interhuman — Voice Socratic Agent
==========================================
Run: streamlit run app.py

Secrets (.streamlit/secrets.toml):
    GEMINI_API_KEY      = "AIza..."
    INTERHUMAN_API_KEY  = "ih_..."
"""

import streamlit as st
import json
from capcs_ai  import build_profile_str, build_history, get_bias, get_perspective, get_question, transcribe_audio, get_closing_analysis
from interhuman import analyse_audio, get_signal_note, format_signal_display

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CAPCS — Think out loud",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── STYLES ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=DM+Mono:wght@300;400&display=swap');

html, body, [data-testid="stAppViewContainer"] { background: #F7F4EE; }
[data-testid="stAppViewContainer"] { font-family: 'DM Mono', monospace; }

/* Hide Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
[data-testid="stSidebar"] { background: #F0EDE5; }

/* Global text */
h1, h2, h3 { font-family: 'Lora', serif !important; color: #1A1714; }
p, li, label { color: #1A1714; }

/* Phase label */
.phase-label {
    font-size: 10px; letter-spacing: 3px; text-transform: uppercase;
    color: #9A7B3A; font-weight: 400; margin-bottom: 6px;
    font-family: 'DM Mono', monospace;
}

/* Cards */
.card {
    background: white; border-radius: 8px; padding: 24px 28px;
    border: 1px solid rgba(26,23,20,0.10); margin-bottom: 16px;
}
.card-bias   { border-left: 3px solid #C0392B; background: #FDF6F5; }
.card-persp  { border-left: 3px solid #2E7D52; background: #F2F9F5; }
.card-question { border-left: 3px solid #5B3A8A; background: #F6F2FC;
                 font-family: 'Lora', serif; font-style: italic;
                 font-size: 20px; line-height: 1.5; color: #1A1714; }
.card-signal { border-left: 3px solid #C8A96E; background: #FDF8EE; font-size: 13px; }
.card-info   { border-left: 3px solid #4A6FA5; background: #EEF2FF; font-size: 13px; }
.card-analysis { border-left: 3px solid #1A1714; background: white;
                  font-family: 'Lora', serif; font-size: 16px; line-height: 1.8; }

/* Transcript display */
.transcript {
    background: #F0EDE5; border-radius: 6px; padding: 12px 16px;
    font-size: 14px; line-height: 1.7; color: #3D3830;
    font-style: italic; margin-top: 8px;
}

/* Round history item */
.history-item {
    padding: 12px 0; border-bottom: 1px solid rgba(26,23,20,0.08);
}
.history-q { font-size: 12px; color: #7A7268; font-style: italic; margin-bottom: 4px; }
.history-a { font-size: 13px; color: #1A1714; }
.history-sig { font-size: 10px; color: #9A7B3A; letter-spacing: 1px;
               text-transform: uppercase; margin-top: 4px; }

/* Buttons */
.stButton > button {
    font-family: 'DM Mono', monospace !important;
    font-size: 12px !important; letter-spacing: 1.5px !important;
    text-transform: uppercase !important; border-radius: 4px !important;
}
.stButton > button[kind="primary"] {
    background: #1A1714 !important; color: #F7F4EE !important;
    border: none !important;
}
.stButton > button[kind="secondary"] {
    background: transparent !important; color: #7A7268 !important;
    border: 1px solid rgba(26,23,20,0.20) !important;
}

/* Radio + select */
[data-testid="stRadio"] label, [data-testid="stSelectbox"] label {
    font-family: 'DM Mono', monospace; font-size: 13px;
}

/* Audio input */
[data-testid="stAudioInput"] { border-radius: 8px; }

/* Divider */
hr { border-color: rgba(26,23,20,0.10) !important; }
</style>
""", unsafe_allow_html=True)


# ── SESSION STATE DEFAULTS ─────────────────────────────────────────────────────
defaults = {
    "phase":    "onboarding",   # onboarding | input | conversation | done
    "profile":  {},
    "decision": "",
    "rounds":   [],
    "mute":     False,
    "generating": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── HELPERS ────────────────────────────────────────────────────────────────────

def label(text):
    st.markdown(f'<div class="phase-label">{text}</div>', unsafe_allow_html=True)

def card(content, style=""):
    cls = f"card card-{style}" if style else "card"
    st.markdown(f'<div class="{cls}">{content}</div>', unsafe_allow_html=True)

def speak(text: str):
    """Browser TTS — speaks the question aloud."""
    if st.session_state.get("mute"):
        return
    safe = json.dumps(text)
    st.components.v1.html(f"""
    <script>
      window.addEventListener('load', function() {{
        const u = new SpeechSynthesisUtterance({safe});
        u.rate  = 0.92;
        u.pitch = 1.0;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
      }});
    </script>
    """, height=0)

def reset():
    for k, v in defaults.items():
        st.session_state[k] = v if not callable(v) else v()
    st.session_state["phase"] = "onboarding"


# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚡ CAPCS")
    st.caption("A thinking partner, not an answer engine.")
    st.divider()
    st.session_state.mute = st.checkbox("🔇 Mute voice", value=st.session_state.mute)
    st.divider()
    if st.button("↺  Start over", use_container_width=True):
        reset()
        st.rerun()
    st.divider()
    st.caption("v1.0 · Interhuman May Build Challenge")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 0 — ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.phase == "onboarding":
    st.markdown("## ⚡ CAPCS")
    st.markdown("*A Socratic thinking partner. Tell it about yourself — it takes 60 seconds.*")
    st.divider()

    card(
        "CAPCS will challenge your thinking by detecting cognitive biases, "
        "offering perspectives you haven't considered, and asking questions "
        "that reveal what you actually want — not what you think you should want.<br><br>"
        "With Interhuman, it also listens to <b>how</b> you answer, not just what you say.",
        style="info"
    )

    st.markdown("")
    label("About you — 3 quick questions")

    situation = st.text_area(
        "1. What's your current situation in one sentence?",
        placeholder="e.g. I'm 3 months into a new job and considering a startup offer...",
        height=80,
        key="ob_situation"
    )

    decision_style = st.radio(
        "2. How do you usually make important decisions?",
        options=[
            "I trust my gut and decide quickly",
            "I research extensively before committing",
            "I consult others and value their input",
            "I tend to avoid deciding until I have to",
        ],
        key="ob_style",
        index=None
    )

    known_bias = st.radio(
        "3. What's your biggest known blind spot?",
        options=[
            "I overthink and miss opportunities",
            "I act too impulsively and regret it",
            "I always play it safe even when I shouldn't",
            "I need others to agree before I commit",
        ],
        key="ob_bias",
        index=None
    )

    st.markdown("")
    if st.button("→ Start", type="primary", use_container_width=True):
        if not situation.strip():
            st.error("Please describe your current situation.")
        elif decision_style is None:
            st.error("Please select your decision-making style.")
        elif known_bias is None:
            st.error("Please select your known blind spot.")
        else:
            st.session_state.profile = {
                "situation":      situation.strip(),
                "decision_style": decision_style,
                "known_bias":     known_bias,
            }
            st.session_state.phase = "input"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — DECISION INPUT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == "input":
    st.markdown("## What decision are you working through?")
    st.caption("Be as specific as possible — context is everything.")
    st.divider()

    decision = st.text_area(
        "Describe your decision",
        placeholder="e.g. I've been offered a role at an early-stage startup that pays 20% less than my current job but gives me equity and more responsibility. I'm not sure whether to take it.",
        height=140,
        key="input_decision"
    )

    st.markdown("")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("→ Challenge my thinking", type="primary", use_container_width=True):
            if not decision.strip():
                st.error("Please describe your decision.")
            else:
                st.session_state.decision = decision.strip()
                st.session_state.rounds   = []
                st.session_state.phase    = "generating_round"
                st.rerun()
    with col2:
        if st.button("← Back", use_container_width=True):
            st.session_state.phase = "onboarding"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# GENERATING ROUND — loading screen between rounds
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == "generating_round":
    st.markdown("## ⚡ CAPCS")
    st.divider()

    with st.spinner("Thinking through your decision..."):
        profile_str = build_profile_str(st.session_state.profile)
        history     = build_history(st.session_state.rounds)
        decision    = st.session_state.decision

        # Get signal note from last round if available
        signal_note = ""
        if st.session_state.rounds:
            last_signals = st.session_state.rounds[-1].get("signals", {})
            signal_note  = get_signal_note(last_signals)

        bias            = get_bias(decision, profile_str, history, signal_note)
        option, why     = get_perspective(decision, profile_str, bias, history, signal_note)
        question        = get_question(decision, profile_str, bias, option, history, signal_note)

    # Store the generated round content and move to conversation
    st.session_state["_pending_round"] = {
        "bias":        bias,
        "perspective": option,
        "why":         why,
        "question":    question,
    }
    st.session_state.phase = "conversation"
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — CONVERSATION
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == "conversation":
    round_num = len(st.session_state.rounds) + 1
    pending   = st.session_state.get("_pending_round", {})

    # Header
    col_title, col_done = st.columns([3, 1])
    with col_title:
        st.markdown(f"## Round {round_num}")
    with col_done:
        if st.button("✓ I've decided", type="secondary", use_container_width=True):
            st.session_state.phase = "generating_analysis"
            st.rerun()

    st.caption(f"*{st.session_state.decision[:120]}{'...' if len(st.session_state.decision) > 120 else ''}*")
    st.divider()

    # ── Bias ──────────────────────────────────────────────────────────────────
    label("⚠️ Bias detected")
    card(pending.get("bias", "—"), style="bias")

    # ── Perspective ───────────────────────────────────────────────────────────
    label("💡 A different angle")
    option = pending.get("perspective", "")
    why    = pending.get("why", "")
    persp_html = f"<strong>{option}</strong><br><small style='color:#4a6a5a'>{why}</small>" if why else f"<strong>{option}</strong>"
    card(persp_html, style="persp")

    # ── Question ──────────────────────────────────────────────────────────────
    label("❓ Socratic challenge")
    question = pending.get("question", "")
    card(question, style="question")

    # Speak the question
    speak(question)

    st.divider()

    # ── Voice / text answer ───────────────────────────────────────────────────
    label("Your answer")
    use_voice = st.toggle("🎙️ Answer by voice", value=True, key=f"voice_toggle_{round_num}")

    transcript = ""
    signals    = {"dominant": None, "scores": {}, "cqi": None, "error": None}

    if use_voice:
        audio = st.audio_input(
            "Record your answer — speak naturally",
            key=f"audio_{round_num}"
        )

        if audio:
            wav_bytes = audio.getvalue()

            with st.spinner("Transcribing..."):
                transcript = transcribe_audio(wav_bytes)

            with st.spinner("Reading your social signals..."):
                signals = analyse_audio(wav_bytes)

            # Show transcript
            if transcript:
                st.markdown(f'<div class="transcript">"{transcript}"</div>', unsafe_allow_html=True)

            # Show signal indicator
            sig_display = format_signal_display(signals)
            if sig_display:
                st.markdown("")
                card(sig_display, style="signal")
            elif signals.get("error"):
                st.caption(f"ℹ️ {signals['error']}")

    else:
        transcript = st.text_area(
            "Type your answer",
            placeholder="Your answer...",
            height=120,
            key=f"text_answer_{round_num}"
        )

    st.markdown("")

    # ── Submit ─────────────────────────────────────────────────────────────────
    col_submit, col_end = st.columns([2, 1])
    with col_submit:
        if st.button("→ Next challenge", type="primary", use_container_width=True):
            if not transcript.strip():
                st.warning("Please record or type your answer first.")
            else:
                # Save completed round
                completed_round = {
                    "round":       round_num,
                    "bias":        pending.get("bias", ""),
                    "perspective": pending.get("perspective", ""),
                    "question":    pending.get("question", ""),
                    "transcript":  transcript,
                    "signals":     signals,
                }
                st.session_state.rounds.append(completed_round)
                st.session_state.pop("_pending_round", None)
                st.session_state.phase = "generating_round"
                st.rerun()

    with col_end:
        if st.button("✓ Done deciding", type="secondary", use_container_width=True):
            # Save current round if answered, then go to analysis
            if transcript.strip():
                completed_round = {
                    "round":       round_num,
                    "bias":        pending.get("bias", ""),
                    "perspective": pending.get("perspective", ""),
                    "question":    pending.get("question", ""),
                    "transcript":  transcript,
                    "signals":     signals,
                }
                st.session_state.rounds.append(completed_round)
            st.session_state.pop("_pending_round", None)
            st.session_state.phase = "generating_analysis"
            st.rerun()

    # ── Round history ──────────────────────────────────────────────────────────
    if st.session_state.rounds:
        st.divider()
        with st.expander(f"Session so far — {len(st.session_state.rounds)} round(s)"):
            for r in reversed(st.session_state.rounds):
                sig = r.get("signals", {})
                sig_str = f"Signal: {sig['dominant']}" if sig.get("dominant") else ""
                st.markdown(
                    f'<div class="history-item">'
                    f'<div class="history-q">Round {r["round"]} · {r.get("bias","").split("—")[0].strip()}</div>'
                    f'<div class="history-q" style="font-style:normal">Q: {r.get("question","")}</div>'
                    f'<div class="history-a">"{r.get("transcript","")}"</div>'
                    f'<div class="history-sig">{sig_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )


# ══════════════════════════════════════════════════════════════════════════════
# GENERATING ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == "generating_analysis":
    st.markdown("## ⚡ CAPCS")
    st.divider()
    with st.spinner("Synthesising your session..."):
        profile_str = build_profile_str(st.session_state.profile)
        analysis    = get_closing_analysis(
            st.session_state.decision,
            profile_str,
            st.session_state.rounds
        )
        st.session_state["_analysis"] = analysis
    st.session_state.phase = "done"
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — DONE / CLOSING REPORT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.phase == "done":
    st.markdown("## Session complete.")
    st.divider()

    analysis = st.session_state.get("_analysis", "")
    if analysis:
        label("What your thinking reveals")
        card(analysis, style="analysis")
        speak(analysis)

    # ── Signal summary ─────────────────────────────────────────────────────────
    rounds = st.session_state.rounds
    if rounds:
        st.divider()
        label(f"Session summary — {len(rounds)} round(s)")

        # Signal breakdown
        all_signals = [r.get("signals", {}).get("dominant") for r in rounds
                       if r.get("signals", {}).get("dominant")]
        if all_signals:
            from collections import Counter
            from interhuman import SIGNAL_EMOJI
            sig_counts = Counter(all_signals)
            sig_parts  = [f"{SIGNAL_EMOJI.get(s,'📊')} {s} ×{c}"
                          for s, c in sig_counts.most_common()]
            card("**Signals detected across rounds:** " + " · ".join(sig_parts), style="signal")

        # CQI average
        cqis = [r.get("signals", {}).get("cqi") for r in rounds
                if r.get("signals", {}) and r["signals"].get("cqi") is not None]
        if cqis:
            avg_cqi = sum(cqis) / len(cqis)
            card(f"**Average Conversation Quality Index (CQI):** {avg_cqi:.0%}", style="signal")

        # Round breakdown
        with st.expander("Full session breakdown"):
            for r in rounds:
                sig = r.get("signals", {})
                from interhuman import SIGNAL_EMOJI
                sig_str = f"{SIGNAL_EMOJI.get(sig.get('dominant',''), '📊')} {sig.get('dominant','')}" if sig.get("dominant") else "No signal"
                st.markdown(f"**Round {r['round']}** · {sig_str}")
                st.caption(f"Bias: {r.get('bias','—')}")
                st.caption(f"Q: {r.get('question','—')}")
                st.markdown(f"> {r.get('transcript','—')}")
                st.markdown("---")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("→ New decision", type="primary", use_container_width=True):
            st.session_state.rounds   = []
            st.session_state.decision = ""
            st.session_state.pop("_analysis", None)
            st.session_state.pop("_pending_round", None)
            st.session_state.phase = "input"
            st.rerun()
    with col2:
        if st.button("↺ Start over", use_container_width=True):
            reset()
            st.rerun()
