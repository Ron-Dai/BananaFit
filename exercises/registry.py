"""Static exercise metadata (muscles worked, description, key joints to track).

Each entry is data-driven so new exercises don't require new code paths for
metadata — but note that rep-counting/form-scoring for a new exercise still
needs its own exercises/base.py ExerciseTracker subclass (see
exercises/curl_tracker.py's CurlTracker for the pattern).
"""

EXERCISES = {
    'squat': {
        'muscles': ['quadriceps', 'hamstrings', 'glutes', 'core'],
        'description': 'Compound lower-body movement',
        'key_joints': ['left_knee', 'right_knee', 'left_hip', 'right_hip'],
    },
    'bicep_curl': {
        'muscles': ['biceps', 'forearms'],
        'description': 'Isolation curl for the biceps',
        'key_joints': ['left_elbow', 'right_elbow'],
    },
    'pushup': {
        'muscles': ['chest', 'triceps', 'anterior deltoid', 'core'],
        'description': 'Compound upper-body push',
        'key_joints': ['left_elbow', 'right_elbow', 'left_shoulder', 'right_shoulder'],
    },
    'unknown': {
        'muscles': [],
        'description': 'No exercise detected',
        'key_joints': [],
    },
}
