# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

A gym assistant app that uses computer vision to analyze workout posture in real time and provide professional feedback. Core features (see README.md):
- Equipment recognition and usage explanation
- Muscle-group mapping per exercise
- Workout routine planner based on scanned equipment
- Real-time posture recognition via MediaPipe
- Simultaneous professional coaching advice

The routine planner is not implemented yet. Equipment recognition exists (`equipment/`) but is not wired into `main.py` and needs model files placed manually before it will run at all (see Running the App).

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
└── feedback.py                 # Generic rule-based coaching text — NOT currently wired into main.py
exercises/
├── registry.py                 # EXERCISES dict: muscles, description, key_joints per exercise
├── classifier.py                # classify_exercise() — geometric heuristics, NOT currently wired into main.py
└── curl_tracker.py              # CurlTracker — per-rep counting + form scoring, bicep curl only
equipment/
├── registry.py                 # EQUIPMENT dict + DETECTOR_CLASS_TO_TAG proxy mapping (see below)
└── recognizer.py                # EquipmentRecognizer — COCO-trained SSD MobileNetV2 via cv2.dnn, NOT wired into main.py
utils/
└── drawing.py                   # Skeleton/angle overlay + both HUD styles (generic + curl-specific)
```

Key data flow (see `main.py`):
1. Open webcam, read frames via OpenCV in a loop.
2. Frame → `pose/detector.py` `PoseDetector.detect()` + `get_landmarks()` → `(33, 4)` float32 array `[x_px, y_px, z_px, visibility]`, or `None` if no person detected.
3. Landmarks → `pose/analyzer.py` `compute_key_angles()` → dict of joint-name → angle in degrees (elbows, knees, hips, L/R).
4. Landmarks + angles → `exercises/curl_tracker.py` `CurlTracker.update()`, which drives a per-arm phase state machine (`extended` ↔ `active`), counts reps, and scores each rep's form (shoulder-shrug check, elbow-drift check).
   - An arm is only counted while it is **in frame and awake**. All three of shoulder/elbow/wrist must clear `_MIN_VISIBILITY` (the elbow angle is meaningless otherwise — MediaPipe reports off-screen joints as low-visibility guesses, which produced phantom reps), and an arm that hangs extended for `_REST_FRAMES` stands down until a bend sustained over `_WAKE_FRAMES` wakes it. Both paths go through `_stand_down()`, which abandons any rep in progress.
5. `utils/drawing.py` renders `draw_skeleton()` (colored by live form status), `draw_angles()`, and `draw_curl_hud()` (rep count, last-rep score, form badge, warnings).

**The app is bicep-curl-only right now.** `exercises/classifier.py` and `pose/feedback.py` (plus `draw_feedback()` in `utils/drawing.py`) are complete and tested but deliberately *not* imported by `main.py`: classification misfires mid-set used to switch modes and discard the rep count. Re-wiring them means restoring the per-exercise branch in `main.py` — and giving each exercise its own tracker so a mode switch no longer resets state.

**Equipment recognition (`equipment/`) is implemented but standalone** — not imported by `main.py`, and a different architecture from the pose pipeline:
- `EquipmentRecognizer` (`recognizer.py`) wraps a COCO-trained SSD MobileNetV2 (`cv2.dnn_DetectionModel`), not MediaPipe. Unlike `pose/detector.py`'s model, its two model files (`frozen_inference_graph.pb`, `ssd_mobilenet_v2_coco_2018_03_29.pbtxt`) are **not auto-downloaded** — there's no single URL pinned with enough confidence to fetch silently, so the constructor raises `FileNotFoundError` with manual-download instructions if they're missing from `equipment/`.
- COCO has no gym-equipment classes. `equipment/registry.py`'s `DETECTOR_CLASS_TO_TAG` maps only the few COCO classes with any real-world resemblance to gym equipment (e.g. COCO `'bench'`, a park bench, standing in for a weight bench) — everything else resolves to `'unknown'`. Treat this mapping as a placeholder, not a real classifier; the eventual fix is a model trained on actual gym equipment, not more COCO proxies.
- `scan()` returns `(tag, confidence, box)` per recognized detection; `best_tag()` and `describe()` are the convenience entry points for a single-shot lookup.

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

`equipment/recognizer.py` is unrelated to this pipeline and not imported by `main.py`; it needs `frozen_inference_graph.pb` and `ssd_mobilenet_v2_coco_2018_03_29.pbtxt` placed manually in `equipment/` before `EquipmentRecognizer()` will construct (see the Architecture section above for why this one isn't auto-downloaded).

## Key Conventions

- Landmark indices follow [MediaPipe Pose landmark numbering](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) (0–32); `pose/analyzer.py`'s `LM` dict is the canonical name → index map other modules import from.
- Landmarks are passed around as a `(33, 4)` numpy array `[x_px, y_px, z_px, visibility]`, not raw MediaPipe objects. `visibility < 0.5` is the convention for "don't trust this landmark" (used in `drawing.py` and `curl_tracker.py`).
- Joint angles are calculated as vectors between three landmarks (e.g., shoulder–elbow–wrist for elbow angle).
- Posture rules live in `exercises/registry.py` as plain dicts; keep them data-driven so new exercises don't require new code paths — except for exercises that need rep tracking, which follow the `CurlTracker` pattern above instead.
- OpenCV windows are destroyed in a `finally` block in `main.py` to prevent orphaned windows on crash.
