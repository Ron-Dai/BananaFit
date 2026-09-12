"""Joint-angle math: the canonical landmark-name -> index map and angle calculations."""

import numpy as np

# MediaPipe Pose landmark indices (0-32)
LM = {
    'left_shoulder':  11, 'right_shoulder': 12,
    'left_elbow':     13, 'right_elbow':    14,
    'left_wrist':     15, 'right_wrist':    16,
    'left_hip':       23, 'right_hip':      24,
    'left_knee':      25, 'right_knee':     26,
    'left_ankle':     27, 'right_ankle':    28,
}


def _angle(a, b, c):
    """Angle in degrees at point b, formed by vectors b->a and b->c."""
    a, b, c = np.array(a[:2]), np.array(b[:2]), np.array(c[:2])
    ba, bc = a - b, c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def compute_key_angles(landmarks):
    """Return dict of joint-name -> angle (degrees). Empty dict if no landmarks."""
    if landmarks is None:
        return {}
    lm = landmarks
    return {
        'left_elbow':   _angle(lm[LM['left_shoulder']],  lm[LM['left_elbow']],   lm[LM['left_wrist']]),
        'right_elbow':  _angle(lm[LM['right_shoulder']], lm[LM['right_elbow']],  lm[LM['right_wrist']]),
        'left_knee':    _angle(lm[LM['left_hip']],       lm[LM['left_knee']],    lm[LM['left_ankle']]),
        'right_knee':   _angle(lm[LM['right_hip']],      lm[LM['right_knee']],   lm[LM['right_ankle']]),
        'left_hip':     _angle(lm[LM['left_shoulder']],  lm[LM['left_hip']],     lm[LM['left_knee']]),
        'right_hip':    _angle(lm[LM['right_shoulder']], lm[LM['right_hip']],    lm[LM['right_knee']]),
    }
