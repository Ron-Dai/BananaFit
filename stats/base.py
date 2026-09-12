"""Interface-only package: progress/history statistics.

Nothing implements this yet. It defines the contract a future persistence
layer should satisfy so the frontend's Progress/History pages (currently
static mock data in frontend/src/main.jsx) have real data to call into, fed
by completed sets from exercises/base.py's ExerciseTracker implementations
(e.g. CurlTracker.rep_count / .last_rep_score per completed rep).
"""

from abc import ABC, abstractmethod


class ProgressTracker(ABC):
    """Contract for a future progress-history store. Not implemented anywhere yet."""

    @abstractmethod
    def log_set(self, exercise, reps, form_score, timestamp=None):
        """Record one completed set.

        `exercise` is an exercises/registry.py EXERCISES key. `reps` and
        `form_score` map directly to what an ExerciseTracker (e.g.
        CurlTracker) already produces per completed rep — `rep_count` and
        `last_rep_score`. `timestamp` defaults to "now" when omitted.
        """
        raise NotImplementedError

    @abstractmethod
    def history(self, exercise, since=None):
        """Return logged sets for `exercise`, optionally only those at/after `since`."""
        raise NotImplementedError

    @abstractmethod
    def summary(self, period='week'):
        """Return aggregate stats (volume, rep count, average form score, ...) for `period`.

        This is what a Progress page's charts would call to render totals.
        """
        raise NotImplementedError
