# Each entry is data-driven so new exercises don't require new code paths.
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
