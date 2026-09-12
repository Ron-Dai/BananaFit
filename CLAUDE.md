# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

A gym assistant app that uses computer vision to analyze workout posture in real time and provide professional feedback. Core features (see README.md):
- Equipment recognition and usage explanation
- Muscle-group mapping per exercise
- Workout routine planner based on scanned equipment
- Real-time posture recognition via MediaPipe
- Simultaneous professional coaching advice

The routine planner is not implemented yet — `planner/base.py` defines the interface a future implementation should satisfy. Equipment recognition exists (`equipment/`, two backends) and is wired into `server.py`'s web UI, but not into `main.py`'s cv2-window path.

## Tech Stack

- **Pose estimation**: MediaPipe Pose (`mediapipe`) — landmark extraction from live or recorded video
- **Equipment recognition**: YOLO-World (`ultralytics`) — open-vocabulary detection, prompted with gym-equipment class names directly; a COCO-trained SSD MobileNetV2 (`cv2.dnn`) backend also exists as a lower-fidelity fallback (see Architecture below)
- **Computer vision**: OpenCV (`opencv-python`) — camera capture, frame rendering, annotation
- **ML / classification**: scikit-learn or a lightweight TensorFlow/ONNX model for exercise and posture classification (aspirational — `exercises/classifier.py` is currently pure geometric rule-based, no trained model)
- **UI**: FastAPI (`server.py`) + React/Vite (`frontend/`) web UI; a local OpenCV window (`main.py`) is also available for the pose pipeline alone

## Architecture

```
main.py                        # CLI entry point: cv2-window camera loop (pose + curl tracking only)
server.py                      # FastAPI entry point: MJPEG streams for frontend/ (pose + equipment)
pipeline.py                    # process_frame() — shared per-frame pose+curl logic for main.py and server.py
run.ps1                        # Launches server.py + `npm run dev` together
pose/
├── detector.py                 # MediaPipe Tasks API wrapper — landmark extraction, auto-downloads model
├── analyzer.py                 # LM landmark-index map + compute_key_angles() (joint angle calculations)
└── feedback.py                 # Generic rule-based coaching text — NOT currently wired into main.py/server.py
exercises/
├── base.py                     # ExerciseTracker(ABC) — contract every rep/form tracker must implement
├── registry.py                 # EXERCISES dict: muscles, description, key_joints per exercise
├── classifier.py                # classify_exercise() — geometric heuristics, NOT currently wired into main.py/server.py
└── curl_tracker.py              # CurlTracker(ExerciseTracker) — per-rep counting + form scoring, bicep curl only
equipment/
├── base.py                     # EquipmentDetector(ABC) — contract every detector backend must implement
├── registry.py                 # EQUIPMENT dict + both backends' class vocabularies (see below)
├── recognizer.py                # EquipmentRecognizer(EquipmentDetector) — COCO-trained SSD MobileNetV2 via cv2.dnn
└── yolo_recognizer.py            # YoloWorldRecognizer(EquipmentDetector) — open-vocabulary YOLO-World, wired into server.py
utils/
└── drawing.py                   # Skeleton/angle/equipment-box overlays + both HUD styles (generic + curl-specific)
planner/
└── base.py                     # WorkoutScheduler(ABC) — interface only, nothing implements this yet
stats/
└── base.py                     # ProgressTracker(ABC) — interface only, nothing implements this yet
tools/
└── dataset_skeletons.py         # Standalone CLI: batch-annotate a dataset with skeletons + angle CSVs
frontend/                       # React/Vite web UI — see frontend/src/main.jsx
```

