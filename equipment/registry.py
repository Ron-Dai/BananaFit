# Gym-equipment metadata, keyed by tag. Data-driven so new equipment doesn't
# require new code paths (mirrors exercises/registry.py).
EQUIPMENT = {
    'bench': {
        'label': 'Weight Bench',
        'muscles': ['chest', 'shoulders', 'triceps'],
        'description': 'Flat/incline bench for presses and supported exercises',
    },
    'medicine_ball': {
        'label': 'Medicine Ball',
        'muscles': ['core', 'shoulders'],
        'description': 'Weighted ball for slams, throws, and rotational core work',
    },
    'unknown': {
        'label': 'Unknown Equipment',
        'muscles': [],
        'description': 'No recognized equipment in frame',
    },

    # Open-vocabulary tags recognized directly by equipment/yolo_recognizer.py
    # (YOLO-World) — the tag IS the class name passed to set_classes(), so no
    # proxy mapping like DETECTOR_CLASS_TO_TAG below is needed for these.
    'dumbbell': {
        'label': 'Dumbbell',
        'muscles': ['full body'],
        'description': 'Free weight for unilateral and compound movements',
    },
    'barbell': {
        'label': 'Barbell',
        'muscles': ['full body'],
        'description': 'Loaded bar for heavy compound lifts (squat, bench, deadlift)',
    },
    'squat rack': {
        'label': 'Squat Rack',
        'muscles': ['legs', 'glutes', 'core'],
        'description': 'Rack for barbell squats and overhead presses',
    },
    'cable machine': {
        'label': 'Cable Machine',
        'muscles': ['back', 'arms', 'shoulders'],
        'description': 'Pulley system for controlled-resistance isolation and compound moves',
    },
    'treadmill': {
        'label': 'Treadmill',
        'muscles': ['cardio', 'legs'],
        'description': 'Motorized belt for walking/running cardio',
    },
    'kettlebell': {
        'label': 'Kettlebell',
        'muscles': ['full body', 'core'],
        'description': 'Ballistic free weight for swings, cleans, and presses',
    },
    'smith machine': {
        'label': 'Smith Machine',
        'muscles': ['legs', 'chest', 'shoulders'],
        'description': 'Guided-bar rack for fixed vertical-path lifts',
    },
    'leg press machine': {
        'label': 'Leg Press Machine',
        'muscles': ['legs', 'glutes'],
        'description': 'Seated sled machine for pressing weight with the legs',
    },
    'pull-up bar': {
        'label': 'Pull-Up Bar',
        'muscles': ['back', 'biceps'],
        'description': 'Overhead bar for bodyweight pulling exercises',
    },
    'rowing machine': {
        'label': 'Rowing Machine',
        'muscles': ['back', 'legs', 'cardio'],
        'description': 'Full-body cardio machine simulating a rowing stroke',
    },
    'exercise bike': {
        'label': 'Exercise Bike',
        'muscles': ['legs', 'cardio'],
        'description': 'Stationary bike for cardio and leg endurance',
    },
    'resistance band': {
        'label': 'Resistance Band',
        'muscles': ['full body'],
        'description': 'Elastic band for variable-resistance accessory work',
    },
    'battle rope': {
        'label': 'Battle Rope',
        'muscles': ['shoulders', 'core', 'cardio'],
        'description': 'Heavy rope for high-intensity conditioning waves',
    },
}

# Open-vocabulary class prompts for equipment/yolo_recognizer.py's YOLO-World
# model. These strings double as EQUIPMENT keys above — YOLO-World's output
# labels are exactly what's passed to set_classes(), so unlike
# DETECTOR_CLASS_TO_TAG below, no proxy mapping is needed.
YOLO_WORLD_CLASSES = [
    'dumbbell', 'barbell', 'bench', 'squat rack', 'cable machine',
    'treadmill', 'kettlebell', 'smith machine', 'leg press machine',
    'pull-up bar', 'rowing machine', 'exercise bike', 'resistance band',
    'battle rope',
]

# Maps a detector class name to an EQUIPMENT tag. The backend in
# equipment/recognizer.py is a COCO-trained general object detector, and COCO
# has no gym-equipment categories — these are the only COCO classes with any
# real-world correspondence to gym equipment, and the mapping is a coarse
# proxy (e.g. 'bench' in COCO means a park bench, not a weight bench). Every
# other COCO class, and anything this dict doesn't list, resolves to
# 'unknown'. Replace this mapping wholesale once a model trained on actual
# gym equipment exists.
DETECTOR_CLASS_TO_TAG = {
    'bench': 'bench',
    'sports ball': 'medicine_ball',
}
