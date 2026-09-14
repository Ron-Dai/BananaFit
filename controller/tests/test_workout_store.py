from sexybanana_accounts import AccountDatabase, AccountService, AccountSettings

from controller.workouts import WorkoutStore


def test_workout_sessions_are_idempotent_and_owned(tmp_path):
    path = tmp_path / "controller.db"
    database = AccountDatabase(path)
    service = AccountService(AccountSettings(database_path=path), database)
    owner = service.register("owner@example.com", "securepass123")
    other = service.register("other@example.com", "securepass123")

    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO fitness_session_owners VALUES (?,?,?)",
            ("session_1", owner.id, "2026-09-13T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO workout_plans VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "userplan_1",
                owner.id,
                "session_1",
                "fitness_plan_1",
                1,
                "available",
                "{}",
                "2026-09-13T00:00:00+00:00",
                "2026-09-13T00:00:00+00:00",
            ),
        )

    store = WorkoutStore(path)
    day = {"day": 1, "date": "2026-09-13"}
    first = store.start(owner.id, "userplan_1", day)
    second = store.start(owner.id, "userplan_1", day)
    assert first["id"] == second["id"]
    assert store.for_user(owner.id, first["id"])["plan_day"] == 1
    assert store.for_user(other.id, first["id"]) is None
