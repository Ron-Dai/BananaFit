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
}

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
