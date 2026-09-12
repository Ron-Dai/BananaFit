import numpy as np
from pose.analyzer import LM

_DOWN_ANGLE = 160   # elbow angle (deg) — arm considered extended / at bottom
_UP_ANGLE   = 70    # elbow angle (deg) — arm considered fully curled / at top

_MAX_SHOULDER_RISE_PX = 25   # pixels shoulder can rise before "shrug" warning
_MAX_ELBOW_DRIFT_DEG  = 25   # degrees upper-arm can drift before "swing" warning


class _ArmTracker:
    """Tracks one arm's rep cycle and form."""

    def __init__(self, side):
        """Set up tracking state for one arm ('left' or 'right')."""
        self._e_key = f'{side}_elbow'
        self._s_idx = LM[f'{side}_shoulder']
        self._e_idx = LM[f'{side}_elbow']

        self.phase          = 'extended'   # 'extended' | 'active'
        self.rep_count      = 0
        self.last_rep_score = None
        self.rep_scores     = []
        self.warnings       = []
        self.is_good_form   = True

        self._hit_top       = False
        self._rep_good      = 0
        self._rep_total     = 0
        self._shoulder_y0   = None
        self._arm_dir_base  = None

    def update(self, landmarks, angles):
        """Advance this arm's rep phase from the current frame and score form if mid-rep."""
        self.warnings     = []
        self.is_good_form = True

        if landmarks is None or self._e_key not in angles:
            return

        angle    = angles[self._e_key]
        shoulder = landmarks[self._s_idx]
        elbow    = landmarks[self._e_idx]

        # Skip frames where key landmarks are low-confidence
        if shoulder[3] < 0.5 or elbow[3] < 0.5:
            return

        if self.phase == 'extended':
            if angle < _DOWN_ANGLE:
                # Rep started — record baselines
                self.phase         = 'active'
                self._hit_top      = False
                self._rep_good     = 0
                self._rep_total    = 0
                self._shoulder_y0  = float(shoulder[1])
                arm_vec = elbow[:2] - shoulder[:2]
                self._arm_dir_base = arm_vec / (np.linalg.norm(arm_vec) + 1e-6)

        elif self.phase == 'active':
            if angle < _UP_ANGLE:
                self._hit_top = True

            if angle > _DOWN_ANGLE:
                # Rep complete — score it if the person actually reached the top
                self.phase = 'extended'
                if self._hit_top:
                    self.rep_count += 1
                    score = int(100 * self._rep_good / max(self._rep_total, 1))
                    self.last_rep_score = score
                    self.rep_scores.append(score)
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

    def update(self, landmarks, angles):
        """Update both arms' trackers with the current frame's landmarks and angles."""
        self._left.update(landmarks, angles)
        self._right.update(landmarks, angles)

    # --- aggregated properties --------------------------------------------------

    @property
    def rep_count(self):
        """Total completed reps across both arms."""
        return self._left.rep_count + self._right.rep_count

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
