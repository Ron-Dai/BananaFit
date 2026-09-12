"""Bounded activity vocabulary with explicit equipment and functional requirements."""

CATALOG = {
    "walk": {
        "name": "Comfortable level walking",
        "equipment": [],
        "functions": ["walk", "standing", "breathing_daily"],
        "category": "aerobic",
        "instructions": "Use a familiar level route. Keep a pace that allows comfortable conversation; slow down or stop if symptoms appear.",
    },
    "sit_to_stand": {
        "name": "Chair sit-to-stand",
        "equipment": ["chair"],
        "functions": ["sit_stand", "standing", "breathing_daily"],
        "category": "strength",
        "instructions": "Use a stable chair on a non-slip surface. Stand and sit within your already comfortable range, breathing continuously.",
    },
    "wall_pushup": {
        "name": "Wall push-up",
        "equipment": ["wall"],
        "functions": ["push_pull", "standing", "breathing_daily"],
        "category": "strength",
        "instructions": "Place hands on a stable wall and use a comfortable stance. Bend and straighten the arms without straining or holding your breath.",
    },
    "stationary_cycle": {
        "name": "Easy stationary cycling",
        "equipment": ["stationary bike"],
        "functions": ["device_transfer", "breathing_daily"],
        "category": "aerobic",
        "instructions": "Use a familiar fitted stationary bike at comfortable resistance. Maintain easy conversation and stop if symptoms arise.",
    },
    "seated_march": {
        "name": "Gentle seated marching",
        "equipment": ["chair"],
        "functions": ["sit_stand", "breathing_daily"],
        "category": "aerobic",
        "instructions": "Sit on a stable chair. Alternate small comfortable foot lifts; use only an already tolerated range.",
    },
    "band_row": {
        "name": "Light resistance-band row",
        "equipment": ["resistance band"],
        "functions": ["grip_carry", "push_pull", "standing", "breathing_daily"],
        "category": "strength",
        "instructions": "Use an intact band and a secure setup you already know. Pull smoothly without pain, breath-holding, or straining; use familiar comfortable resistance.",
    },
    "curl": {
        "name": "Comfortable dumbbell curl",
        "equipment": ["dumbbells"],
        "functions": ["grip_carry", "standing", "breathing_daily"],
        "category": "strength",
        "instructions": "Use a familiar comfortable load, keep the upper arms steady, and move without pain or straining. No maximum-load test is needed.",
    },
}


def equipment_from_text(text: str) -> set[str]:
    """Recognize explicit positive equipment inventory; reject ambiguous negated entries."""
    import re

    result = set()
    # Treat each comma/semicolon/newline phrase independently; do not turn 'no bike' into access.
    for phrase in re.split(r"[,;\n]", text.lower()):
        if re.search(r"\b(no|without|not|avoid|unavailable|cannot)\b", phrase):
            continue
        for item in {e for activity in CATALOG.values() for e in activity["equipment"]}:
            if re.search(r"\b" + re.escape(item) + r"\b", phrase):
                result.add(item)
    return result


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def weekday_availability(text: str) -> list[int] | None:
    """Parse explicit positive weekday availability; ask for clarification on negated schedules."""
    import re

    cleaned = text.lower().strip().rstrip(".")
    if cleaned in {
        "any",
        "any day",
        "every day",
        "all days",
        "flexible",
        "no preference",
        "no preferences",
        "none",
    }:
        return list(range(7))
    if re.search(r"\b(no|not|except|excluding|avoid|unavailable|cannot|can't)\b", cleaned):
        return None
    if "weekends" in cleaned or cleaned == "weekend":
        return [5, 6]
    if "weekdays" in cleaned:
        return list(range(5))
    days = [i for i, name in enumerate(WEEKDAYS) if re.search(r"\b" + name + r"s?\b", cleaned)]
    return days or None


def excluded_activities(text: str) -> set[str]:
    """Honor explicit supported exercise exclusions; broader wording stays in model context."""
    import re

    excluded = set()
    aliases = {
        "walk": ["walk", "walking"],
        "sit_to_stand": ["sit-to-stand", "sit to stand", "squat"],
        "wall_pushup": ["pushup", "push-up", "push up", "pushing"],
        "stationary_cycle": ["cycling", "bike"],
        "seated_march": ["march"],
        "band_row": ["row", "rowing", "pulling"],
        "curl": ["curl"],
    }
    for phrase in re.split(r"[,;.!\n]", text.lower()):
        if not re.search(r"\b(avoid|no|not|dislike|hate|cannot|can't|don't)\b", phrase):
            continue
        for activity, words in aliases.items():
            if any(re.search(r"\b" + re.escape(word) + r"s?\b", phrase) for word in words):
                excluded.add(activity)
        if "standing" in phrase:
            excluded.update(key for key, item in CATALOG.items() if "standing" in item["functions"])
    return excluded
