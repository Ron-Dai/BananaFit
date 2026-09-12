import numpy as np
from pose.analyzer import LM

_DOWN_ANGLE = 150   # elbow angle (deg) — arm considered extended / at bottom
_UP_ANGLE   = 50    # elbow angle (deg) — arm considered fully curled / at top

_MAX_SHOULDER_RISE_PX = 25   # pixels shoulder can rise before "shrug" warning
_MAX_ELBOW_DRIFT_DEG  = 25   # degrees upper-arm can drift before "swing" warning

# Two arms finishing within this many frames are one two-armed rep, not two reps.
# Wide enough to absorb the lag between arms in a simultaneous curl, short enough
# that alternating curls (seconds apart) still count separately.
_REP_MERGE_FRAMES = 5

_MIN_VISIBILITY = 0.5   # below this a landmark is treated as out of frame

_REST_FRAMES = 30   # extended, non-curling frames before an arm counts as at rest
_WAKE_FRAMES = 3    # consecutive bent frames needed to bring a resting arm back


class _ArmTracker:
    """Tracks one arm's rep cycle and form."""

    def __init__(self, side):
        """Set up tracking state for one arm ('left' or 'right')."""
        self._e_key = f'{side}_elbow'
        self._s_idx = LM[f'{side}_shoulder']
        self._e_idx = LM[f'{side}_elbow']
        self._w_idx = LM[f'{side}_wrist']

        self.phase          = 'extended'   # 'extended' | 'active'
        self.last_rep_score = None
        self.rep_scores     = []
        self.rep_completed  = False        # True only on the frame a rep finishes
        self.warnings       = []
        self.is_good_form   = True

        self.in_frame       = False        # all three arm landmarks visible this frame
        self.at_rest        = True         # not counting until a sustained curl wakes it

        self._hit_top       = False
        self._rep_good      = 0
        self._rep_total     = 0
        self._shoulder_y0   = None
        self._arm_dir_base  = None
        self._idle_frames   = 0
        self._bent_frames   = 0

    def _stand_down(self):
        """Stop counting this arm and abandon any rep in progress."""
        self.at_rest       = True
        self.phase         = 'extended'
        self._hit_top      = False
        self._rep_good     = 0
        self._rep_total    = 0
        self._shoulder_y0  = None
        self._arm_dir_base = None
        self._idle_frames  = 0
        self._bent_frames  = 0

    def update(self, landmarks, angles):
        """Advance this arm's rep phase from the current frame and score form if mid-rep."""
        self.warnings      = []
        self.is_good_form  = True
        self.rep_completed = False

        if landmarks is None or self._e_key not in angles:
            self.in_frame = False
            self._stand_down()
            return

        shoulder = landmarks[self._s_idx]
        elbow    = landmarks[self._e_idx]
        wrist    = landmarks[self._w_idx]

        # The elbow angle is shoulder-elbow-wrist, so all three have to be visible for
        # it to mean anything. MediaPipe still reports off-screen joints — it just marks
        # them low-visibility — and using those yields a garbage angle that fakes reps.
        if min(shoulder[3], elbow[3], wrist[3]) < _MIN_VISIBILITY:
            self.in_frame = False
            self._stand_down()
            return

        self.in_frame = True
        angle = angles[self._e_key]
        bent  = angle < _DOWN_ANGLE

        if self.at_rest:
            # Wake only on a sustained bend, so one glitched frame on an arm that is
            # just hanging there (or re-entering frame) cannot start a phantom rep.
            self._bent_frames = self._bent_frames + 1 if bent else 0
            if self._bent_frames < _WAKE_FRAMES:
                return
            self.at_rest = False

        if self.phase == 'extended':
            if bent:
                # Rep started — record baselines
                self._idle_frames  = 0
                self.phase         = 'active'
                self._hit_top      = False
                self._rep_good     = 0
                self._rep_total    = 0
                self._shoulder_y0  = float(shoulder[1])
                arm_vec = elbow[:2] - shoulder[:2]
                self._arm_dir_base = arm_vec / (np.linalg.norm(arm_vec) + 1e-6)
            else:
                self._idle_frames += 1
                if self._idle_frames >= _REST_FRAMES:
                    self._stand_down()

        elif self.phase == 'active':
            if angle < _UP_ANGLE:
                self._hit_top = True

            if angle > _DOWN_ANGLE:
                # Rep complete — score it if the person actually reached the top
                self.phase = 'extended'
                if self._hit_top:
                    score = int(100 * self._rep_good / max(self._rep_total, 1))
                    self.last_rep_score = score
                    self.rep_scores.append(score)
                    self.rep_completed = True
                self._shoulder_y0  = None
                self._arm_dir_base = None
            else:
                # Mid-rep — check form
                self._rep_total += 1
                ok = True

                # 1. Shoulder shrug (y decreases = shoulder rises in image coords)
                if self._shoulder_y0 is not None:
                    if (self._shoulder_y0 - shoulder[1]) > _MAX_SHOULDER_RISE_PX:
                        self.warnings.append('Keep shoulder down — no shrugging')
                        ok = False

                # 2. Elbow / upper-arm swing
                if self._arm_dir_base is not None:
                    arm_vec = elbow[:2] - shoulder[:2]
                    arm_dir = arm_vec / (np.linalg.norm(arm_vec) + 1e-6)
                    cos_val = float(np.clip(np.dot(arm_dir, self._arm_dir_base), -1.0, 1.0))
                    if np.degrees(np.arccos(cos_val)) > _MAX_ELBOW_DRIFT_DEG:
                        self.warnings.append('Elbow swinging — pin it to your side')
                        ok = False

                if ok:
                    self._rep_good += 1

        self.is_good_form = len(self.warnings) == 0

    def get_color(self):
        """BGR skeleton colour reflecting current form status."""
        if not self.is_good_form:
            return (30, 30, 220)    # red   — actively bad form
        if self.phase == 'active':
            return (30, 220, 30)    # green — curling with good form
        return (180, 180, 180)      # grey  — resting


