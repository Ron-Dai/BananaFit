"""Unified FastAPI entry point for accounts, plans, and camera pipelines."""

import os
import sys
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parent
for package_source in (ROOT / 'fitness_intake' / 'src', ROOT / 'user_accounts' / 'src'):
    source = str(package_source)
    if source not in sys.path:
        sys.path.insert(0, source)

from controller import CoachMetricsStore, WorkoutStore, create_controller_router  # noqa: E402
from sexybanana_accounts import (  # noqa: E402
    AccountDatabase,
    AccountService,
    AccountSettings,
    build_fitness_service,
    create_router as create_account_router,
    install_exception_handlers,
)

from pose.detector import PoseDetector  # noqa: E402
from pose.yolo_detector import YoloPoseDetector  # noqa: E402
from exercises.curl_tracker import CurlTracker  # noqa: E402
from pipeline import process_frame  # noqa: E402
from equipment.yolo_recognizer import YoloWorldRecognizer  # noqa: E402
from utils.drawing import draw_equipment_boxes  # noqa: E402

settings = AccountSettings()
account_database = AccountDatabase(settings.database_path)
fitness_service = build_fitness_service(settings)
account_service = AccountService(settings, account_database, fitness_service)
coach_metrics = CoachMetricsStore()
workout_store = WorkoutStore(settings.database_path)
_browser_pose_detector = None
_browser_curl_tracker = CurlTracker()
_browser_pose_lock = Lock()

app = FastAPI(title='BananaFit API', version='0.2.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['Content-Type', 'X-CSRF-Token'],
)
install_exception_handlers(app)
app.include_router(create_account_router(account_service))
app.include_router(
    create_controller_router(account_service, coach_metrics, workout_store, ROOT)
)


@app.get('/api/health')
def health():
    """Small startup probe that does not initialize camera models."""
    return {'status': 'ok'}


def _decode_browser_frame(body: bytes):
    """Decode one bounded browser-captured JPEG without retaining its bytes."""
    if not body or len(body) > 2_500_000:
        raise HTTPException(status_code=413, detail='Camera frame is empty or too large.')
    frame = cv2.imdecode(np.frombuffer(body, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail='Camera frame is not a valid image.')
    return frame


@app.post('/api/coach/frame')
async def browser_coach_frame(request: Request):
    """Score a browser-captured frame with the existing pose and curl pipeline."""
    frame = _decode_browser_frame(await request.body())
    return await run_in_threadpool(_score_browser_frame, frame)


def _score_browser_frame(frame):
    """Run CPU inference outside the async server loop, one frame at a time."""
    global _browser_pose_detector
    with _browser_pose_lock:
        if _browser_pose_detector is None:
            # MediaPipe's native macOS graph can abort a headless web-server
            # process while creating its Metal service. Browser frames use this
            # CPU-safe adapter and keep the existing scoring pipeline unchanged.
            _browser_pose_detector = YoloPoseDetector()
        process_frame(frame, _browser_pose_detector, _browser_curl_tracker)
        coach_metrics.update_from_tracker(_browser_curl_tracker)
        return coach_metrics.snapshot()


def _open_camera():
    """Return an opened camera, or ``None`` before an HTTP stream is committed."""
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        return cap
    cap.release()
    return None


def _frames(cap):
    """Yield MJPEG-framed JPEGs of the webcam feed with pose + curl-tracking overlays."""
    detector = PoseDetector()
    curl     = CurlTracker()
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            process_frame(frame, detector, curl)
            coach_metrics.update_from_tracker(curl)

            ok, jpeg = cv2.imencode('.jpg', frame)
            if not ok:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    finally:
        coach_metrics.set_inactive()
        cap.release()
        detector.close()


@app.get('/video_feed')
def video_feed():
    """MJPEG stream of the annotated webcam feed for the frontend's <img> tag."""
    cap = _open_camera()
    if cap is None:
        coach_metrics.set_inactive()
        return Response(status_code=503)
    return StreamingResponse(
        _frames(cap), media_type='multipart/x-mixed-replace; boundary=frame'
    )


_equipment_recognizer = None


def _get_equipment_recognizer():
    """Return the process-wide YoloWorldRecognizer, building it on first use.

    Loading YOLO-World (weights + CLIP text embeddings) is expensive, so
    it's cached across requests instead of rebuilt on every connection.
    """
    global _equipment_recognizer
    if _equipment_recognizer is None:
        _equipment_recognizer = YoloWorldRecognizer()
    return _equipment_recognizer


def _equipment_frames(cap):
    """Yield MJPEG-framed JPEGs of the webcam feed with equipment detection boxes."""
    recognizer = _get_equipment_recognizer()
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            detections = recognizer.scan(frame)
            draw_equipment_boxes(frame, detections)

            ok, jpeg = cv2.imencode('.jpg', frame)
            if not ok:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    finally:
        cap.release()


@app.get('/equipment_feed')
def equipment_feed():
    """MJPEG stream of the webcam with live YOLO-World gym-equipment detections."""
    cap = _open_camera()
    if cap is None:
        return Response(status_code=503)
    return StreamingResponse(
        _equipment_frames(cap), media_type='multipart/x-mixed-replace; boundary=frame'
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host=os.environ.get('BANANAFIT_HOST', '127.0.0.1'),
        port=int(os.environ.get('BANANAFIT_PORT', '8000')),
    )
