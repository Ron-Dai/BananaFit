"""Shared per-frame processing pipeline used by both main.py and server.py."""

from pose.analyzer import compute_key_angles
from utils.drawing import draw_skeleton, draw_angles, draw_curl_hud


def process_frame(frame, detector, curl):
    """Run pose detection + curl tracking on frame, drawing overlays in place.

    Shared by main.py (cv2 window) and server.py (web stream) so the two
    front ends never drift out of sync with each other.
    """
    results   = detector.detect(frame)
    landmarks = detector.get_landmarks(results, frame.shape)
    angles    = compute_key_angles(landmarks)

    curl.update(landmarks, angles)
    draw_skeleton(frame, landmarks)
    draw_angles(frame, landmarks, angles)
    draw_curl_hud(frame,
                  rep_count=curl.rep_count,
                  last_score=curl.last_rep_score,
                  warnings=curl.warnings,
                  is_good_form=curl.is_good_form)
    return frame
