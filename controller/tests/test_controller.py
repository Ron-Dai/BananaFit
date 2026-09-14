from types import SimpleNamespace

from controller.exercise_bridge import EXERCISE_BRIDGE, present_block
from controller.runtime import CoachMetricsStore


def test_every_plan_exercise_has_an_explicit_bridge():
    assert set(EXERCISE_BRIDGE) == {
        "walk",
        "sit_to_stand",
        "wall_pushup",
        "stationary_cycle",
        "seated_march",
        "band_row",
        "curl",
    }


def test_unknown_library_animation_is_not_fuzzily_substituted():
    block = {
        "exercise_id": "sit_to_stand",
        "name": "Chair sit-to-stand",
        "phase": "main",
        "active_minutes": 2,
        "rest_minutes": 1,
        "sets": 2,
        "repetitions": 8,
        "completion_rule": "repetitions",
    }
    result = present_block(block, {})
    assert result["id"] == "plan-sit_to_stand"
    assert result["gif_url"] is None
    assert result["target_duration_seconds"] == 120


def test_camera_tracker_score_is_clamped_and_exposed():
    store = CoachMetricsStore()
    tracker = SimpleNamespace(
        last_rep_score=104,
        warnings=["elbow"],
        rep_count=3,
        is_good_form=False,
    )
    store.update_from_tracker(tracker)
    snapshot = store.snapshot()
    assert snapshot["form_score"] == 100
    assert snapshot["rep_count"] == 3
    assert snapshot["warnings"] == ["elbow"]
    assert snapshot["stream_active"] is True
    store.set_inactive()
    assert store.snapshot()["stream_active"] is False


def test_camera_score_stays_empty_until_the_tracker_completes_a_rep():
    store = CoachMetricsStore()
    tracker = SimpleNamespace(
        last_rep_score=None,
        warnings=[],
        rep_count=0,
        is_good_form=True,
    )
    store.update_from_tracker(tracker)
    assert store.snapshot()["form_score"] is None

    tracker.last_rep_score = 87
    tracker.rep_count = 1
    store.update_from_tracker(tracker)
    assert store.snapshot()["form_score"] == 87

    tracker.last_rep_score = None
    store.update_from_tracker(tracker)
    assert store.snapshot()["form_score"] == 87
