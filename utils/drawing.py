import cv2

from pose.analyzer import LM

# Standard MediaPipe Pose skeleton connections (landmark index pairs)
_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),
    (9,10),(11,12),(11,13),(13,15),(15,17),(15,19),(15,21),(17,19),
    (12,14),(14,16),(16,18),(16,20),(16,22),(18,20),
    (11,23),(12,24),(23,24),(23,25),(24,26),(25,27),(26,28),
    (27,29),(28,30),(29,31),(30,32),(27,31),(28,32),
]

_ANGLE_JOINTS = {
    'left_elbow':  LM['left_elbow'],
    'right_elbow': LM['right_elbow'],
    'left_knee':   LM['left_knee'],
    'right_knee':  LM['right_knee'],
}


def draw_skeleton(frame, landmarks):
    if landmarks is None:
        return
    for s, e in _CONNECTIONS:
        if s >= len(landmarks) or e >= len(landmarks):
            continue
        if landmarks[s][3] < 0.5 or landmarks[e][3] < 0.5:
            continue
        cv2.line(frame,
                 (int(landmarks[s][0]), int(landmarks[s][1])),
                 (int(landmarks[e][0]), int(landmarks[e][1])),
                 (255, 255, 255), 2)
    for lm in landmarks:
        if lm[3] >= 0.5:
            cv2.circle(frame, (int(lm[0]), int(lm[1])), 4, (0, 230, 0), -1)


def draw_angles(frame, landmarks, angles):
    if landmarks is None:
        return
    for name, idx in _ANGLE_JOINTS.items():
        if name not in angles:
            continue
        x, y = int(landmarks[idx][0]), int(landmarks[idx][1])
        cv2.putText(frame, f'{int(angles[name])}°', (x - 20, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)


def draw_feedback(frame, exercise_name, feedback_messages):
    h, w = frame.shape[:2]
    panel_h = 30 + len(feedback_messages[:3]) * 28

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    label = exercise_name.replace('_', ' ').title()
    cv2.putText(frame, f'Exercise: {label}', (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 255), 2)

    for i, msg in enumerate(feedback_messages[:3]):
        good = 'good' in msg.lower() or 'keep' in msg.lower()
        color = (60, 220, 60) if good else (30, 120, 255)
        cv2.putText(frame, msg, (10, 52 + i * 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
