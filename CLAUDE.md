# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

A gym assistant app that uses computer vision to analyze workout posture in real time and provide professional feedback. Core features (see README.md):
- Equipment recognition and usage explanation
- Muscle-group mapping per exercise
- Workout routine planner based on scanned equipment
- Real-time posture recognition via MediaPipe
- Simultaneous professional coaching advice

Equipment recognition and the routine planner are not implemented yet — current code covers pose detection, exercise classification, and per-exercise feedback only.

## Tech Stack

- **Pose estimation**: MediaPipe Pose (`mediapipe`) — landmark extraction from live or recorded video
- **Computer vision**: OpenCV (`opencv-python`) — camera capture, frame rendering, annotation
- **ML / classification**: scikit-learn or a lightweight TensorFlow/ONNX model for exercise and posture classification (aspirational — `exercises/classifier.py` is currently pure geometric rule-based, no trained model)
- **UI**: CLI or OpenCV window initially; upgrade path to a web UI (FastAPI + React) later

## Architecture

```
main.py                       # Entry point: camera loop + orchestration
pose/
├── detector.py                # MediaPipe Tasks API wrapper — landmark extraction, auto-downloads model
├── analyzer.py                 # LM landmark-index map + compute_key_angles() (joint angle calculations)
└── feedback.py                 # Generic rule-based coaching text, used for non-curl exercises
exercises/
├── registry.py                 # EXERCISES dict: muscles, description, key_joints per exercise
├── classifier.py                # classify_exercise() — geometric heuristics, no ML model yet
└── curl_tracker.py              # CurlTracker — per-rep counting + form scoring, bicep curl only
utils/
└── drawing.py                   # Skeleton/angle overlay + both HUD styles (generic + curl-specific)
```

Key data flow (see `main.py`):
1. Open webcam, read frames via OpenCV in a loop.
2. Frame → `pose/detector.py` `PoseDetector.detect()` + `get_landmarks()` → `(33, 4)` float32 array `[x_px, y_px, z_px, visibility]`, or `None` if no person detected.
3. Landmarks → `pose/analyzer.py` `compute_key_angles()` → dict of joint-name → angle in degrees (elbows, knees, hips, L/R).
4. Landmarks + angles → `exercises/classifier.py` `classify_exercise()` → `'squat' | 'bicep_curl' | 'pushup' | 'unknown'`.
5. Branch on exercise:
   - **`bicep_curl`**: `exercises/curl_tracker.py` `CurlTracker.update()` drives a per-arm phase state machine (`extended` ↔ `active`) that counts reps and scores each rep's form (shoulder-shrug check, elbow-drift check). `utils/drawing.py` `draw_curl_hud()` renders rep count, last-rep score, and a form-status badge; skeleton color reflects live form status.
   - **anything else**: `CurlTracker` is discarded and recreated (rep/phase state does not persist across an exercise switch), and `pose/feedback.py` `get_feedback()` returns generic coaching messages rendered by `draw_feedback()`.
6. `draw_skeleton()` / `draw_angles()` overlay the pose skeleton and joint-angle labels every frame regardless of branch.

`CurlTracker`'s per-arm phase state machine (`_ArmTracker` in `curl_tracker.py`) is the pattern to follow when adding rep-counting/form-scoring for other exercises (e.g. squat, pushup) — a generic exercise doesn't get this treatment through `exercises/registry.py` alone; it needs its own tracker class and a dedicated branch in `main.py` plus a HUD renderer in `utils/drawing.py`.

## Running the App

```powershell
# Install dependencies (requires standard CPython — NOT the MSYS2/msys64 python)
# Use: C:\Users\liqiy\AppData\Local\Python\bin\python.exe
python -m pip install mediapipe opencv-python

# Run (model is auto-downloaded on first launch ~4 MB)
python main.py
```

> **Note:** MediaPipe 1.0+ dropped the `solutions` API. This project uses the Tasks API (`mp.tasks.vision.PoseLandmarker`). The model file (`pose/pose_landmarker.task`) is downloaded automatically on first run.

## Key Conventions

- Landmark indices follow [MediaPipe Pose landmark numbering](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) (0–32); `pose/analyzer.py`'s `LM` dict is the canonical name → index map other modules import from.
- Landmarks are passed around as a `(33, 4)` numpy array `[x_px, y_px, z_px, visibility]`, not raw MediaPipe objects. `visibility < 0.5` is the convention for "don't trust this landmark" (used in `drawing.py` and `curl_tracker.py`).
- Joint angles are calculated as vectors between three landmarks (e.g., shoulder–elbow–wrist for elbow angle).
- Posture rules live in `exercises/registry.py` as plain dicts; keep them data-driven so new exercises don't require new code paths — except for exercises that need rep tracking, which follow the `CurlTracker` pattern above instead.
- OpenCV windows are destroyed in a `finally` block in `main.py` to prevent orphaned windows on crash.
