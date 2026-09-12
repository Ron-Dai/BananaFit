"""Deterministic descriptive calculations, never a clinical normal-value library."""

from __future__ import annotations

from typing import Any
from datetime import date

from .models import Answer, Session, now
from .rules import records, rv, usable, value
from .specification import Specification, convert


def comparable(
    left: Answer | None, right: Answer | None, *, same_time: bool = True
) -> tuple[bool, str]:
    """Require documented compatible conditions; do not infer comparability from numbers."""
    if not left or not right or not usable(left) or not usable(right):
        return False, "One or both valid measurements are unavailable."
    lm, rm = left.measurement_metadata, right.measurement_metadata
    if (
        not lm
        or not rm
        or not left.unit
        or left.unit == "unknown"
        or not right.unit
        or right.unit == "unknown"
    ):
        return False, "Measurement units or metadata are unavailable."
    if any(
        m.method == "unknown"
        or m.observed_at == "unknown"
        or m.setting == "unknown"
        or m.quality == "invalid"
        for m in [lm, rm]
    ):
        return False, "Date, method, setting, or quality does not support comparison."
    if lm.date_precision not in {"day"} or rm.date_precision not in {"day"}:
        return False, "Comparison requires day-level observation precision."
    try:
        date.fromisoformat(lm.observed_at[:10])
        date.fromisoformat(rm.observed_at[:10])
    except ValueError:
        return False, "The observation date is not a valid calendar date."
    if not any(v not in (None, "unknown", "") for v in lm.device.values()) or not any(
        v not in (None, "unknown", "") for v in rm.device.values()
    ):
        return False, "The measurement devices have not been documented."
    if (
        lm.method != rm.method
        or lm.device != rm.device
        or lm.setting != rm.setting
        or lm.protocol != rm.protocol
        or lm.context != rm.context
    ):
        return False, "Methods, devices, positions, protocols, or contexts differ."
    if same_time and lm.observed_at[:10] != rm.observed_at[:10]:
        return False, "Measurements are not from the same documented day."
    lc, rc = lm.reference.get("construct"), rm.reference.get("construct")
    if lc != rc:
        return False, "Measurement constructs differ."
    try:
        convert(right.value, right.unit, left.unit)
    except ValueError:
        return False, "Measurement units are incompatible."
    return True, "Comparable under documented conditions; measurement uncertainty still applies."


def result(
    metric: str,
    number: float | None,
    unit: str | None,
    answers: list[Answer],
    formula: str,
    reason: str = "",
) -> dict:
    """Build a traceable derived-result envelope, including unavailable results."""
    return {
        "metric_id": metric,
        "value": number,
        "unit": unit,
        "input_answer_ids": [a.answer_id for a in answers],
        "formula": formula,
        "formula_version": "1.0",
        "computed_at": now(),
        "comparable": number is not None,
        "reason": reason,
        "interpretation": "Descriptive only; not a diagnosis or a training-load estimate.",
    }


def paired_metrics(record: dict) -> list[dict]:
    """Describe paired measurements only when their actual construct and protocol agree."""
    left, right = record.get("left"), record.get("right")
    valid, reason = comparable(left, right)
    construct = rv(record, "construct")
    if not construct or not rv(record, "region_task") or not rv(record, "protocol"):
        valid, reason = (
            False,
            "The paired construct, anatomical task, or common protocol is missing.",
        )
    if left and right and left.measurement_metadata and right.measurement_metadata:
        declared = [
            m.reference.get("construct")
            for m in [left.measurement_metadata, right.measurement_metadata]
        ]
        if any(c and c != construct for c in declared):
            valid, reason = (
                False,
                "The paired label does not match the individual measurement constructs.",
            )
    answers = [a for a in [left, right] if isinstance(a, Answer)]
    signed = absolute = relative = None
    relative_reason = reason
    if valid:
        left_value, right_value = left.value, convert(right.value, right.unit, left.unit)
        signed, absolute = right_value - left_value, abs(right_value - left_value)
        if (
            construct
            in {"grip_strength", "strength", "circumference", "mass", "duration", "force", "torque"}
            and min(left_value, right_value) >= 0
            and max(left_value, right_value) > 0
        ):
            relative = 100 * absolute / max(left_value, right_value)
        else:
            relative_reason = "Relative difference requires a supported true-zero ratio construct and a positive denominator."
    return [
        result(
            "paired_signed_difference",
            signed,
            left.unit if left else None,
            answers,
            "right - left",
            reason,
        ),
        result(
            "paired_absolute_difference",
            absolute,
            left.unit if left else None,
            answers,
            "abs(right - left)",
            reason,
        ),
        result(
            "paired_relative_difference",
            relative,
            "%",
            answers,
            "100 * abs(right - left) / max(left, right)",
            relative_reason,
        ),
    ]


