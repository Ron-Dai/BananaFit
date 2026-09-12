"""Geometric-heuristic exercise classifier, keyed to exercises/registry.py's EXERCISES.

Not currently wired into main.py/server.py — see CLAUDE.md's Architecture
section for why (a misfire mid-set switched modes and discarded the rep
count). Complements exercises/base.py's ExerciseTracker subclasses: this
answers "which exercise is being performed", trackers answer "how many good
reps of it have happened".
"""

from pose.analyzer import LM


def classify_exercise(landmarks, angles):
    """Rule-based exercise classifier. Returns an EXERCISES registry key."""
    if landmarks is None or not angles:
        return 'unknown'

    lm = landmarks
    avg_shoulder_y = (lm[LM['left_shoulder']][1] + lm[LM['right_shoulder']][1]) / 2
    avg_hip_y      = (lm[LM['left_hip']][1]      + lm[LM['right_hip']][1])      / 2
    avg_wrist_y    = (lm[LM['left_wrist']][1]     + lm[LM['right_wrist']][1])    / 2
    avg_ankle_y    = (lm[LM['left_ankle']][1]     + lm[LM['right_ankle']][1])    / 2

    avg_knee   = (angles.get('left_knee', 180)   + angles.get('right_knee', 180))   / 2
    avg_elbow  = (angles.get('left_elbow', 180)  + angles.get('right_elbow', 180))  / 2

    # Pushup: body roughly horizontal (shoulder ≈ hip height) and elbows working
    body_vertical_span = abs(avg_ankle_y - avg_shoulder_y)
    shoulder_hip_delta = abs(avg_shoulder_y - avg_hip_y)
    if body_vertical_span > 0 and (shoulder_hip_delta / body_vertical_span) < 0.15 and avg_elbow < 160:
        return 'pushup'

    # Squat: standing, knees significantly bent
    if avg_knee < 150 and avg_ankle_y > avg_shoulder_y:
        return 'squat'

    # Bicep curl: wrists above hips, elbows bent
    if avg_wrist_y < avg_hip_y and avg_elbow < 150:
        return 'bicep_curl'

    return 'unknown'
