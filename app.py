"""AI Fitness Coach - Streamlit prototype.  Run:  streamlit run app.py

Flow: choose exercise -> full-screen live camera with coaching overlay -> summary + AI coach.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from streamlit_webrtc import webrtc_streamer

from coach.gemini_coach import get_feedback
from exercises.configs import EXERCISES
from ui.processor import CoachProcessor

st.set_page_config(page_title="AI Fitness Coach", page_icon="\U0001F3CB", layout="wide")

RTC_CONFIG = {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
ss = st.session_state
ss.setdefault("stage", "select")
ss.setdefault("paused", False)
ss.setdefault("summary", None)


def api_key() -> str | None:
    try:
        return st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    except Exception:
        return os.getenv("GEMINI_API_KEY")


FULLSCREEN_CSS = """
<style>
header[data-testid="stHeader"], footer {display:none;}
.block-container {padding: 0.6rem 1rem 0 1rem; max-width: 100%;}
[data-testid="stSidebar"] {display:none;}
</style>
"""


# ------------------------------------------------------------------ select page
def page_select() -> None:
    st.title("\U0001F3CB AI Fitness Coach")
    st.caption("Live posture tracking, rep counting and form feedback from your camera.")

    key = st.radio("Choose your exercise", list(EXERCISES), format_func=lambda k: EXERCISES[k].label, horizontal=True)
    ex = EXERCISES[key]
    c1, c2, c3 = st.columns(3)
    reps = c1.number_input("Reps per set", 1, 50, ex.default_reps)
    sets = c2.number_input("Sets", 1, 10, 3)
    rest = c3.number_input("Rest between sets (s)", 5, 300, 45, step=5)

    with st.container(border=True):
        st.markdown(f"**Camera setup - {ex.view}**  \n{ex.setup_tip}")
        st.markdown(
            f"Full rep = joint angle from **> {ex.extended_above:.0f}°** down to "
            f"**< {ex.flexed_below:.0f}°** (green target line). Partial reps are not counted."
        )
    if st.button("▶  Start training", type="primary", use_container_width=True):
        ss.update(stage="train", cfg=dict(key=key, reps=int(reps), sets=int(sets), rest=int(rest)), paused=False, summary=None)
        st.rerun()


# ------------------------------------------------------------------ train page
def page_train() -> None:
    st.markdown(FULLSCREEN_CSS, unsafe_allow_html=True)
    cfg = ss.cfg
    b1, b2, _ = st.columns([1, 1, 6])
    if b1.button("▶ Resume" if ss.paused else "⏸ Pause", use_container_width=True):
        ss.paused = not ss.paused
    end = b2.button("⏹ End session", type="primary", use_container_width=True)

    ctx = webrtc_streamer(
        key="coach",
        video_processor_factory=CoachProcessor,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": {"width": {"ideal": 1280}, "height": {"ideal": 720}}, "audio": False},
        # the component lives in an iframe, so page CSS cannot reach the <video>: size it here
        video_html_attrs={"autoPlay": True, "controls": True, "muted": True,
                          "style": {"width": "100%", "background": "#000", "borderRadius": "10px", "objectFit": "contain"}},
        desired_playing_state=True,
        async_processing=True,
    )
    proc = ctx.video_processor
    if proc:
        proc.configure(cfg["key"], cfg["reps"], cfg["sets"], cfg["rest"])
        proc.paused = ss.paused
        if proc.model_error:
            st.error(f"Pose model could not load: {proc.model_error}")
    else:
        st.info("Allow camera access in your browser, then step back so your full body is visible.")

    if end:
        ss.summary = proc.snapshot() if proc else None
        ss.stage = "summary"
        st.rerun()


# ---------------------------------------------------------------- summary page
def page_summary() -> None:
    s = ss.summary
    st.title("Session summary")
    if not s or not s["records"]:
        st.warning("No reps were recorded in this session.")
    else:
        m = st.columns(4)
        m[0].metric("Reps counted", s["reps_counted"])
        m[1].metric("Clean-form reps", s["clean_reps"])
        m[2].metric("Avg depth", f"{s['avg_depth_pct']}%")
        m[3].metric("Partial reps", s["partial_reps"])
        df = pd.DataFrame(s["records"]).rename(columns={"min_angle": "lowest angle", "depth_pct": "depth %", "duration_s": "seconds"})
        df["issues"] = df["issues"].apply(lambda x: "; ".join(x) if x else "-")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Coach feedback")
        lang = st.selectbox("Language", ["English", "Hindi", "Telugu", "Tamil", "Spanish"], index=0)
        if st.button("Get coach feedback", type="primary"):
            with st.spinner("Your coach is reviewing the session..."):
                ss.feedback = get_feedback(s, api_key(), lang)
        if ss.get("feedback"):
            text, source = ss.feedback
            st.write(text)
            st.caption(f"Source: {source}")

    if st.button("↺ Train again"):
        ss.update(stage="select", feedback=None)
        st.rerun()


{"select": page_select, "train": page_train, "summary": page_summary}[ss.stage]()
