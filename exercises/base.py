"""Abstract interface all per-exercise rep-tracking backends must implement."""

from abc import ABC, abstractmethod


class ExerciseTracker(ABC):
    """Contract for a per-exercise, per-frame rep/form tracker.

    exercises/curl_tracker.py's CurlTracker is the only implementation today.
    CLAUDE.md describes its per-arm phase state machine as "the pattern to
    follow when adding rep-counting/form-scoring for other exercises" (e.g.
    a future SquatTracker, PushupTracker) — this class makes that contract
    concrete instead of only descriptive, so main.py/server.py's pipeline
    (pipeline.py's process_frame) and utils/drawing.py's draw_curl_hud-style
    HUD renderers can drive any exercise tracker interchangeably.
    """

    @abstractmethod
    def update(self, landmarks, angles):
        """Advance tracker state from one frame's landmarks and joint angles.

        `landmarks` is the (33, 4) array from pose/detector.py's
        PoseDetector.get_landmarks() (or None if no person was detected);
        `angles` is the dict from pose/analyzer.py's compute_key_angles().
        Must update rep_count/last_rep_score/warnings/is_good_form for this
        frame; called once per frame before those properties are read.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def rep_count(self):
        """Total completed reps so far — what a HUD's rep counter displays."""
        raise NotImplementedError

    @property
    @abstractmethod
    def last_rep_score(self):
        """Form score (0-100) of the most recently completed rep, or None if none yet."""
        raise NotImplementedError

    @property
    @abstractmethod
    def warnings(self):
        """Active form-warning messages for the current frame (empty list if none)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_good_form(self):
        """True if the current frame shows no active form warnings."""
        raise NotImplementedError

    @abstractmethod
    def get_color(self):
        """BGR colour reflecting current form status.

        utils/drawing.py's draw_skeleton() accepts an optional `color`
        override for exactly this; pipeline.py doesn't currently pass one
        (the skeleton renders a fixed colour), but this stays part of the
        contract so a HUD can opt back into form-based skeleton colouring.
        """
        raise NotImplementedError
