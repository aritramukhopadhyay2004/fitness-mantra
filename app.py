"""AI Fitness Coach - Streamlit app.  Run:  streamlit run app.py

Flow: choose exercise -> live browser pose tracking + real-time Gemini coaching -> datewise records & summary.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from coach.gemini_coach import get_feedback, live_coach_tip
from coach.records import check_live_achievements, load_records, save_session_record
from exercises.configs import EXERCISES

st.set_page_config(page_title="AI Fitness Coach", page_icon="\U0001F3CB", layout="wide")

_TRACKER_DIR = Path(__file__).resolve().parent / "ui" / "browser_tracker"
_browser_tracker = components.declare_component("browser_tracker", path=str(_TRACKER_DIR))

ss = st.session_state
ss.setdefault("stage", "select")
ss.setdefault("summary", None)
ss.setdefault("live_suggestions", [])
ss.setdefault("achievements", [])
ss.setdefault("awarded_keys", set())
ss.setdefault("live_bests", {})
ss.setdefault("latest_achievement", "")
ss.setdefault("last_event_id", None)
ss.setdefault("live_ai_tip", "")
ss.setdefault("training_store", load_records())
ss.setdefault("language", "English")


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


def render_datewise_records(store: dict) -> None:
    by_date = store.get("by_date", {})
    prs = store.get("personal_records", {})
    if not by_date:
        return

    st.subheader("Datewise Training Records")
    if prs:
        pr_cols = st.columns(len(prs))
        for col, (ex_name, pr) in zip(pr_cols, prs.items()):
            col.metric(
                f"{ex_name} PR",
                f"{pr.get('best_reps_in_session', 0)} reps",
                f"Best depth: {pr.get('best_depth_pct', 0)}%",
            )

    for date_key in sorted(by_date.keys(), reverse=True):
        sessions = by_date[date_key]
        with st.expander(f"{date_key} ({len(sessions)} session{'s' if len(sessions) != 1 else ''})", expanded=(date_key == sorted(by_date.keys(), reverse=True)[0])):
            for idx, entry in enumerate(reversed(sessions), 1):
                st.markdown(
                    f"**#{idx} · {entry.get('time', '')} — {entry.get('exercise', '')}** "
                    f"({entry.get('reps_counted', 0)} reps, {entry.get('clean_reps', 0)} clean, "
                    f"avg depth {entry.get('avg_depth_pct', 0)}%)"
                )
                if entry.get("achievements"):
                    st.caption("Achievements: " + " | ".join(entry["achievements"]))
                if entry.get("live_suggestions"):
                    with st.popover(f"View {len(entry['live_suggestions'])} live suggestions"):
                        for s in entry["live_suggestions"]:
                            st.write(f"- **[{s.get('time', '')}] Set {s.get('set', 1)}, Rep {s.get('rep', 0)}**: {s.get('suggestion', '')}")
                if entry.get("final_feedback"):
                    st.info(entry["final_feedback"])


# ------------------------------------------------------------------ select page
def page_select() -> None:
    st.title("\U0001F3CB AI Fitness Coach")
    st.caption("Live posture tracking, real-time Gemini coaching, achievements, and datewise training records.")

    key = st.radio("Choose your exercise", list(EXERCISES), format_func=lambda k: EXERCISES[k].label, horizontal=True)
    ex = EXERCISES[key]
    c1, c2, c3, c4 = st.columns(4)
    reps = c1.number_input("Reps per set", 1, 50, ex.default_reps)
    sets = c2.number_input("Sets", 1, 10, 3)
    rest = c3.number_input("Rest between sets (s)", 5, 300, 45, step=5)
    lang = c4.selectbox("Coach language", ["English", "Hindi", "Telugu", "Tamil", "Spanish"], index=0)

    with st.container(border=True):
        st.markdown(f"**Camera setup - {ex.view}**  \n{ex.setup_tip}")
        st.markdown(
            f"Full rep = joint angle from **> {ex.extended_above:.0f}°** down to "
            f"**< {ex.flexed_below:.0f}°** (green target line). Partial reps are not counted."
        )
    if st.button("▶  Start training", type="primary", use_container_width=True):
        ss.update(
            stage="train",
            cfg=dict(key=key, reps=int(reps), sets=int(sets), rest=int(rest)),
            language=lang,
            summary=None,
            feedback=None,
            live_suggestions=[],
            achievements=[],
            awarded_keys=set(),
            live_bests={},
            latest_achievement="",
            last_event_id=None,
            live_ai_tip="",
        )
        st.rerun()

    render_datewise_records(ss.training_store)


# ------------------------------------------------------------------ train page
def page_train() -> None:
    st.markdown(FULLSCREEN_CSS, unsafe_allow_html=True)
    cfg = ss.cfg
    ex_dict = asdict(EXERCISES[cfg["key"]])
    payload = _browser_tracker(
        exercise=ex_dict,
        reps=cfg["reps"],
        sets=cfg["sets"],
        rest_s=cfg["rest"],
        live_ai_tip=ss.live_ai_tip,
        key=f"coach_{cfg['key']}_{cfg['reps']}_{cfg['sets']}_{cfg['rest']}",
    )

    if isinstance(payload, dict):
        event_id = payload.get("event_id")
        event = payload.get("event")
        if event == "rep" and event_id and event_id != ss.last_event_id:
            ss.last_event_id = event_id
            snap = payload.get("snapshot") or {}
            new_hits = check_live_achievements(snap, ss.training_store, ss.awarded_keys, ss.live_bests)
            if new_hits:
                ss.achievements.extend(new_hits)
                ss.latest_achievement = new_hits[-1]
            tip, src = live_coach_tip(snap, new_hits, api_key(), ss.language)
            ss.live_ai_tip = tip
            ss.live_suggestions.append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "set": snap.get("set_no", 1),
                    "rep": snap.get("reps_counted", 0),
                    "suggestion": tip,
                    "achievements": new_hits,
                    "source": src,
                }
            )
            st.rerun()
        elif event == "end" and event_id and event_id != ss.last_event_id:
            ss.last_event_id = event_id
            summary = payload.get("summary") or {"records": []}
            if summary.get("records"):
                text, source = get_feedback(
                    summary,
                    api_key(),
                    ss.language,
                    live_suggestions=ss.live_suggestions,
                    achievements=ss.achievements,
                )
                ss.feedback = (text, source)
                save_session_record(
                    ss.training_store,
                    summary,
                    ss.live_suggestions,
                    ss.achievements,
                    text,
                    source,
                )
            else:
                ss.feedback = None
            ss.summary = summary
            ss.stage = "summary"
            st.rerun()

    if ss.latest_achievement:
        st.success(f"Latest Achievement / Record: {ss.latest_achievement}")


# ---------------------------------------------------------------- summary page
def page_summary() -> None:
    s = ss.summary
    st.title("Session summary")
    if not s or not s.get("records"):
        st.warning("No reps were recorded in this session.")
    else:
        m = st.columns(4)
        m[0].metric("Reps counted", s["reps_counted"])
        m[1].metric("Clean-form reps", s["clean_reps"])
        m[2].metric("Avg depth", f"{s['avg_depth_pct']}%")
        m[3].metric("Partial reps", s["partial_reps"])

        if ss.achievements:
            st.subheader("Achievements & Records Met")
            for a in ss.achievements:
                st.success(a)

        df = pd.DataFrame(s["records"]).rename(columns={"min_angle": "lowest angle", "depth_pct": "depth %", "duration_s": "seconds"})
        df["issues"] = df["issues"].apply(lambda x: "; ".join(x) if x else "-")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Final Coach Summary")
        lang = st.selectbox(
            "Language",
            ["English", "Hindi", "Telugu", "Tamil", "Spanish"],
            index=["English", "Hindi", "Telugu", "Tamil", "Spanish"].index(ss.language)
            if ss.language in ["English", "Hindi", "Telugu", "Tamil", "Spanish"]
            else 0,
        )
        if st.button("Regenerate coach feedback", type="primary"):
            with st.spinner("Your coach is reviewing the session..."):
                ss.feedback = get_feedback(
                    s,
                    api_key(),
                    lang,
                    live_suggestions=ss.live_suggestions,
                    achievements=ss.achievements,
                )
        if ss.get("feedback"):
            text, source = ss.feedback
            st.write(text)
            st.caption(f"Source: {source}")

        if ss.live_suggestions:
            with st.expander(f"Real-time suggestions given during this workout ({len(ss.live_suggestions)})", expanded=True):
                for item in ss.live_suggestions:
                    st.write(f"- **[{item['time']}] Set {item['set']}, Rep {item['rep']}**: {item['suggestion']}")

    render_datewise_records(ss.training_store)

    if st.button("↺ Train again"):
        ss.update(
            stage="select",
            feedback=None,
            live_suggestions=[],
            achievements=[],
            awarded_keys=set(),
            live_bests={},
            latest_achievement="",
            last_event_id=None,
            live_ai_tip="",
        )
        st.rerun()


{"select": page_select, "train": page_train, "summary": page_summary}[ss.stage]()
