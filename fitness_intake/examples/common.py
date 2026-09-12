"""Explicitly fictional data for documentation and offline demonstrations only."""

from sexybanana_intake import Answer
from sexybanana_intake.rules import SCREEN_FIELDS


def answered(value, **metadata):
    """Construct a fictional user-confirmed answer with optional original metadata."""
    return Answer(
        status="answered",
        value=value,
        source_type="self_report",
        validation="user_confirmed",
        **metadata,
    )


def fictional_answers():
    """Return an explicitly invented adult profile; never use these negatives for a real user."""
    data = {"immediate_screen." + key: answered(False) for key in SCREEN_FIELDS}
    data.update(
        {
            "profile.age": answered(32),
            "medical_history.conditions": answered([]),
            "medical_history.symptoms": answered([]),
            "medical_history.professional_restrictions": answered([]),
            "injury_history.ever_injury_or_surgery": answered(False),
            "injury_history.current_pain_regions": answered([]),
            "function.movement_limits": answered([]),
            "medication_and_exposure.medications": answered([]),
            "nutrition_recovery.delayed_exacerbation": answered(False),
            "nutrition_recovery.orthostatic_intolerance": answered(False),
            "activity_history.current_activities": answered([]),
            "activity_history.training_history": answered(
                "Returning to gentle activity after a sedentary month; familiar with walking and chair transfers."
            ),
            "activity_history.exercise_adverse_history": answered("none"),
            "goals_and_constraints.goals": answered(["health", "strength"]),
            "goals_and_constraints.days_per_week": answered(3),
            "goals_and_constraints.session_duration": answered(20),
            "goals_and_constraints.time_preferences": answered("Monday, Wednesday, Friday"),
            "goals_and_constraints.equipment": answered("chair, wall"),
            "goals_and_constraints.preferences": answered(
                "Prefer familiar gentle activity; no excluded activities."
            ),
            "reports_and_update.unmentioned_factors": answered("none"),
            "body_composition.body_fat_percent": Answer(status="not_measured"),
        }
    )
    for task in [
        "walk",
        "standing",
        "breathing_daily",
        "sit_stand",
        "push_pull",
        "grip_carry",
        "device_transfer",
    ]:
        data["function.activities." + task] = answered("none")
    return data
