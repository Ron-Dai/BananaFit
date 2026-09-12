"""Safe DSL parsing, recursive answer validation, paths, and reference integrity."""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterator

import yaml
from pydantic import ValidationError

from .errors import IntakeError
from .models import Answer, MeasurementMetadata, Session, identifier, now


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys and use YAML 1.2-style booleans rather than yes/no coercion."""


UniqueLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for char, entries in UniqueLoader.yaml_implicit_resolvers.items():
    UniqueLoader.yaml_implicit_resolvers[char] = [
        x for x in entries if x[0] not in ("tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp")
    ]
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF")
)


def unique_mapping(loader: UniqueLoader, node: Any, deep: bool = False) -> dict:
    """Reject duplicate YAML map entries, including duplicate enum options."""
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("Duplicate YAML mapping key.")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


@dataclass(frozen=True)
class FieldDefinition:
    id: str
    type: str
    source_label: str
    unit: str | None
    source_note: str


# Exact dimensional identities; not physiological reference ranges.
UNIT_FACTORS = {
    "kg": ("mass", 1.0),
    "g": ("mass", 0.001),
    "lb": ("mass", 0.45359237),
    "cm": ("length", 1.0),
    "m": ("length", 100.0),
    "mm": ("length", 0.1),
    "in": ("length", 2.54),
    "L": ("volume", 1.0),
    "mL": ("volume", 0.001),
    "L/s": ("flow", 1.0),
    "L/min": ("flow", 1 / 60),
    "ratio": ("ratio", 1.0),
    "%": ("ratio", 0.01),
}


def convert(value: float, original_unit: str, target_unit: str) -> float:
    """Convert explicitly compatible dimensions; reject unknown conversions."""
    if original_unit == target_unit:
        return value
    left, right = UNIT_FACTORS.get(original_unit), UNIT_FACTORS.get(target_unit)
    if not left or not right or left[0] != right[0]:
        raise ValueError("Unsupported unit conversion; confirm the original unit.")
    return value * left[1] / right[1]


class Specification:
    """Load a bounded, versioned form DSL and validate its recursive answer graph."""

    def __init__(self, path: str | Path | None = None):
        resource = (
            Path(path)
            if path
            else files("sexybanana_intake").joinpath("resources/fitness_intake_spec.yaml")
        )
        try:
            text = resource.read_text(encoding="utf-8")
            if len(text) > 2_000_000:
                raise ValueError("Specification exceeds size limit.")
            self.raw = yaml.load(text, Loader=UniqueLoader)
            # JSON round trip rejects recursive aliases before recursive processing.
            json.dumps(self.raw, allow_nan=False)
            self.sections = {}
            self.records = {}
            for section in self.raw["sections"]:
                if section["id"] in self.sections:
                    raise ValueError("Duplicate section ID.")
                self.sections[section["id"]] = self._fields(section["fields"])
            for name, record in self.raw["records"].items():
                self.records[name] = self._fields(record["fields"])
            self.enums = self.raw["enums"]
            self.matrices = self.raw["matrices"]
            for fields_ in [*self.sections.values(), *self.records.values()]:
                for f in fields_.values():
                    self._validate_type(f.type)
            for matrix in self.matrices.values():
                self._validate_type(matrix["value_type"])
                items = matrix["items"]
                if any(len(x) != 2 for x in items) or len({x[0] for x in items}) != len(items):
                    raise ValueError("Invalid matrix items.")
                self.definition(matrix["positive_followup"])
            for section in self.raw["sections"]:
                self._sources(section.get("source_refs", []))
            for rule in self.raw["interpretation_rules"]["rules"]:
                self._sources(rule["source_refs"])
            for key, prefix, count in [("branching", "B", 12), ("interpretation_rules", "R", 13)]:
                ids = [r["id"] for r in self.raw[key]["rules"]]
                if len(ids) != len(set(ids)) or set(ids) != {
                    f"{prefix}{n:02}" for n in range(1, count + 1)
                }:
                    raise ValueError("Unsupported or duplicate rule IDs.")
            self.id = self.raw["spec"]["id"]
            self.version = str(self.raw["spec"]["version"])
            self._check_record_cycles()
        except (KeyError, TypeError, ValueError, yaml.YAMLError, OSError, RecursionError):
            raise IntakeError(
                "invalid_spec", "The specification is unavailable or invalid."
            ) from None

    @staticmethod
    def _fields(rows: list) -> dict[str, FieldDefinition]:
        """Parse exactly five columns and reject duplicate field IDs."""
        result = {}
        for row in rows:
            if not isinstance(row, list) or len(row) != 5 or row[0] in result:
                raise ValueError("Invalid field definition.")
            result[row[0]] = FieldDefinition(*row)
        return result

    def _sources(self, refs: list[str]) -> None:
        """Validate source citations without treating their URLs as executable actions."""
        if any(ref not in self.raw["sources"] for ref in refs):
            raise ValueError("Unresolved source reference.")

    def _validate_type(self, type_: str) -> None:
        """Resolve primitive and named types in the DSL."""
        if ":" in type_:
            kind, name = type_.split(":", 1)
            container = {
                "enum": self.enums,
                "multi": self.enums,
                "record": self.records,
                "matrix": self.matrices,
            }.get(kind, {})
            if name not in container:
                raise ValueError("Unresolved field type.")
        elif type_ not in {
            "text",
            "bool",
            "integer",
            "number",
            "date",
            "datetime",
            "measurement",
            "measurements",
            "refs",
        }:
            raise ValueError("Unknown field type.")

    def _check_record_cycles(self) -> None:
        """Reject recursive record definitions that would create unbounded forms."""

        def visit(name: str, ancestors: set[str]) -> None:
            if name in ancestors:
                raise ValueError("Recursive record type.")
            for field in self.records[name].values():
                if field.type.startswith("record:"):
                    visit(field.type.split(":")[1], ancestors | {name})

        for name in self.records:
            visit(name, set())

    def definition(self, path: str) -> FieldDefinition:
        """Resolve section.field, matrix item, record ID child, or measurement ID paths."""
        try:
            parts = path.split(".")
            field = self.sections[parts[0]][parts[1]]
            index = 2
            while index < len(parts):
                kind, _, name = field.type.partition(":")
                if kind == "matrix":
                    matrix = self.matrices[name]
                    label = dict(matrix["items"])[parts[index]]
                    field = FieldDefinition(parts[index], matrix["value_type"], label, None, "")
                    index += 1
                elif kind == "record":
                    field = self.records[name][parts[index + 1]]
                    index += 2
                elif kind == "measurements":
                    field = FieldDefinition(
                        field.id, "measurement", field.source_label, field.unit, field.source_note
                    )
                    index += 1
                else:
                    raise KeyError(path)
            return field
        except (KeyError, IndexError):
            raise IntakeError(
                "invalid_path", "The field path does not exist in the specification."
            ) from None

    def blank(self, field: FieldDefinition) -> Answer:
        """Initialize matrix children independently; container status is structural only."""
        if field.type.startswith("matrix:"):
            return Answer(
                status="answered",
                value={
                    key: Answer() for key, _ in self.matrices[field.type.split(":")[1]]["items"]
                },
            )
        return Answer()

    def new_responses(self) -> dict[str, dict[str, Answer]]:
        """Initialize all sections without inventing negative health information."""
        return {
            section: {key: self.blank(field) for key, field in fields_.items()}
            for section, fields_ in self.sections.items()
        }

    def normalize(
        self, field: FieldDefinition, raw: Answer | dict, *, importing: bool = False
    ) -> Answer:
        """Validate a field recursively, retaining invalid evidence without using it."""
        try:
            answer = (
                raw.model_copy(deep=True) if isinstance(raw, Answer) else Answer.model_validate(raw)
            )
        except (ValidationError, TypeError):
            raise IntakeError(
                "invalid_answer",
                "Answer envelopes must follow the documented status/value contract.",
            ) from None
        if answer.status != "answered":
            return answer
        if answer.answered_at is None:
            answer.answered_at = now()
        kind, _, name = field.type.partition(":")
        value = answer.value
        try:
            if kind in {"text", "date", "datetime"} and not isinstance(value, str):
                raise ValueError("A string is required.")
            if kind == "text" and not value.strip():
                raise ValueError("Use a missingness status instead of an empty answer.")
            if kind == "bool" and type(value) is not bool:
                raise ValueError("A literal boolean is required.")
            if kind == "integer" and type(value) is not int:
                raise ValueError("An integer is required.")
            if kind in {"number", "measurement"} and (
                type(value) not in (float, int) or not math.isfinite(value)
            ):
                raise ValueError("A finite number is required.")
            if kind in {"date", "datetime"}:
                if kind == "date" and re.fullmatch(r"\d{4}", value):
                    if not 1 <= int(value) <= 9999:
                        raise ValueError("Invalid year.")
                    answer.date_precision = "year"
                elif kind == "date" and re.fullmatch(r"\d{4}-\d{2}", value):
                    date.fromisoformat(value + "-01")
                    answer.date_precision = "month"
                elif kind == "date":
                    date.fromisoformat(value)
                    answer.date_precision = "day"
                elif datetime.fromisoformat(value).tzinfo is None:
                    answer.date_precision = "unknown"
                    answer.issues.append(
                        "Timezone unknown; do not use as a current screening timestamp."
                    )
            if kind == "enum":
                if value not in self.enums[name]:
                    raise ValueError("Unknown enum option.")
                if value in {"unknown", "not_applicable"}:
                    answer.status, answer.value = value, None
            if kind == "multi":
                if (
                    not isinstance(value, list)
                    or any(type(x) is not str or x not in self.enums[name] for x in value)
                    or len(value) != len(set(value))
                ):
                    raise ValueError("Use unique declared options in a list.")
                if "unknown" in value or "not_applicable" in value:
                    if len(value) != 1:
                        raise ValueError("Missingness cannot be combined with selected options.")
                    answer.status, answer.value = value[0], None
            if kind == "refs" and (
                not isinstance(value, list) or any(type(x) is not str for x in value)
            ):
                raise ValueError("References must be a list of typed identifiers.")
            if kind == "measurement":
                metadata = answer.measurement_metadata
                if metadata is None:
                    metadata = MeasurementMetadata(
                        original_value=value, original_unit=answer.unit or "unknown"
                    )
                    answer.measurement_metadata = metadata
                if metadata.original_value is None:
                    metadata.original_value = value
                if not answer.unit or answer.unit == "unknown":
                    answer.unit = "unknown"
                    answer.issues.append("Unit missing; calculation unavailable.")
                elif field.unit and not importing:
                    answer.value = convert(value, answer.unit, field.unit)
                    answer.unit = field.unit
                elif field.unit and importing and answer.unit != field.unit:
                    raise ValueError("Imported normalized unit does not match the field.")
                if (
                    metadata.quality == "acceptable_per_documented_protocol"
                    and not metadata.quality_reason
                ):
                    metadata.quality = "limited"
                    answer.issues.append("Documented quality evidence is missing.")
                if metadata.quality == "invalid":
                    raise ValueError("Measurement quality is invalid.")
            if kind in {"integer", "number", "measurement"}:
                self._bounds(field, answer.value, answer.unit)
            if kind == "measurements":
                if not isinstance(value, list):
                    raise ValueError("Repeated measurements require an array of Answer objects.")
                child = FieldDefinition(
                    field.id, "measurement", field.source_label, field.unit, field.source_note
                )
                answer.value = [self.normalize(child, x, importing=importing) for x in value]
            if kind == "matrix":
                declared = dict(self.matrices[name]["items"])
                if not isinstance(value, dict) or set(value) - set(declared):
                    raise ValueError("Unknown matrix item.")
                answer.value = {
                    key: self.normalize(
                        FieldDefinition(key, self.matrices[name]["value_type"], label, None, ""),
                        value.get(key, {}),
                        importing=importing,
                    )
                    for key, label in declared.items()
                }
            if kind == "record":
                if not isinstance(value, list):
                    raise ValueError("Records require an array.")
                normalized = []
                for record in value:
                    if not isinstance(record, dict) or set(record) - (
                        set(self.records[name]) | {"record_id"}
                    ):
                        raise ValueError("Unknown record field.")
                    item = {"record_id": record.get("record_id", identifier("record"))}
                    for key, child in self.records[name].items():
                        default = (
                            {"status": "answered", "value": identifier("report")}
                            if name == "report" and key == "report_id"
                            else {}
                        )
                        item[key] = self.normalize(
                            child, record.get(key, default), importing=importing
                        )
                    normalized.append(item)
                answer.value = normalized
        except (ValueError, TypeError, KeyError):
            answer.history.append(
                {"at": now(), "reason": "Invalid input retained as evidence", "raw_value": value}
            )
            answer.status, answer.value, answer.validation = "invalid", None, "invalid"
            answer.issues.append("Value, unit, date, or nested structure requires correction.")
        answer.issues = list(dict.fromkeys(answer.issues))
        return answer

    @staticmethod
    def _bounds(field: FieldDefinition, value: Any, unit: str | None) -> None:
        """Check physical/domain bounds only, never universal clinical normal ranges."""
        nonnegative = {
            "age",
            "height",
            "weight",
            "falls_last_12_months",
            "resting_heart_rate",
            "sleeping_heart_rate",
            "day_average_heart_rate",
            "pulse",
            "systolic",
            "diastolic",
            "days_per_week",
            "session_duration",
            "sleep_hours",
            "sedentary_time",
        }
        if field.id in nonnegative and value < 0:
            raise ValueError("Negative value is not valid for this field.")
        if field.id in {"height", "weight"} and value <= 0:
            raise ValueError("Height and weight must be positive.")
        limits = {
            "days_per_week": (0, 7),
            "sleep_hours": (0, 24),
            "sedentary_time": (0, 24),
            "pain_intensity": (0, 10),
            "fev1_fvc": (0, 1),
        }
        if field.id in limits and not limits[field.id][0] <= value <= limits[field.id][1]:
            raise ValueError("Value is outside the field domain.")
        if (
            field.id in {"body_fat_percent", "resting_spo2"}
            and unit == "%"
            and not 0 <= value <= 100
        ):
            raise ValueError("Percentage is outside physical bounds.")

    def locate(self, session: Session, path: str) -> tuple[dict | list, str | int, FieldDefinition]:
        """Resolve a concrete stable path to its mutable container and definition."""
        field = self.definition(path)
        parts = path.split(".")
        container, key = session.responses[parts[0]], parts[1]
        current = container[key]
        index = 2
        try:
            while index < len(parts):
                value = current.value
                if isinstance(value, dict):
                    container, key = value, parts[index]
                    index += 1
                elif isinstance(value, list) and parts[index].startswith("record_"):
                    container = next(x for x in value if x["record_id"] == parts[index])
                    key = parts[index + 1]
                    index += 2
                elif isinstance(value, list):
                    container = value
                    key = next(i for i, a in enumerate(value) if a.answer_id == parts[index])
                    index += 1
                else:
                    raise KeyError(path)
                current = container[key]
            return container, key, field
        except (KeyError, StopIteration, IndexError, TypeError):
            raise IntakeError(
                "invalid_path", "The referenced record or answer is not in this session."
            ) from None

    def walk(self, session: Session) -> Iterator[tuple[str, FieldDefinition, Answer]]:
        """Yield every current answer, including nested and unasked children."""

        def visit(path: str, field: FieldDefinition, answer: Answer):
            yield path, field, answer
            if answer.status != "answered":
                return
            if field.type.startswith("matrix:"):
                for key, child in answer.value.items():
                    yield from visit(path + "." + key, self.definition(path + "." + key), child)
            elif field.type.startswith("record:"):
                for record in answer.value:
                    for key, child in record.items():
                        if key != "record_id":
                            child_path = path + "." + record["record_id"] + "." + key
                            yield from visit(child_path, self.definition(child_path), child)
            elif field.type == "measurements":
                for child in answer.value:
                    child_path = path + "." + child.answer_id
                    yield from visit(child_path, self.definition(child_path), child)

        for section, fields_ in session.responses.items():
            for key, answer in fields_.items():
                yield from visit(section + "." + key, self.sections[section][key], answer)

    def validate_session(self, session: Session) -> Session:
        """Hydrate imported nested answers and reject version, ID, and reference errors."""
        if (session.spec_id, session.spec_version, session.format_version) != (
            self.id,
            self.version,
            "1.0",
        ) or set(session.responses) != set(self.sections):
            raise IntakeError(
                "incompatible_session",
                "Session and specification versions or sections do not match.",
            )
        for section, fields_ in self.sections.items():
            if set(session.responses[section]) != set(fields_):
                raise IntakeError(
                    "incompatible_session", "Session fields do not match the specification."
                )
            for key, field in fields_.items():
                session.responses[section][key] = self.normalize(
                    field, session.responses[section][key], importing=True
                )
        ids = set()
        refs = []

        def add(id_: str, kind: str):
            if (
                not isinstance(id_, str)
                or not re.fullmatch(kind + r"_[0-9a-f]{32}", id_)
                or id_ in ids
            ):
                raise IntakeError("invalid_identifier", "Identifiers must be unique typed UUIDs.")
            ids.add(id_)

        add(session.session_id, "session")
        add(session.participant_id, "participant")
        for path, field, answer in self.walk(session):
            add(answer.answer_id, "answer")
            refs.extend((ref, "report") for ref in answer.report_refs + answer.attachment_refs)
            refs.extend((ref, "record") for ref in answer.related_record_ids)
            if answer.status == "answered":
                if field.type.startswith("record:"):
                    for record in answer.value:
                        add(record["record_id"], "record")
                if field.id == "report_id":
                    add(answer.value, "report")
                if field.type == "refs":
                    refs.extend(
                        (
                            ref,
                            "report"
                            if field.id
                            in {
                                "report_refs",
                                "imaging_reports",
                                "neurological_tests",
                                "rehabilitation_documents",
                            }
                            else None,
                        )
                        for ref in answer.value
                    )
        for ref, kind in refs:
            if (
                ref in session.broken_references
                and isinstance(session.broken_references[ref], str)
                and session.broken_references[ref].strip()
            ):
                if not ref.startswith(("answer_", "record_", "report_")) or (
                    kind and not ref.startswith(kind + "_")
                ):
                    raise IntakeError(
                        "invalid_reference", "A withdrawn reference has the wrong target type."
                    )
                continue
            if (
                ref not in ids
                or (kind and not ref.startswith(kind + "_"))
                or not ref.startswith(("answer_", "record_", "report_"))
            ):
                raise IntakeError(
                    "invalid_reference",
                    "A reference is missing, has the wrong type, or belongs to another session.",
                )
        return session
