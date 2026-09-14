"""Explicit bridge between fitness-plan IDs and the checked-in exercise dataset."""

EXERCISE_BRIDGE = {
    "walk": {
        "library_id": None,
        "tracking": "duration",
        "load_label": "No external load",
    },
    "sit_to_stand": {
        "library_id": None,
        "tracking": "repetitions",
        "load_label": "Bodyweight",
    },
    "wall_pushup": {
        "library_id": "0659",
        "tracking": "repetitions",
        "load_label": "Bodyweight",
    },
    "stationary_cycle": {
        "library_id": "2138",
        "tracking": "duration",
        "load_label": "No external load",
    },
    "seated_march": {
        "library_id": None,
        "tracking": "duration",
        "load_label": "Bodyweight",
    },
    "band_row": {
        "library_id": "3144",
        "tracking": "repetitions",
        "load_label": "Resistance band",
    },
    "curl": {
        "library_id": "0294",
        "tracking": "repetitions",
        "load_label": "Comfortable dumbbell load",
    },
}


def present_block(block: dict, dataset_by_id: dict[str, dict]) -> dict:
    """Return a stable frontend record without fuzzy runtime matching."""

    exercise_id = block.get("exercise_id")
    bridge = EXERCISE_BRIDGE.get(exercise_id, {})
    library_id = bridge.get("library_id")
    library = dataset_by_id.get(library_id, {}) if library_id else {}
    active_minutes = block.get("active_minutes") or 0
    return {
        "id": library_id or f"plan-{exercise_id}",
        "plan_exercise_id": exercise_id,
        "name": block.get("name") or exercise_id.replace("_", " ").title(),
        "category": library.get("category", "personal"),
        "body_part": library.get("body_part", library.get("category", "personal")),
        "equipment": library.get("equipment") or ", ".join(block.get("equipment") or []) or "none",
        "instructions": library.get("instructions") or {"en": block.get("instructions", "")},
        "secondary_muscles": library.get("secondary_muscles", []),
        "target": library.get("target", "personal plan"),
        "gif_url": library.get("gif_url"),
        "attribution": library.get("attribution", "BananaFit fitness plan"),
        "phase": block.get("phase"),
        "sets": block.get("sets"),
        "repetitions": block.get("repetitions"),
        "active_minutes": active_minutes,
        "target_duration_seconds": round(active_minutes * 60),
        "rest_seconds": round((block.get("rest_minutes") or 0) * 60),
        "rest_seconds_between_sets": block.get("rest_seconds_between_sets"),
        "tempo_seconds_per_rep": block.get("tempo_seconds_per_rep"),
        "rpe": block.get("rpe"),
        "tracking": bridge.get("tracking", "instructions_only"),
        "load_label": bridge.get("load_label", "Not set"),
        "coaching_cues": block.get("coaching_cues", []),
        "completion_rule": block.get("completion_rule"),
    }
