"""Thread-safe, process-local snapshots emitted by the camera pipelines."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock


@dataclass
class CoachMetrics:
    form_score: int | None = None
    rep_count: int = 0
    last_rep_score: int | None = None
    is_good_form: bool = True
    warnings: tuple[str, ...] = ()
    updated_at: str | None = None
    stream_active: bool = False


class CoachMetricsStore:
    """Keep the latest non-sensitive pose result for frontend polling."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._value = CoachMetrics()

    def update_from_tracker(self, tracker) -> None:
        with self._lock:
            last_score = tracker.last_rep_score
            if last_score is not None:
                score = max(0, min(100, int(last_score)))
            else:
                score = self._value.form_score
            self._value = CoachMetrics(
                form_score=score,
                rep_count=int(tracker.rep_count),
                last_rep_score=last_score,
                is_good_form=bool(tracker.is_good_form),
                warnings=tuple(tracker.warnings),
                updated_at=datetime.now(timezone.utc).isoformat(),
                stream_active=True,
            )

    def set_inactive(self) -> None:
        with self._lock:
            self._value.stream_active = False

    def snapshot(self) -> dict:
        with self._lock:
            result = asdict(self._value)
        result["warnings"] = list(result["warnings"])
        return result