def latest(measurements: list[Answer]) -> Answer | None:
    """Select a latest valid dated observation, never an arbitrary last-entered reading."""
    candidates = []
    for answer in measurements:
        if (
            not usable(answer)
            or not answer.measurement_metadata
            or answer.measurement_metadata.date_precision != "day"
            or not answer.unit
            or answer.unit == "unknown"
        ):
            continue
        try:
            date.fromisoformat(answer.measurement_metadata.observed_at[:10])
        except ValueError:
            continue
        candidates.append(answer)
    return max(candidates, key=lambda a: a.measurement_metadata.observed_at) if candidates else None


def derive(session: Session, spec: Specification) -> list[dict[str, Any]]:
    """Calculate supported metrics using explicit prerequisite checks and answer references."""
    output = []
    height = latest(value(session, "profile.height", []))
    weight = latest(value(session, "profile.weight", []))
    fat = latest(value(session, "body_composition.body_fat_percent", []))

    # Different constructs use different methods, but dates and source context must align.
    def contemporaneous(a: Answer | None, b: Answer | None) -> bool:
        if (
            not a
            or not b
            or not usable(a)
            or not usable(b)
            or not a.measurement_metadata
            or not b.measurement_metadata
        ):
            return False
        try:
            date.fromisoformat(a.measurement_metadata.observed_at[:10])
            date.fromisoformat(b.measurement_metadata.observed_at[:10])
        except ValueError:
            return False
        return bool(
            a.measurement_metadata.date_precision == "day"
            and b.measurement_metadata.date_precision == "day"
            and a.measurement_metadata.observed_at[:10] == b.measurement_metadata.observed_at[:10]
            and a.measurement_metadata.method != "unknown"
            and b.measurement_metadata.method != "unknown"
        )

    if height and weight:
        ok = contemporaneous(height, weight) and height.value > 0 and weight.value > 0
        output.append(
            result(
                "bmi",
                weight.value / (height.value / 100) ** 2 if ok else None,
                "kg/m2",
                [height, weight],
                "weight_kg / (height_cm / 100)^2",
                "Requires valid same-day height and weight; adult reference cutoffs are not applied.",
            )
        )
    if weight and fat:
        ok = (
            contemporaneous(weight, fat)
            and 0 < fat.value < 100
            and weight.source_type == fat.source_type
        )
        fm = weight.value * fat.value / 100 if ok else None
        output.extend(
            [
                result(
                    "fat_mass_from_percent",
                    fm,
                    "kg",
                    [weight, fat],
                    "weight_kg * body_fat_percent / 100",
                    "Derived estimate, not an independent measurement; requires compatible sources.",
                ),
                result(
                    "fat_free_mass_from_percent",
                    weight.value - fm if fm is not None else None,
                    "kg",
                    [weight, fat],
                    "weight_kg - fat_mass_from_percent",
                    "Fat-free mass is not skeletal muscle mass.",
                ),
            ]
        )
    circumferences = records(session, "body_composition.circumferences")
    waist_record = next(
        (
            r
            for r in circumferences
            if str(rv(r, "site", "")).lower() == "waist" and rv(r, "landmark")
        ),
        None,
    )
    hip_record = next(
        (
            r
            for r in circumferences
            if str(rv(r, "site", "")).lower() == "hip" and rv(r, "landmark")
        ),
        None,
    )
    waist = waist_record["value"] if waist_record else None
    hip = hip_record["value"] if hip_record else None
    if waist and hip:
        ok = contemporaneous(waist, hip) and hip.value > 0
        output.append(
            result(
                "waist_hip_ratio",
                waist.value / hip.value if ok else None,
                "ratio",
                [waist, hip],
                "waist_cm / hip_cm",
                "Landmarks and compatible observation dates are required.",
            )
        )
    if waist and height:
        ok = contemporaneous(waist, height) and height.value > 0
        output.append(
            result(
                "waist_height_ratio",
                waist.value / height.value if ok else None,
                "ratio",
                [waist, height],
                "waist_cm / height_cm",
                "No population reference cutoff is applied.",
            )
        )
    for record in records(session, "asymmetry.paired_observations"):
        output.extend(dict(item, record_id=record["record_id"]) for item in paired_metrics(record))
    for path, field, answer in spec.walk(session):
        if field.type != "measurements" or not usable(answer) or len(answer.value) < 2:
            continue
        ordered = sorted(
            (
                a
                for a in answer.value
                if usable(a)
                and a.measurement_metadata
                and a.measurement_metadata.observed_at != "unknown"
            ),
            key=lambda a: a.measurement_metadata.observed_at,
        )
        if len(ordered) >= 2:
            prior, current = ordered[-2:]
            ok, reason = comparable(prior, current, same_time=False)
            number = convert(current.value, current.unit, prior.unit) - prior.value if ok else None
            output.append(
                dict(
                    result(
                        "longitudinal_change",
                        number,
                        prior.unit,
                        [prior, current],
                        "current - prior",
                        reason,
                    ),
                    field_path=path,
                    observed_dates=[
                        prior.measurement_metadata.observed_at,
                        current.measurement_metadata.observed_at,
                    ],
                )
            )
    return output
