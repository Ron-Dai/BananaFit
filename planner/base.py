"""Interface-only package: the workout routine planner / calendar.

README.md and CLAUDE.md both list "plan workout routine based on equipment
scanned and your plan" as a project goal that isn't implemented yet. This
module defines the contract a future implementation should satisfy, so a
calendar/scheduling UI (frontend's "Workout Plan" flow) and a planner
implementation can be built against a stable interface independently.
"""

from abc import ABC, abstractmethod


class WorkoutScheduler(ABC):
    """Contract for a future workout planner. Not implemented anywhere yet."""

    @abstractmethod
    def generate_plan(self, available_equipment, goals):
        """Build a new multi-session workout plan.

        `available_equipment` is a list of equipment tags (see
        equipment/registry.py's EQUIPMENT dict) — typically gathered by
        running an EquipmentDetector.scan() (equipment/base.py) over a gym.
        `goals` is implementation-defined (e.g. target muscle groups,
        sessions per week, experience level).

        Expected to return a dated sequence of sessions, each listing
        exercises drawn from exercises/registry.py's EXERCISES.
        """
        raise NotImplementedError

    @abstractmethod
    def schedule_session(self, date, exercises):
        """Place a specific list of exercises (EXERCISES keys) onto the calendar for `date`."""
        raise NotImplementedError

    @abstractmethod
    def sessions_between(self, start_date, end_date):
        """Return all sessions scheduled within [start_date, end_date].

        This is the query a calendar view (week/month grid) would call to
        render itself.
        """
        raise NotImplementedError
