# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

A gym assistant app that uses computer vision to analyze workout posture in real time and provide professional feedback. Core features (see README.md):
- Equipment recognition and usage explanation
- Muscle-group mapping per exercise
- Workout routine planner based on scanned equipment
- Real-time posture recognition via MediaPipe
- Simultaneous professional coaching advice

## Tech Stack

- **Pose estimation**: MediaPipe Pose (`mediapipe`) — landmark extraction from live or recorded video
- **Computer vision**: OpenCV (`opencv-python`) — camera capture, frame rendering, annotation
- **ML / classification**: scikit-learn or a lightweight TensorFlow/ONNX model for exercise and posture classification
- **UI**: CLI or OpenCV window initially; upgrade path to a web UI (FastAPI + React) later

## Architecture

```
projectGym/
├── main.py                  # Entry point: camera loop + orchestration
├── pose/
│   ├── detector.py          # MediaPipe Pose wrapper — landmark extraction
│   ├── analyzer.py          # Angle/joint calculations on landmarks
│   └── feedback.py          # Rule-based or model-based posture feedback
├── exercises/
│   ├── registry.py          # Exercise definitions: muscles, correct-form rules
│   └── classifier.py        # Classify current exercise from landmarks
├── equipment/
│   └── recognizer.py        # Equipment detection (YOLO or MobileNet)
└── utils/
    └── drawing.py           # Overlay helpers (skeleton, angles, text on frame)
```

Key data flow:
1. `main.py` opens webcam, reads frames via OpenCV.
2. Each frame → `pose/detector.py` → list of 33 MediaPipe landmarks (x, y, z, visibility).
3. Landmarks → `exercises/classifier.py` → active exercise name.
4. Landmarks + exercise → `pose/analyzer.py` → joint angles.
5. Angles → `pose/feedback.py` → coaching text (e.g., "Keep your back straight").
6. `utils/drawing.py` renders skeleton + feedback onto the frame.

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

- Landmark indices follow [MediaPipe Pose landmark numbering](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) (0–32).
- Joint angles are calculated as vectors between three landmarks (e.g., shoulder–elbow–wrist for elbow angle).
- Posture rules live in `exercises/registry.py` as plain dicts; keep them data-driven so new exercises don't require new code paths.
- OpenCV windows are destroyed in a `finally` block in `main.py` to prevent orphaned windows on crash.
