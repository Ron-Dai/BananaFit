"""Explicitly paid, opt-in DeepSeek demonstration using fictional data only."""

import argparse
import os
from pathlib import Path

from sexybanana_intake import Consent, DeepSeekConfig, DeepSeekProvider, FitnessIntakeService
from common import fictional_answers


def load_component_env() -> None:
    """Load an optional local override without replacing host environment values."""
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("DEEPSEEK_"):
            os.environ.setdefault(key, value.strip().strip("'\""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Explicitly authorize paid DeepSeek calls with this fictional profile.",
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("No request sent. Pass --live to enable paid calls explicitly.")
    load_component_env()
    service = FitnessIntakeService(provider=DeepSeekProvider(DeepSeekConfig.from_env()))
    session = service.create_session(consent=Consent(external_ai=True))
    turn = service.submit_message(
        session.session_id, "I am 32 years old", message_sections=["profile"]
    )
    print("Candidates require confirmation:", list(turn.pending))
    # This demo confirms only the exact fictional age supplied, never arbitrary model candidates.
    if "profile.age" in turn.pending and turn.pending["profile.age"]["answer"].get("value") == 32:
        service.confirm_candidates(session.session_id, ["profile.age"])
    else:
        service.confirm_candidates(session.session_id, list(turn.pending), accept=False)
    answers = fictional_answers()
    if service.get_session(session.session_id).responses["profile"]["age"].status == "answered":
        answers.pop("profile.age")
    service.submit_answers(session.session_id, answers)
    result = service.generate_plan(session.session_id)
    print("Planning status:", result.status)
    if result.plan:
        print(service.render_plan_markdown(result.plan))


if __name__ == "__main__":
    main()
