# AI Fitness Coach (Streamlit prototype)

Live camera -> pose landmarks -> joint angles -> rep/set counting + form cues, drawn onto the video
(target line, gauge, angle readout). Gemini writes the post-session coaching.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=...        # optional; without it you get an offline rule-based summary
export GEMINI_MODEL=...          # optional; defaults to gemini-2.5-flash (change if retired)
streamlit run app.py
```
First run downloads the MediaPipe pose model (~6 MB) into `models/`. Allow camera access in the browser.
Use the browser's native full-screen button on the video: the overlay is burned into the frames, so it stays.

## Layout
```
core/        framework-free logic  (geometry, smoothing, rep state machine, engine, pose backend)
exercises/   one config per exercise (angles, tolerances, form checks, cues)  <- add exercises here
ui/          overlay drawing + streamlit-webrtc video processor
coach/       Gemini coach (post-set only) + offline fallback
tests/       pytest with a synthetic skeleton (no camera needed):  python -m pytest -q tests
app.py       select -> train (live) -> summary
```

## Add an exercise
Add an `Exercise(...)` in `exercises/configs.py` and register it in `EXERCISES`:
joint triplet, `extended_above` / `flexed_below` angles, `moving_end` ("a" = proximal end travels, e.g. hip in a squat;
"c" = distal end, e.g. wrist in a curl), and `FormCheck`s (joint angle range, or segment tilt from vertical).
**All thresholds are starting values - have a trainer/physio review them.**

## Known limits
- 2D side-view angles only; wrong camera angle = wrong numbers (the app asks for the full body and says what is missing).
- One person, one working side (the better-seen side is picked automatically).
- Valgus knees, grip, bar path etc. need a front view / more landmarks - not covered yet.

## Porting to MANTRA later
- `core/` and `exercises/` have no framework imports: move to `backend/app/services/` (or port to TS).
- Per-frame work should run in the browser (MediaPipe Tasks Vision JS in React) - sending video to FastAPI adds latency.
  The browser sends only the finished **session summary JSON** to the backend.
- Replace `coach/gemini_coach.py::gemini_feedback` with MANTRA's `providers/` (`LLMProvider`) so keys, credits and the
  mock provider are reused; add the form limits to `domains/rules/fitness.yaml`; expose `/v1/fitness/session` in `endpoints/`.
