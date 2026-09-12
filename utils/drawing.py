import cv2

from pose.analyzer import LM

# Body-only skeleton connections (landmark index pairs). Indices 0-10 are the
# face (nose/eyes/ears/mouth) and are excluded — irrelevant to posture.
_CONNECTIONS = [
    (11,12),(11,13),(13,15),(15,17),(15,19),(15,21),(17,19),
    (12,14),(14,16),(16,18),(16,20),(16,22),(18,20),
    (11,23),(12,24),(23,24),(23,25),(24,26),(25,27),(26,28),
    (27,29),(28,30),(29,31),(30,32),(27,31),(28,32),
]

_FIRST_BODY_LANDMARK = 11
_LIMB_COLOR = (30, 30, 220)      # BGR red
_LIMB_THICKNESS = 5

_ANGLE_JOINTS = {
    'left_elbow':  LM['left_elbow'],
    'right_elbow': LM['right_elbow'],
    'left_knee':   LM['left_knee'],
    'right_knee':  LM['right_knee'],
}


def draw_skeleton(frame, landmarks, color=_LIMB_COLOR):
    """Draw the body skeleton (no face points) with a uniform bone/joint colour."""
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
                 color, _LIMB_THICKNESS)
    for i, lm in enumerate(landmarks):
        if i < _FIRST_BODY_LANDMARK:
            continue
        if lm[3] >= 0.5:
            cv2.circle(frame, (int(lm[0]), int(lm[1])), 4, color, -1)


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
    """Generic coaching panel for non-curl exercises."""
    w = frame.shape[1]
    panel_h = 30 + len(feedback_messages[:3]) * 28
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, exercise_name.replace('_', ' ').title(),
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 255), 2)
    for i, msg in enumerate(feedback_messages[:3]):
        good = 'good' in msg.lower() or 'keep' in msg.lower()
        cv2.putText(frame, msg, (10, 52 + i * 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                    (60, 220, 60) if good else (30, 120, 255), 2)


def draw_curl_hud(frame, rep_count, last_score, warnings, is_good_form):
    """Specialized HUD for bicep curl: rep counter, form score, warnings."""
    h, w = frame.shape[:2]

    # ── Top-left panel: title + stats ──────────────────────────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (310, 120), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    cv2.putText(frame, 'BICEP CURL', (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 210, 255), 2)

    # Rep counter
    cv2.putText(frame, 'REPS', (10, 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)
    cv2.putText(frame, str(rep_count), (65, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 255, 255), 3)

    # Last rep score
    if last_score is not None:
        if last_score >= 80:
            score_color = (40, 210, 40)
        elif last_score >= 60:
            score_color = (40, 180, 255)
        else:
            score_color = (40, 40, 220)
        cv2.putText(frame, 'LAST', (175, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)
        cv2.putText(frame, f'{last_score}%', (170, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.6, score_color, 3)

    # ── Top-right badge: form status ───────────────────────────────────────────
    form_label = 'GOOD FORM' if is_good_form else 'FIX FORM'
    form_color = (40, 210, 40) if is_good_form else (40, 40, 220)
    badge_w = 190
    overlay2 = frame.copy()
    cv2.rectangle(overlay2, (w - badge_w - 10, 5), (w - 5, 48), (0, 0, 0), -1)
    cv2.addWeighted(overlay2, 0.6, frame, 0.4, 0, frame)
    # Coloured left-edge indicator bar
    cv2.rectangle(frame, (w - badge_w - 10, 5), (w - badge_w - 3, 48), form_color, -1)
    cv2.putText(frame, form_label, (w - badge_w + 4, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, form_color, 2)

    # ── Bottom bar: warnings ────────────────────────────────────────────────────
    if warnings:
        n = min(len(warnings), 2)
        bar_top = h - 15 - n * 38
        overlay3 = frame.copy()
        cv2.rectangle(overlay3, (0, bar_top - 8), (w, h), (0, 0, 40), -1)
        cv2.addWeighted(overlay3, 0.65, frame, 0.35, 0, frame)
        for i, msg in enumerate(warnings[:2]):
            cv2.putText(frame, f'⚠  {msg}',
                        (14, bar_top + i * 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (40, 80, 255), 2)
