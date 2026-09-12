"""Generate the README method/model/field reference directly from the implementation."""

from __future__ import annotations

import ast
from pathlib import Path

from sexybanana_intake import models
from sexybanana_intake.localization import question
from sexybanana_intake.specification import Specification

ROOT = Path(__file__).resolve().parents[1]
MARKER = "<!-- GENERATED_REFERENCE_START -->"


def escape(text: str) -> str:
    """Keep generated table content inside one Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def generate() -> str:
    """Return signatures, responsibilities, model fields, and the complete English field directory."""
    parts = [
        MARKER,
        "## Complete method and model reference",
        "",
        "Generated from the shipped source. Public entry points are stable integration contracts; underscored methods are implementation details. Every callable below is documented here so developers can follow the internal data flow without guessing.",
        "",
    ]
    for path in sorted((ROOT / "src/sexybanana_intake").glob("*.py")):
        tree = ast.parse(path.read_text())
        methods = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append((node.name, node))
            elif isinstance(node, ast.ClassDef):
                methods.extend(
                    (node.name + "." + child.name, child)
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
        if not methods:
            continue
        parts += [f"### `{path.name}`", "", "| Signature | Responsibility |", "| --- | --- |"]
        for name, node in methods:
            signature = name + "(" + ast.unparse(node.args) + ")"
            if node.returns:
                signature += " -> " + ast.unparse(node.returns)
            doc = (
                ast.get_docstring(node) or "Construct or fulfill the documented interface contract."
            )
            parts.append(f"| `{escape(signature)}` | {escape(doc)} |")
        parts.append("")
    parts += [
        "### Pydantic model fields",
        "",
        "All models forbid undeclared fields and nonfinite typed numbers. The domain validator additionally checks dynamic Answer values against the YAML type. `Any` is used only where the DSL determines the actual field type.",
        "",
    ]
    for name, cls in vars(models).items():
        if not isinstance(cls, type) or not issubclass(cls, models.Model) or cls is models.Model:
            continue
        parts += [f"#### `{name}`", "", "| Field | Type | Default |", "| --- | --- | --- |"]
        for key, field in cls.model_fields.items():
            default = (
                "Required"
                if field.is_required()
                else "Generated independently per instance"
                if field.default_factory
                else repr(field.default)
            )
            type_name = (
                str(field.annotation)
                .replace("typing.", "")
                .replace("sexybanana_intake.models.", "")
            )
            parts.append(f"| `{key}` | `{escape(type_name)}` | {escape(default)} |")
        parts.append("")
    spec = Specification()
    parts += [
        "### Complete English intake field directory",
        "",
        "These are presentation prompts for the source DSL. The original YAML retains its original-language labels and notes. System identifiers are listed for integration reference but are never asked as health questions.",
        "",
    ]
    for section, fields in spec.sections.items():
        parts += [
            f"#### `{section}`",
            "",
            "| Path | Type | Unit | English prompt |",
            "| --- | --- | --- | --- |",
        ]
        for key, definition in fields.items():
            path = section + "." + key
            parts.append(
                f"| `{path}` | `{definition.type}` | {definition.unit or 'None'} | {escape(question(spec, path, definition).text)} |"
            )
        parts.append("")
    for name, fields in spec.records.items():
        parts += [
            f"#### Record `{name}`",
            "",
            "Each record has a generated `record_id`; every field below uses an Answer envelope.",
            "",
            "| Field | Type | Unit |",
            "| --- | --- | --- |",
        ]
        for key, definition in fields.items():
            parts.append(f"| `{key}` | `{definition.type}` | {definition.unit or 'None'} |")
        parts.append("")
    parts += [
        "Regenerate this appendix after changing methods, models, or the DSL:",
        "",
        "```bash",
        "python tools/generate_reference.py",
        "```",
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    """Replace only the generated README appendix, preserving the hand-written guide."""
    readme = ROOT / "README.md"
    body = readme.read_text().split(MARKER)[0].rstrip()
    readme.write_text(body + "\n\n" + generate(), encoding="utf-8")


if __name__ == "__main__":
    main()
