"""Datewise training records and personal-record / achievement tracking."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "training_records.json"


def _empty_store() -> dict[str, Any]:
    return {"personal_records": {}, "by_date": {}}


def load_records() -> dict[str, Any]:
    """Load persisted datewise training records and personal bests."""
    try:
        if DATA_PATH.exists():
            data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("personal_records", {})
                data.setdefault("by_date", {})
                return data
    except Exception:
        pass
    return _empty_store()


def _write_records(store: dict[str, Any]) -> None:
    try:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    except Exception:
        # Ephemeral or read-only filesystem fallback: caller still keeps state in session_state
        pass


def check_live_achievements(
    snapshot: dict[str, Any],
    store: dict[str, Any],
    already_awarded: set[str],
) -> list[str]:
    """Check for real-time achievements & personal records met during a live workout."""
    ex_name = snapshot.get("exercise", "Exercise")
    prs = store.get("personal_records", {}).get(ex_name, {})
    last_rep = snapshot.get("last_rep") or {}
    reps_counted = int(snapshot.get("reps_counted", 0))
    clean_reps = int(snapshot.get("clean_reps", 0))
    clean_streak = int(snapshot.get("clean_streak", 0))
    depth_pct = int(last_rep.get("depth_pct", 0))
    counted = bool(last_rep.get("counted", False))

    new_hits: list[str] = []

    def award(key: str, label: str) -> None:
        if key not in already_awarded:
            already_awarded.add(key)
            new_hits.append(label)

    if counted and reps_counted == 1:
        award("first_rep", f"First {ex_name} rep completed!")
    if clean_streak >= 3:
        award(f"streak_{clean_streak}", f"{clean_streak} clean-form reps in a row!")
    if counted and depth_pct >= 100 and depth_pct > int(prs.get("best_depth_pct", 0)):
        award(f"depth_pr_{depth_pct}", f"New depth record: {depth_pct}%!")
    if reps_counted > int(prs.get("best_reps_in_session", 0)) and int(prs.get("best_reps_in_session", 0)) > 0:
        award("rep_pr", f"New session rep record: {reps_counted} reps!")
    if clean_reps > int(prs.get("best_clean_reps", 0)) and int(prs.get("best_clean_reps", 0)) > 0:
        award("clean_pr", f"New clean-form record: {clean_reps} clean reps!")
    if snapshot.get("set_completed"):
        award(f"set_{snapshot.get('sets_completed', 1)}", f"Set {snapshot.get('sets_completed', 1)} completed!")

    return new_hits


def save_session_record(
    store: dict[str, Any],
    summary: dict[str, Any],
    live_suggestions: list[dict[str, Any]],
    achievements: list[str],
    final_feedback: str,
    feedback_source: str,
) -> dict[str, Any]:
    """Update personal records and append the completed session under today's date."""
    now = datetime.now()
    date_key = now.strftime("%Y-%m-%d")
    ex_name = summary.get("exercise", "Exercise")

    prs_all = store.setdefault("personal_records", {})
    ex_pr = prs_all.setdefault(
        ex_name,
        {
            "best_reps_in_session": 0,
            "best_clean_reps": 0,
            "best_depth_pct": 0,
            "total_sessions": 0,
            "total_reps": 0,
        },
    )

    reps_counted = int(summary.get("reps_counted", 0))
    clean_reps = int(summary.get("clean_reps", 0))
    counted_records = [r for r in summary.get("records", []) if r.get("counted")]
    max_depth = max((int(r.get("depth_pct", 0)) for r in counted_records), default=0)

    final_achievements = list(achievements)
    if reps_counted > 0 and reps_counted > ex_pr["best_reps_in_session"]:
        msg = f"Session Rep PR ({ex_name}): {reps_counted} reps"
        if msg not in final_achievements:
            final_achievements.append(msg)
    if clean_reps > 0 and clean_reps > ex_pr["best_clean_reps"]:
        msg = f"Clean Form PR ({ex_name}): {clean_reps} reps"
        if msg not in final_achievements:
            final_achievements.append(msg)
    if max_depth > ex_pr["best_depth_pct"]:
        msg = f"Best Depth PR ({ex_name}): {max_depth}%"
        if msg not in final_achievements:
            final_achievements.append(msg)

    ex_pr["best_reps_in_session"] = max(ex_pr["best_reps_in_session"], reps_counted)
    ex_pr["best_clean_reps"] = max(ex_pr["best_clean_reps"], clean_reps)
    ex_pr["best_depth_pct"] = max(ex_pr["best_depth_pct"], max_depth)
    ex_pr["total_sessions"] += 1
    ex_pr["total_reps"] += reps_counted

    entry = {
        "time": now.strftime("%H:%M:%S"),
        "exercise": ex_name,
        "reps_counted": reps_counted,
        "clean_reps": clean_reps,
        "partial_reps": int(summary.get("partial_reps", 0)),
        "avg_depth_pct": int(summary.get("avg_depth_pct", 0)),
        "avg_rep_seconds": float(summary.get("avg_rep_seconds", 0.0)),
        "form_issue_counts": summary.get("form_issue_counts", {}),
        "achievements": final_achievements,
        "live_suggestions": live_suggestions,
        "final_feedback": final_feedback,
        "feedback_source": feedback_source,
    }

    by_date = store.setdefault("by_date", {})
    by_date.setdefault(date_key, []).append(entry)
    _write_records(store)
    return entry
