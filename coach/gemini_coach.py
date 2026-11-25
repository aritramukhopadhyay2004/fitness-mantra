"""The coach's "brain": turns a finished session's metrics into plain-language coaching.

Gemini is called AFTER a set / session with a compact JSON summary, never per video
frame (too slow and costly). Real-time cues come from the rule engine instead.

In MANTRA, replace `gemini_feedback` with a call through backend/app/providers
(LLMProvider) so the key, model choice, credits and mock mode are handled in one place.
"""
from __future__ import annotations

import json
import os
from typing import Optional

SYSTEM_RULES = """You are a supportive, concise strength-and-fitness coach.
Use ONLY the session data provided; do not invent numbers.
Give: (1) one-sentence overall verdict, (2) the top 2-3 things to fix, each with one
simple cue the person can remember, (3) one positive thing, (4) a suggestion for the next session.
Under 150 words. Plain text, no markdown tables. Not medical advice: if the person
mentions pain or injury, tell them to stop and consult a professional."""


def build_prompt(
    summary: dict,
    language: str = "English",
    live_suggestions: Optional[list[dict]] = None,
    achievements: Optional[list[str]] = None,
) -> str:
    slim = {k: v for k, v in summary.items() if k != "records"}
    slim["per_rep"] = [
        {k: r[k] for k in ("set", "rep", "counted", "depth_pct", "duration_s", "issues")}
        for r in summary.get("records", [])
    ][:60]
    if achievements:
        slim["achievements_and_records_met"] = achievements
    if live_suggestions:
        slim["live_suggestions_given"] = [
            {"set": s.get("set"), "rep": s.get("rep"), "tip": s.get("suggestion")}
            for s in live_suggestions[-20:]
        ]
    return f"{SYSTEM_RULES}\n\nRespond in {language}.\n\nSESSION DATA (JSON):\n{json.dumps(slim, indent=2)}"


def local_feedback(summary: dict) -> str:
    """Offline fallback so the app works without an API key."""
    n, clean, partial = summary["reps_counted"], summary["clean_reps"], summary["partial_reps"]
    if n == 0 and partial == 0:
        return "No reps were detected. Check the camera angle and make sure your full body is visible."
    lines = [f"You completed {n} full {summary['exercise'].lower()} reps ({clean} with clean form)."]
    if summary["avg_depth_pct"]:
        lines.append(f"Average range of motion: {summary['avg_depth_pct']}% of the target depth.")
    if partial:
        lines.append(f"{partial} partial rep(s) were not counted - aim to reach the green target line.")
    for issue, cnt in sorted(summary["form_issue_counts"].items(), key=lambda kv: -kv[1])[:3]:
        lines.append(f"Fix: {issue} (seen in {cnt} rep{'s' if cnt != 1 else ''}).")
    if clean == n and n:
        lines.append("Great consistency - consider adding reps or load next time.")
    return "\n".join(lines)


def _generate_text(api_key: str, prompt: str, model: Optional[str] = None) -> str:
    from google import genai

    client = genai.Client(api_key=api_key)
    primary = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    candidates = [primary] if primary == "gemini-3.8-flash-lite" else [primary, "gemini-3.8-flash-lite"]
    last_err = None
    for m in candidates:
        try:
            resp = client.models.generate_content(model=m, contents=prompt)
            text = (resp.text or "").strip()
            if text:
                return text
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return ""


def gemini_feedback(
    summary: dict,
    api_key: str,
    model: Optional[str] = None,
    language: str = "English",
    live_suggestions: Optional[list[dict]] = None,
    achievements: Optional[list[str]] = None,
) -> str:
    prompt = build_prompt(summary, language, live_suggestions, achievements)
    return _generate_text(api_key, prompt, model=model)


def get_feedback(
    summary: dict,
    api_key: Optional[str] = None,
    language: str = "English",
    live_suggestions: Optional[list[dict]] = None,
    achievements: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Returns (text, source) where source is 'gemini' or 'local' (with reason if it fell back)."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if key:
        try:
            text = gemini_feedback(
                summary,
                key,
                language=language,
                live_suggestions=live_suggestions,
                achievements=achievements,
            )
            if text:
                return text, "gemini"
        except Exception as e:
            return local_feedback(summary), f"local (Gemini failed: {type(e).__name__}: {e})"
    return local_feedback(summary), "local (no GEMINI_API_KEY set)"


def _local_live_tip(snapshot: dict, achievements: list[str]) -> str:
    last = snapshot.get("last_rep") or {}
    issues = last.get("issues") or []
    depth = last.get("depth_pct", 0)
    prefix = f"Milestone: {achievements[0]} " if achievements else ""
    if not last.get("counted", True):
        return f"{prefix}Partial rep ({depth}% depth) — lower to the green target line."
    if issues:
        return f"{prefix}Rep {snapshot.get('reps_counted', 0)} counted ({depth}% depth). Fix: {issues[0]}."
    return f"{prefix}Clean rep ({depth}% depth)! Keep that steady tempo and posture."


def live_coach_tip(
    snapshot: dict,
    achievements: list[str],
    api_key: Optional[str] = None,
    language: str = "English",
) -> tuple[str, str]:
    """Generate a short real-time coaching tip during a live workout."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return _local_live_tip(snapshot, achievements), "local"
    try:
        prompt = (
            "You are a live strength & posture coach watching a workout in real time. "
            f"Respond in {language} in 1-2 short sentences (under 35 words). "
            "Highlight any achievement/record met and give one specific form or posture cue based ONLY on this JSON:\n"
            f"{json.dumps({'snapshot': snapshot, 'new_achievements': achievements})}"
        )
        text = _generate_text(key, prompt)
        if text:
            return text, "gemini"
    except Exception as e:
        return _local_live_tip(snapshot, achievements), f"local ({type(e).__name__})"
    return _local_live_tip(snapshot, achievements), "local"
