"""Run a fictional intake, correction, persistence, and fourteen-day plan without networking."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from sexybanana_intake import FakeProvider, FitnessIntakeService, SQLiteStore
from common import answered, fictional_answers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Optionally save the English Markdown plan here."
    )
    args = parser.parse_args()
    with TemporaryDirectory() as directory:
        database = Path(directory) / "demo.sqlite"
        provider = FakeProvider(
            [
                {
                    "candidates": [
                        {
                            "path": "profile.age",
                            "answer": {"status": "answered", "value": 32},
                            "evidence_quote": "I am 32 years old",
                        }
                    ],
                    "clarifications": [],
                }
            ]
        )
        service = FitnessIntakeService(provider=provider, store=SQLiteStore(database))
        session = service.create_session()
        print(service.privacy_notice())
        print("FICTIONAL OFFLINE DEMONSTRATION — no external model was called.")
        for question in service.get_next_questions(session.session_id):
            print(question.text)
        turn = service.submit_message(
            session.session_id, "I am 32 years old", request_id="demo-age"
        )
        service.confirm_candidates(session.session_id, list(turn.pending))
        answers = fictional_answers()
        answers.pop("profile.age")
        service.submit_answers(session.session_id, answers, request_id="demo-profile")
        service.update_answer(
            session.session_id,
            "goals_and_constraints.session_duration",
            answered(25),
            reason="Fictional participant corrected availability",
        )
        # A new service instance restores the same session from disk.
        restored = FitnessIntakeService(provider=provider, store=SQLiteStore(database))
        result = restored.generate_plan(
            session.session_id, start_date="2026-09-14", timezone="America/New_York"
        )
        print("Planning status:", result.status)
        if result.plan is None:
            raise RuntimeError("The fictional ready profile should produce a validated plan.")
        markdown = restored.render_plan_markdown(result.plan)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(markdown, encoding="utf-8")
            print("Plan saved to", args.output)
        else:
            print(markdown)
        restored.delete_session(session.session_id)


if __name__ == "__main__":
    main()
