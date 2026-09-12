import cv2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pose.detector import PoseDetector
from exercises.curl_tracker import CurlTracker
from pipeline import process_frame
from equipment.yolo_recognizer import YoloWorldRecognizer
from utils.drawing import draw_equipment_boxes

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['GET'],
    allow_headers=['*'],
)


def _frames():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError('Error: cannot open webcam.')

    detector = PoseDetector()
    curl     = CurlTracker()
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            process_frame(frame, detector, curl)

            ok, jpeg = cv2.imencode('.jpg', frame)
            if not ok:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    finally:
        cap.release()
        detector.close()


@app.get('/video_feed')
def video_feed():
    """MJPEG stream of the annotated webcam feed for the frontend's <img> tag."""
    return StreamingResponse(_frames(), media_type='multipart/x-mixed-replace; boundary=frame')


_equipment_recognizer = None


def _get_equipment_recognizer():
    # Loading YOLO-World (weights + CLIP text embeddings) is expensive, so
    # it's cached across requests instead of rebuilt on every connection.
    global _equipment_recognizer
    if _equipment_recognizer is None:
        _equipment_recognizer = YoloWorldRecognizer()
    return _equipment_recognizer


def _equipment_frames():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError('Error: cannot open webcam.')

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
    return StreamingResponse(_equipment_frames(), media_type='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