Key data flow (see `pipeline.py`'s `process_frame()`, shared by both `main.py` and `server.py`):
1. Open webcam, read frames via OpenCV in a loop (`main.py`'s own loop, or `server.py`'s `_frames()` generator for the `/video_feed` MJPEG stream).
2. Frame → `pose/detector.py` `PoseDetector.detect()` + `get_landmarks()` → `(33, 4)` float32 array `[x_px, y_px, z_px, visibility]`, or `None` if no person detected.
3. Landmarks → `pose/analyzer.py` `compute_key_angles()` → dict of joint-name → angle in degrees (elbows, knees, hips, L/R).
4. Landmarks + angles → `exercises/curl_tracker.py` `CurlTracker.update()`, which drives a per-arm phase state machine (`extended` ↔ `active`), counts reps, and scores each rep's form (shoulder-shrug check, elbow-drift check).
   - An arm is only counted while it is **in frame and awake**. All three of shoulder/elbow/wrist must clear `_MIN_VISIBILITY` (the elbow angle is meaningless otherwise — MediaPipe reports off-screen joints as low-visibility guesses, which produced phantom reps), and an arm that hangs extended for `_REST_FRAMES` stands down until a bend sustained over `_WAKE_FRAMES` wakes it. Both paths go through `_stand_down()`, which abandons any rep in progress.
5. `utils/drawing.py` renders `draw_skeleton()` (fixed colour; see `exercises/base.py`'s `get_color()` for the form-based-colour hook this could opt back into), `draw_angles()`, and `draw_curl_hud()` (rep count, last-rep score, form badge, warnings).

**The app is bicep-curl-only right now.** `exercises/classifier.py` and `pose/feedback.py` (plus `draw_feedback()` in `utils/drawing.py`) are complete and tested but deliberately *not* imported by `main.py`/`server.py`: classification misfires mid-set used to switch modes and discard the rep count. Re-wiring them means giving each exercise its own `exercises/base.py` `ExerciseTracker` subclass so a mode switch no longer resets state — `CurlTracker` is the pattern to follow (see "Extending" below).

**Equipment recognition (`equipment/`) has two backends behind one interface** — `equipment/base.py`'s `EquipmentDetector` ABC — and is wired into `server.py`'s `/equipment_feed` MJPEG stream (frontend's "Equipment Recognition" page), but not into `main.py`'s cv2-window path:
- `YoloWorldRecognizer` (`yolo_recognizer.py`) is the one `server.py` actually uses. It wraps YOLO-World (`ultralytics`), an open-vocabulary detector: `equipment/registry.py`'s `YOLO_WORLD_CLASSES` list is passed straight to `set_classes()`, so it detects real gym-equipment names directly — no proxy mapping needed. The model (`yolov8s-worldv2.pt`, ~370 MB incl. CLIP text encoder) auto-downloads on first use via `ultralytics`.
- `EquipmentRecognizer` (`recognizer.py`) wraps a COCO-trained SSD MobileNetV2 (`cv2.dnn_DetectionModel`) instead — kept as a lighter-weight alternative backend, not currently used by `server.py`. Unlike `pose/detector.py`'s model, its two model files (`frozen_inference_graph.pb`, `ssd_mobilenet_v2_coco_2018_03_29.pbtxt`) are **not auto-downloaded** — there's no single URL pinned with enough confidence to fetch silently, so the constructor raises `FileNotFoundError` with manual-download instructions if they're missing from `equipment/`. COCO has no gym-equipment classes, so `equipment/registry.py`'s `DETECTOR_CLASS_TO_TAG` maps only the few COCO classes with any real-world resemblance to gym equipment (e.g. COCO `'bench'`, a park bench, standing in for a weight bench) — everything else resolves to `'unknown'`.
- Both backends implement `scan(frame_bgr)`; `EquipmentDetector` gives them `best_tag()` and `describe()` for free (single-shot convenience lookups) so neither subclass duplicates that logic.

## Extending

- **New exercise** (squat, pushup, ...): subclass `exercises/base.py`'s `ExerciseTracker`, following `CurlTracker`'s per-arm phase state machine (`_ArmTracker` in `curl_tracker.py`) as the pattern — a generic exercise doesn't get rep-tracking through `exercises/registry.py` alone; it needs its own tracker class, a dedicated branch in `main.py`/`server.py`, and a HUD renderer in `utils/drawing.py`.
- **New equipment-detector backend**: subclass `equipment/base.py`'s `EquipmentDetector` and implement `scan()`; `best_tag()`/`describe()` come for free.
- **Workout planner/calendar, progress statistics**: `planner/base.py`'s `WorkoutScheduler` and `stats/base.py`'s `ProgressTracker` are interface-only ABCs for these — nothing implements them yet. Build against those contracts rather than inventing new shapes.

## Running the App

```powershell
# Install dependencies (requires standard CPython — NOT the MSYS2/msys64 python)
# Use: C:\Users\liqiy\AppData\Local\Python\bin\python.exe
python -m pip install mediapipe opencv-python fastapi uvicorn ultralytics

# Web UI (pose + equipment recognition, models auto-download on first use):
.\run.ps1                 # starts server.py + `npm run dev` together, or run them separately:
python server.py          # FastAPI backend on :8000
cd frontend; npm run dev  # Vite dev server, prints its own local URL

# Standalone CLI alternative (pose + curl tracking only, no equipment recognition):
python main.py
```

> **Note:** MediaPipe 1.0+ dropped the `solutions` API. This project uses the Tasks API (`mp.tasks.vision.PoseLandmarker`). The model file (`pose/pose_landmarker.task`) and YOLO-World's weights (`yolov8s-worldv2.pt`) both download automatically on first use.

`equipment/recognizer.py` (the COCO/SSD backend, not the one `server.py` uses) needs `frozen_inference_graph.pb` and `ssd_mobilenet_v2_coco_2018_03_29.pbtxt` placed manually in `equipment/` before `EquipmentRecognizer()` will construct (see the Architecture section above for why this one isn't auto-downloaded).

## Key Conventions

- Landmark indices follow [MediaPipe Pose landmark numbering](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) (0–32); `pose/analyzer.py`'s `LM` dict is the canonical name → index map other modules import from.
- Landmarks are passed around as a `(33, 4)` numpy array `[x_px, y_px, z_px, visibility]`, not raw MediaPipe objects. `visibility < 0.5` is the convention for "don't trust this landmark" (used in `drawing.py` and `curl_tracker.py`).
- Joint angles are calculated as vectors between three landmarks (e.g., shoulder–elbow–wrist for elbow angle).
- Posture rules live in `exercises/registry.py` as plain dicts; keep them data-driven so new exercises don't require new code paths — except for exercises that need rep tracking, which follow the `CurlTracker` pattern above instead.
- OpenCV windows are destroyed in a `finally` block in `main.py` to prevent orphaned windows on crash.