class CurlTracker:
    """Tracks both arms; presents combined state for the HUD."""

    def __init__(self):
        """Create independent trackers for the left and right arms."""
        self._left  = _ArmTracker('left')
        self._right = _ArmTracker('right')

        self.rep_count        = 0
        self._frames_since_rep = _REP_MERGE_FRAMES

    def update(self, landmarks, angles):
        """Update both arms, counting a simultaneous two-arm curl as a single rep."""
        self._left.update(landmarks, angles)
        self._right.update(landmarks, angles)

        self._frames_since_rep += 1
        if self._left.rep_completed or self._right.rep_completed:
            if self._frames_since_rep >= _REP_MERGE_FRAMES:
                self.rep_count += 1
            self._frames_since_rep = 0

    # --- aggregated properties --------------------------------------------------

    @property
    def warnings(self):
        """Deduplicated list of active form warnings from both arms."""
        seen, out = set(), []
        for w in self._left.warnings + self._right.warnings:
            if w not in seen:
                seen.add(w)
                out.append(w)
        return out

    @property
    def is_good_form(self):
        """True only if both arms currently have good form."""
        return self._left.is_good_form and self._right.is_good_form

    @property
    def last_rep_score(self):
        """Score of the most recently completed rep (either arm)."""
        candidates = []
        if self._left.rep_scores:
            candidates.append((len(self._left.rep_scores), self._left.last_rep_score))
        if self._right.rep_scores:
            candidates.append((len(self._right.rep_scores), self._right.last_rep_score))
        return max(candidates, key=lambda x: x[0])[1] if candidates else None

    def get_color(self):
        """Skeleton colour: red if either arm has bad form, else the active arm's colour."""
        if not self._left.is_good_form or not self._right.is_good_form:
            return (30, 30, 220)
        # Prefer the arm that's actively in a rep
        for arm in (self._left, self._right):
            if arm.phase == 'active':
                return arm.get_color()
        return (180, 180, 180)
