"""Offline executable tour of all public service methods with fictional information."""

from tempfile import TemporaryDirectory
from pathlib import Path

from common import answered, fictional_answers
from sexybanana_intake import (
    Consent,
    Constraint,
    FakeProvider,
    Feedback,
    FitnessIntakeService,
    SQLiteStore,
)


def main():
    with TemporaryDirectory() as directory:
        service = FitnessIntakeService(FakeProvider(), SQLiteStore(Path(directory) / "demo.sqlite"))
        session = service.create_session(language="en", consent=Consent())
        sid = session.session_id
        assert service.privacy_notice()
        assert len(service.list_sections(sid)) == 17
        assert service.get_next_questions(sid, limit=1)
        service.submit_message(sid, "no", request_id="single-screen-answer")
        answers = fictional_answers()
        answers.pop("immediate_screen.current_chest_discomfort")
        service.submit_answers(sid, answers, request_id="remaining-fictional-answers")
        service.update_answer(sid, "profile.age", answered(33), reason="Fictional correction")
        service.update_consent(sid, Consent(external_ai=False))
        assert service.evaluate_readiness(sid).status == "ready"
        assert service.build_summary(sid)["participant_id"] == session.participant_id

        # Explicit host review of a fictional instruction, not a model-created permission.
        instruction = answered(
            "Fictional professional instruction: comfortable level walking only."
        )
        instruction.source_type = "clinician_report"
        instruction.validation = "source_checked"
        service.update_answer(
            sid,
            "medical_history.professional_restrictions",
            answered(
                [
                    {
                        "original_instruction": instruction,
                        "issuer_role": answered("physiotherapist"),
                        "status_now": answered("Reviewed for this fictional demonstration"),
                    }
                ]
            ),
        )
        record = (
            service.get_session(sid)
            .responses["medical_history"]["professional_restrictions"]
            .value[0]
        )
        service.set_constraints(
            sid,
            [
                Constraint(
                    source_answer_ids=[record["original_instruction"].answer_id],
                    reviewed_by="Fictional reviewer",
                    allowed_exercise_ids=["walk"],
                    max_rpe=3.0,
                    professional_scope=True,
                )
            ],
        )
        result = service.generate_plan(sid)
        assert result.status == "limited" and result.plan
        assert service.render_plan_markdown(result.plan).count("## Day ") == 14
        service.submit_feedback(
            sid,
            Feedback(
                plan_id=result.plan["plan_id"],
                day=7,
                completed=True,
                tolerance="too_hard",
                notes="Fictional request for a gentler second week",
            ),
            request_id="week-one-feedback",
        )
        revision = service.revise_plan(sid, result.plan["plan_id"], completed_through=7)
        assert revision.plan and revision.plan["days"][:7] == result.plan["days"][:7]

        exported = service.export_session(sid)
        second_service = FitnessIntakeService(FakeProvider())
        imported = second_service.import_session(exported)
        assert imported.consent.external_ai is False and imported.constraints == []
        assert all(plan["stale"] for plan in imported.plans)
        second_service.delete_session(imported.session_id)
        service.delete_session(sid)

        # Independent confirmation example with a grounded synthetic extraction.
        extractor = FitnessIntakeService(
            FakeProvider(
                [
                    {
                        "candidates": [
                            {
                                "path": "profile.age",
                                "answer": {"status": "answered", "value": 33},
                                "evidence_quote": "33 years old",
                            }
                        ],
                        "clarifications": [],
                    }
                ]
            )
        )
        extraction_session = extractor.create_session()
        turn = extractor.submit_message(extraction_session.session_id, "I am 33 years old")
        extractor.confirm_candidates(extraction_session.session_id, list(turn.pending))
        assert (
            extractor.get_session(extraction_session.session_id).responses["profile"]["age"].value
            == 33
        )
        extractor.delete_session(extraction_session.session_id)
    print("All public service methods completed successfully with fictional offline data.")


if __name__ == "__main__":
    main()
