# SexyBanana Fitness Intake

An independent Python component for progressive fitness intake, traceable health summaries, and constrained fourteen-day plans. It integrates with a main application through Python methods and does not import OpenCV, MediaPipe, or the existing camera loop.

All new presentation text and documentation are in English. The original Chinese YAML is preserved verbatim as source evidence; its stable English identifiers drive a separate English presentation layer.

**Version:** 0.1.0. **Python:** 3.11 or later. **Initial external provider:** DeepSeek. **Default external processing:** disabled until explicitly authorized. **Networking in ordinary tests:** none.

This is a fitness planning component, not a clinically validated diagnostic or medical-clearance system. It produces conservative introductory plans from an established activity scope. It does not diagnose injuries, prescribe rehabilitation for arbitrary diseases, calculate maximal training loads, or guarantee that all risks have been excluded.

## Installation and first run

From the SexyBanana repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e './components/fitness_intake[dev]'
cd components/fitness_intake
python examples/offline_demo.py
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell. Use standard CPython 3.11+, not a Python environment tied to another application.

The offline demonstration uses explicitly fictional answers. It shows questions, extracts and confirms an age using a fake provider, records a profile, corrects availability, restores the session through a new service instance, generates a validated plan, and deletes its temporary database. It requires no API key and makes no network requests.

To save its English output:

```bash
python examples/offline_demo.py --output sample_plan.md
```

See [the complete fictional sample](examples/sample_plan.md). Never copy the example's negative symptom or medical-history answers into a real user's profile.

To install the component from another project without installing the computer-vision application:

```bash
python -m pip install /absolute/path/to/SexyBanana/components/fitness_intake
```

The package name is `sexybanana-intake`; the import name is `sexybanana_intake`.

## Main-application integration

The service is synchronous and independent of any UI. The host presents questions, authenticates users, authorizes access to sessions, and obtains consent. No public method reads from `input()` or starts a server.

```python
from sexybanana_intake import Answer, FakeProvider, FitnessIntakeService

service = FitnessIntakeService(provider=FakeProvider(), questions_per_turn=1)
session = service.create_session()
session_id = session.session_id

print(service.privacy_notice())
questions = service.get_next_questions(session_id)
print(questions[0].text)

# Fictional demonstration: this answers only the one displayed question.
turn = service.submit_message(session_id, "no", request_id="first-answer")
print(turn.status)

turn = service.submit_answers(
    session_id,
    {
        "profile.age": Answer(
            status="answered", value=32, source_type="self_report", validation="user_confirmed"
        )
    },
    expected_version=turn.version,
    request_id="age-answer",
)
readiness = service.evaluate_readiness(session_id)
print(readiness.status)
print(readiness.missing)

# This partial profile is intentionally insufficient. No fake plan is substituted.
result = service.generate_plan(session_id)
assert result.plan is None
```

For a complete, runnable intake-to-plan flow, use [offline_demo.py](examples/offline_demo.py) with [common.py](examples/common.py). For a wider tour of public methods, use [api_walkthrough.py](examples/api_walkthrough.py).

A normal application flow is:

1. Create a session and display the data-use notice.
2. Get one to three questions and render their types, units, choices, and missingness options.
3. Submit explicit structured answers, or send free text to an authorized model for extraction.
4. Present extracted candidates with their exact supporting quotations and require confirmation or correction.
5. Inspect `TurnResult.status`, flags, and pending questions after every change.
6. Build a summary or inspect readiness without an external model call.
7. Generate a plan only if readiness is `ready` or `limited`.
8. Render the returned plan or serialize the same structure to the application's frontend.
9. Record execution and recovery feedback; revise remaining days or reassess when needed.

The host must immediately display an `emergency` result and its next-step guidance. Do not wait for another model response, complete the questionnaire, or replace the warning with a training recommendation.

For an asynchronous application, move synchronous service calls to an appropriate worker:

```python
import asyncio


# Inside an async handler with an already authorized session_id:
async def next_questions(service, session_id):
    return await asyncio.to_thread(service.get_next_questions, session_id)
```

Do not wrap service calls in `asyncio.run()` inside an existing event loop. Storage uses optimistic concurrency, but this does not replace the host's authentication or session authorization.

## DeepSeek configuration

This development version includes the project owner's explicitly authorized OpenRouter key as a source fallback in `providers.py`. `DeepSeekConfig.from_env()` uses that key together with `deepseek/deepseek-chat` and `https://openrouter.ai/api/v1` when no environment overrides are present. Replace the fallback and rotate the key before a public or production release. Anyone who can read the repository can copy a source-level credential.

From the component directory, the bundled demonstration can be run directly:

```bash
python examples/live_deepseek.py --live
```

Environment variables take priority over every bundled development value, so a deployment can provide its own `DEEPSEEK_API_KEY`, model, and base URL without changing source files. An optional untracked `.env` beside the README may also be loaded by `examples/live_deepseek.py`; it is only an override and is no longer required for the bundled demonstration.

The example refuses to send requests unless `--live` is present. Running it incurs provider charges and sends only its fictional profile. It includes one extraction call and, when successful, one planning call.

Verify the selected model before live deployment using [DeepSeek's API documentation](https://api-docs.deepseek.com/). The base URL identifies an OpenAI-compatible chat endpoint; it does not mean the request is sent to OpenAI. Model names and supported parameters are provider-managed and configurable.

```python
from sexybanana_intake import (
    Consent,
    DeepSeekConfig,
    DeepSeekProvider,
    FitnessIntakeService,
)

provider = DeepSeekProvider(DeepSeekConfig.from_env())
service = FitnessIntakeService(provider=provider)
session = service.create_session(consent=Consent(external_ai=True))
turn = service.submit_message(
    session.session_id,
    "I am 32 years old",
    message_sections=["profile"],
)
print(turn.pending)  # Show this to the user; do not blindly accept model candidates.
```

The host declares `message_sections` for external free text because the component cannot reliably classify all sensitive material before sending it. The host must ensure that declaration accurately covers the submitted content. The model's allowed extraction paths are restricted to those sections. For unrestricted mixed health text, declare every relevant section and obtain the corresponding consent first.

| Configuration | Environment variable | Default or requirement |
| --- | --- | --- |
| `api_key` | `DEEPSEEK_API_KEY` | Bundled authorized development key; stored as Pydantic `SecretStr` |
| `model` | `DEEPSEEK_MODEL` | `deepseek/deepseek-chat` |
| `base_url` | `DEEPSEEK_BASE_URL` | `https://openrouter.ai/api/v1`; HTTPS only |
| `timeout_seconds` | `DEEPSEEK_TIMEOUT_SECONDS` | 45 seconds; must be positive and at most 300 |
| `max_retries` | `DEEPSEEK_MAX_RETRIES` | 2; at most 5 |
| `max_tokens` | `DEEPSEEK_MAX_TOKENS` | 6000; between 256 and 32000 |
| `temperature` | `DEEPSEEK_TEMPERATURE` | `0` by default for reproducible validation |
| `json_mode` | Configuration object only | `True` |
| `backoff_seconds` | Configuration object only | 0.5; exponential backoff capped at 10 seconds |

The adapter sends `POST /chat/completions`, disables redirects and automatic environment-proxy use, and has no tools, file access, or conversation memory. If a custom compatible gateway is configured, confirm that it is authorized to receive the data and credential.

JSON mode uses `response_format={"type": "json_object"}` and explicit JSON instructions. This ensures neither schema compliance nor safe content by itself; the component checks both locally. See [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/).

Authentication and invalid-request failures are not retried. Network errors, timeouts, 408, 429, and server errors have bounded retries. Empty, truncated, malformed, or semantically invalid output is rejected. This version performs no automatic model-driven repair of invalid clinical or plan content; the caller receives an actionable error rather than an unbounded repair loop.

## Public service methods

Full signatures, including defaults and return annotations, appear in the generated reference at the end of this README. The following table explains the contract and side effects.

| Method | Required arguments | Optional arguments and behavior | Returns |
| --- | --- | --- | --- |
| `FitnessIntakeService(...)` | None | `provider=None`, `store=None` uses `MemoryStore`, `spec=None` uses packaged YAML, `questions_per_turn=3`, `screen_max_age_hours=24` | Service |
| `privacy_notice()` | None | Local English data-use notice | `str` |
| `create_session(...)` | None | `consent=None` means no external consent; `language="en"` is the only supported presentation language | `Session` |
| `get_session(session_id)` | Session ID | Isolated, recursively hydrated snapshot; editing it does not save anything | `Session` |
| `list_sections(session_id)` | Session ID | All 17 modules remain accessible; returns counts and field IDs | `list[dict]` |
| `get_next_questions(session_id, ...)` | Session ID | `section=None`, `limit=None` uses configured 1–3 count, `reopen=False`; records displayed paths when they change | `list[Question]` |
| `submit_answers(session_id, answers, ...)` | Session ID and path-to-Answer mapping | `expected_version=None`, `request_id=None`; new repeated observations append; scalar corrections require `update_answer` | `TurnResult` |
| `submit_message(session_id, message, ...)` | Session ID and nonempty text | `message_sections=None`, `expected_version=None`, `request_id=None`; external free text requires declared sections; candidates require confirmation | `TurnResult` |
| `confirm_candidates(session_id, paths, ...)` | Session ID and unique pending paths | `accept=True`, `expected_version=None`; `accept=False` discards the selected proposed values | `TurnResult` |
| `update_answer(session_id, path, answer, ...)` | Session ID, exact path, replacement Answer | `reason="User correction"`, `expected_version=None`, `request_id=None`; preserves history and invalidates dependencies and reviewed constraints | `TurnResult` |
| `update_consent(session_id, consent, ...)` | Session ID and complete replacement Consent | `expected_version=None`; does not assert any new health evidence | `Session` |
| `set_constraints(session_id, constraints, ...)` | Session ID and reviewed Constraint list | `expected_version=None`; host-only interpretation of documented evidence; not available to the model | `Session` |
| `evaluate_readiness(session_id)` | Session ID | Local rule evaluation; no model call or medical-clearance claim | `Readiness` |
| `build_summary(session_id)` | Session ID | Deterministic full output contract and derived metrics; caches the result | `dict` |
| `generate_plan(session_id, ...)` | Session ID | `start_date=None`, `timezone=None`, `expected_version=None`; one candidate call followed by validation | `PlanResult` |
| `submit_feedback(session_id, feedback, ...)` | Session ID and Feedback | `expected_version=None`, `request_id=None`; stores execution, tolerance, notes, and optional answer updates | `TurnResult` |
| `revise_plan(session_id, plan_id, ...)` | Session ID, owned plan ID, `completed_through` | `completed_through` is 0–13; `expected_version=None`; revises the same 14-day period and preserves earlier days | `PlanResult` |
| `render_plan_markdown(plan)` | Previously validated issued plan | Local English rendering; never generates new advice | `str` |
| `export_session(session_id)` | Session ID | Complete sensitive JSON snapshot; caller controls saving and transfer | `str` |
| `import_session(data)` | JSON string or dictionary | Validates version and references; never overwrites existing session ID; resets consent, constraints, pending proposals, and caches | `Session` |
| `delete_session(session_id)` | Session ID | Idempotent removal of all component-managed session data | `None` |

Use `IntakeError.code` and typed result states for application logic. Never parse explanatory English to decide whether to proceed. Input values can become `invalid` answers while retaining original evidence; malformed envelopes and invalid references raise errors and are not committed.

`TurnResult` contains `session_id`, current `version`, readiness `status`, next `questions`, `pending` extractions, `flags`, and an English `message`. Its version includes question-tracking updates and is suitable for the next optimistic write.

`generate_plan` creates a new plan version on each successful call. It has no idempotency key; do not automatically retry it at the application layer without accounting for duplicate paid generation. Answer, message, correction, and feedback submissions support `request_id`. Reusing a request ID with different content raises `idempotency_conflict`; repeating the same request returns current state without applying it twice.

## Answer, record, and measurement contracts

Every health field uses an `Answer`; arbitrary primitives are not sufficient envelopes. `status="answered"` requires a non-null value. Every other status requires `value=None`.

| Status | Meaning |
| --- | --- |
| `answered` | A value was explicitly supplied; validity and source still matter |
| `not_asked` | No answer has been collected |
| `unknown` | The answer is unknown |
| `not_measured` | An applicable measurement has not been taken |
| `declined` | The user declined to supply the information |
| `not_applicable` | The user identified the item as inapplicable |
| `invalid` | Input is retained as evidence but cannot support calculations |

Booleans are literal `True` or `False`. Strings such as `"unknown"`, `"false"`, and empty strings are never silently converted to booleans. A legitimate numerical zero is retained.

Other important Answer fields are:

- `answer_id`: system-assigned typed UUID; stable when that answer is corrected.
- `unit`: normalized unit, or `"unknown"` for a measurement whose unit is missing.
- `original_text`: original evidence, never overwritten by an AI paraphrase.
- `answered_at`: time the answer was supplied or explicitly confirmed, including timezone.
- `observed_at` and `date_precision`: the event or observation time and its precision; not automatically the submission time.
- `source_type`: `self_report`, `clinician_report`, `supervised_measurement`, `home_measurement`, `wearable`, `derived`, `other`, or `unknown`.
- `source_detail`: description of the source, separate from clinical verification.
- `validation`: `unchecked`, `user_confirmed`, `source_checked`, `inconsistent`, or `invalid`.
- `report_refs`, `related_record_ids`, and `attachment_refs`: typed references to evidence inside the same session.
- `note`, `other_text`, and `issues`: additional information, multiple-choice “other” text, and specific quality issues.
- `history`: previous/current values, timestamps, actor, and reasons for changes.

`user_confirmed` means the user accepted the extraction or answer. It does not mean a clinician confirmed the diagnosis. The host alone may record source-checked professional evidence after actually checking it; the model cannot assign that authority.

### Paths and repeated records

Paths begin with `section.field`, never with an unqualified field name:

```text
profile.age
medical_history.condition_screen.diabetes
injury_history.injuries.record_<32 hex characters>.side
profile.weight.answer_<32 hex characters>
```

Use IDs returned by the service, not invented IDs. Record-array values contain dictionaries with a bare `record_id`; each other record field contains an Answer. Repeated measurements are arrays of Answers. Matrix values map each item ID to its own Answer.

```python
from sexybanana_intake import Answer


def reported(value):
    return Answer(
        status="answered", value=value, source_type="self_report", validation="user_confirmed"
    )


# With an existing service and session_id:
service.submit_answers(
    session_id,
    {
        "injury_history.injuries": reported(
            [
                {
                    "event_name": reported("Fictional historical ankle injury"),
                    "onset_date": reported("2018"),
                    "side": reported("left"),
                    "current_function": reported("Describe current function here"),
                    "trajectory": reported("stable"),
                }
            ]
        ),
    },
)
record = service.get_session(session_id).responses["injury_history"]["injuries"].value[0]
service.update_answer(
    session_id,
    f"injury_history.injuries.{record['record_id']}.side",
    reported("right"),
    reason="User corrected the affected side",
)
```

Appending a new record is not a correction of the previous event. Use `submit_answers` to append and a stable nested path with `update_answer` to correct. Replacing or withdrawing an entire array preserves prior evidence in history and records reasons for broken references.

For matrices, submit one item path at a time, or an explicit object of individually answered items. A bare “none” is not expanded into all-negative disease history. Matrix containers use `answered` structurally so all independently `not_asked` child entries are available from session creation; this does not mean the matrix's questions were answered. This is a documented representation extension to the source envelope.

### Measurements and dates

```python
from sexybanana_intake import Answer, MeasurementMetadata

observation = Answer(
    status="answered",
    value=70000,
    unit="g",
    original_text="70,000 g",
    source_type="home_measurement",
    validation="user_confirmed",
    measurement_metadata=MeasurementMetadata(
        original_value=70000,
        original_unit="g",
        observed_at="2026-09-12",
        date_precision="day",
        method="digital scale",
        device={"model": "Fictional scale"},
        setting="At home, same clothing",
        quality="limited",
    ),
)
service.submit_answers(
    session_id,
    {
        "profile.weight": Answer(status="answered", value=[observation]),
    },
)
```

The stored normalized observation is 70 kg; its original 70,000 g remains in metadata. Missing device, method, date, or setting is recorded as unknown. Missing units prevent dependent calculations. A documented protocol-quality claim without a quality reason is downgraded rather than accepted blindly.

Supported exact dimensional conversions include kg/g/lb, cm/m/mm/in, L/mL, L/s/L/min, and ratio/percent. Unlisted units may be preserved when the source field has no target unit, but unsupported conversions fail validation. Equal units do not establish that two measurements represent the same construct.

Date-only values such as `2018`, `2018-04`, and `2018-04-03` retain year, month, or day precision. Month validation may internally check a calendar date, but the stored value never gains a fabricated day. Unknown or approximate dates can use a missingness state with the original wording and precision retained. Timezone-less datetimes are marked as uncertain and cannot establish fresh current screening.

## Intake and planning states

| State | May contain a new plan? | Host behavior |
| --- | --- | --- |
| `ready` | Yes, after candidate validation | Present the scoped introductory plan; do not label it medical clearance |
| `limited` | Yes, within established limits | Display the scope, adaptations, and uncertainties alongside the plan |
| `needs_more_info` | No | Offer the listed voluntary clarifications; preserve the session |
| `needs_review` | No | Display the relevant professional-review recommendation and its reason |
| `emergency` | No | Prioritize immediate local emergency-care guidance; stop ordinary exercise questioning |

The default core questions concern current symptoms, professional restrictions, conditions, symptoms, injuries, current pain, movement limitations, age, delayed exacerbation, orthostatic symptoms, medication instructions, goals, availability, equipment, preferences, existing activity, experience, exercise reactions, and the open-ended “anything else” question.

Body fat, spirometry, photographs, and laboratory testing are not universal entry requirements. The detailed modules stay available through `list_sections` and `get_next_questions(section=...)`. `get_next_questions` skips declined/unknown/unmeasured/inapplicable fields in ordinary progression; the host can explicitly reopen them when the user asks.

Current screening has a configurable 24-hour reconfirmation policy. This is a product freshness policy, not a medical guarantee or guideline threshold. Each individual screening timestamp is checked. Updating one question does not refresh all other answers. An old positive acute-warning answer is not silently cleared by time alone.

Free-text interpretation has limits. Literal answers to a single explicit question can be stored without a model. General language extraction uses the configured provider and confirmation. A narrow local backstop recognizes an explicit English statement of current chest pain, but it is not a comprehensive emergency-language detector. Always include the structured immediate screen and display warnings derived from it, even when the provider is unavailable.

## Rule-to-implementation and test mapping

Branch rules are implemented in `rules.branch_targets`; safety and sufficiency rules are implemented in `rules.evaluate`, with pending emergency candidates handled by `service._readiness`. The raw YAML descriptions are never executed as code.

| Branch | Implemented behavior | Verification |
| --- | --- | --- |
| B01 | Positive condition matrix prioritizes condition details | `test_all_branch_handlers_are_executable` |
| B02 | Reported injury/event prioritizes injury and residual-function records | Same branch test; historical surgery case |
| B03 | Symptoms, pain, or asymmetry prioritize symptom details | Same branch test; acute symptom cases |
| B04 | Differences prioritize descriptive and paired records | Same branch test; paired-metric cases |
| B05 | Medications, supplements, or devices prioritize existing instructions and changes | Same branch test; medication case |
| B06 | Cardiopulmonary or orthostatic information prioritizes current status and restrictions | Same branch test; emergency cases |
| B07 | Delayed exacerbation prioritizes activity/delay/recovery details | Same branch test; PEM case |
| B08 | Functional difficulty prioritizes task, assistance, and tolerated variations | Same branch test; scope checks |
| B09 | Volunteered reproductive/nutritional context opens appropriate optional fields | Same branch test; minor/special-scope tests |
| B10 | Reports prioritize source metadata and confirmation | Same branch test; report/reference tests |
| B11 | Critical unknown/refused information remains visible without repeated pressure | Same branch test; refusal test |
| B12 | Changed data marks dependencies for reassessment | Same branch test; correction/revision tests |

Branching proposes record entry and follow-up; it never fabricates a diagnosis or event just because a matrix option is positive. Existing record children become individually addressable follow-up questions.

| Rule | Implementation outcome | Main test coverage |
| --- | --- | --- |
| R01 | Acute structured warnings preempt plans; pending explicit warnings also interrupt | `test_cases_07_08_acute_warning_interrupts`, free-text and historical regression tests |
| R02 | Current illness, trauma, concerning symptoms, or unresolved positive symptom screens block dependent planning | Acute warning and symptom feedback tests |
| R03 | Conditions/screenings require current context, not a blanket disease-based ban | Historical surgery, branch, and readiness tests |
| R04 | Original restrictions need explicit reviewed scope; expiration does not lift them | Restriction expiry and conflicting-scope tests |
| R05 | Describe comparable differences without pathology thresholds or weaker-side extra volume | Cases 03–05 and correction case |
| R06 | Progressive weakness/function decline requires assessment | Branch and warning regression coverage |
| R07 | PEM-like worsening prevents automatic progression and requests applicable professional scope | Case 09 and plan progression rejection |
| R08 | Medication/special context changes assumptions; no age-only heart-rate zones | Case 10, minor, professional-scope tests |
| R09 | Preserve constructs, sources, methods, and uncertainty | Measurement tests and case 11 |
| R10 | Retain invalid/conflicting data, paired-BP issues, critical report instructions, and broken-link reasons | DSL, regression, and reference tests |
| R11 | Use activity-specific function and reviewed adaptation scopes | Functional checks and professional-scope intersection tests |
| R12 | Changed evidence invalidates summaries, calculations, and issued plans | Case 12 and feedback/revision tests |
| R13 | Check sufficiency per decision; optional measurements do not block all service | Cases 01–02 and partial-intake integration tests |

`rule_states` distinguishes `triggered`, `not_triggered`, and `indeterminate`. Lack of enough evidence to evaluate a rule is not a negative finding. This implementation does not include a universal clinical threshold database or disease-specific clearance algorithm. Unresolved clinical wording may remain a professional-review requirement instead of being automatically interpreted.

## Reviewed constraints and adaptations

The host can enter a `Constraint` after reviewing an existing instruction. This API is not exposed as a model tool. A constraint contains:

```python
Constraint(
    source_answer_ids=[original_instruction_answer_id],
    reviewed_by="Authorized reviewer role or identifier",
    allowed_exercise_ids=["walk"],
    max_rpe=3.0,
    max_session_minutes=15.0,
    max_days_per_week=3,
    professional_scope=True,
    note="Reviewed interpretation, separate from original wording",
)
```

`source_answer_ids` must reference valid current answers in the same session. Professional scope additionally requires an original instruction in a professional-restriction record marked `clinician_report` and `source_checked` by the host. A clinician-sourced age or weight alone cannot authorize a professional activity scope.

When adapting around pain or a movement limitation, also reference the relevant current limitation answer. Multiple constraints always intersect; a later constraint cannot reopen an activity excluded by an earlier one. Conflicts produce an empty or unresolved scope. Changing an answer with `update_answer` clears reviewed interpretations so they cannot silently continue using changed evidence.

The host must authenticate and authorize the reviewer. The library's Python API does not verify professional identity, contact clinicians, or create medical permission.

## Derived metrics and summaries

`build_summary` is local and deterministic. Its output includes every key in the source `output_contract`: participant/version/time, evidence summary, health factors, injury/impairment map, asymmetry summary, constraints, adaptations, goals/resources, flags, missing/conflicting information, follow-ups, planning scope, review needs, and reassessment triggers.

Each fact retains its field path, answer ID, source type, verification state, original text, units, and evidence links. Self-report and source-checked professional evidence remain distinct. Flags include rule ID, severity, supporting answer IDs, field paths, next step, and resolution state.

Derived results contain `metric_id`, `value`, `unit`, `input_answer_ids`, `formula`, `formula_version`, `computed_at`, comparability, and an explanation. Unavailable calculations use null values with reasons; raw answers are never overwritten.

| Metric | Formula | Additional constraints |
| --- | --- | --- |
| BMI | `weight_kg / (height_cm / 100)**2` | Valid dated height/weight, positive values; no automatic adult reference labels |
| Waist/hip | `waist_cm / hip_cm` | Documented landmarks, compatible dates, positive denominator |
| Waist/height | `waist_cm / height_cm` | Compatible dates and positive height |
| Derived fat mass | `weight_kg * body_fat_percent / 100` | Same-day compatible sources; boundary percentages require verification |
| Derived fat-free mass | `weight_kg - derived_fat_mass` | Not skeletal muscle mass |
| Signed paired difference | `right - left` | Matching construct, task, documented methods/devices/conditions, units, and date |
| Absolute paired difference | `abs(right - left)` | Same comparison prerequisites |
| Relative paired difference | `100 * abs(right-left) / max(left,right)` | Supported true-zero construct, nonnegative values, positive denominator |
| Longitudinal change | `current - prior` | Compatible methods, devices, position, protocol, context, and units; dates preserved |

This release uses a conservative same-day policy for paired/contemporaneous comparisons; it may return unavailable where a professional could justify a broader comparison. It does not mix lean soft tissue with skeletal muscle, compare manufacturer scores as physiological quantities, or infer VO₂max, 1RM, training weights, recovery percentage, or clinical diagnosis from these formulas.

## Plan schema and validation

The provider can propose only a small numeric `CandidatePlan` structure. The component attaches trusted names, instructions, evidence, conditions, and warnings after validation. This prevents a model from smuggling new exercise instructions or medical claims into arbitrary narrative fields.

```json
{
  "days": [
    {
      "day": 1,
      "kind": "training",
      "preparation_minutes": 1.0,
      "blocks": [
        {"exercise_id": "walk", "phase": "warmup", "active_minutes": 2.0,
         "rest_minutes": 0.0, "rpe": 1.0},
        {"exercise_id": "walk", "phase": "main", "active_minutes": 10.0,
         "rest_minutes": 1.0, "rpe": 3.0},
        {"exercise_id": "walk", "phase": "cooldown", "active_minutes": 2.0,
         "rest_minutes": 0.0, "rpe": 1.0}
      ]
    }
  ]
}
```

This excerpt illustrates one day only and is intentionally not a complete candidate. A valid candidate must contain ordered Days 1–14, with rest days included. Strength main blocks additionally require `sets` and `repetitions`. Intensity is explicitly RPE 0–10; no heart-rate or external-weight field exists in the candidate schema.

The shipped catalog contains `walk`, `sit_to_stand`, `wall_pushup`, `stationary_cycle`, `seated_march`, `band_row`, and `curl`. Activities require documented equipment and corresponding daily-function answers, or a reviewed professional adaptation scope. Unresolved current pain/limitations prevent unsupported activity selection. This bounded catalog is an introductory implementation, not a complete exercise or rehabilitation library.

The default maximum RPE is 4 and warm-up/cool-down are capped at 2, subject to stricter reviewed limits. These are configurable-in-code product limits for the initial planning scope, not clinical thresholds. No kilogram load is inferred from body measurements. A candidate must fit the user's session time including preparation and rest.

Named weekdays constrain scheduling. Without calendar dates, Day 1 is a relative Monday anchor so weekday preferences remain meaningful; no current date or geographic location is inferred. A supplied ISO start date maps available weekdays to actual dates. Time-of-day wording is retained as context; this component does not book calendar appointments.

Week 2 is conditional on comfortable Week 1 tolerance without new or delayed symptoms. Automatic increases in weekly active minutes or peak RPE are rejected. User feedback can produce a revised plan within the same period; this initial version maintains or reduces the established scope rather than automatically escalating it.

An issued plan contains IDs/versions, source profile version, specification and prompt versions, provider identity, dates/timezone, objectives, source answer IDs, constraints, uncertainties, reassessment instructions, conditionality, review days, and enriched daily blocks. Each block contains display name, equipment, instructions, RPE scale, dose, supported alternatives, and adaptation notes. Renderers must use the returned validated object rather than asking the model to rewrite it.

## Feedback, persistence, and deletion

```python
from sexybanana_intake import Feedback

# With an existing issued plan:
service.submit_feedback(
    session_id,
    Feedback(
        plan_id=plan["plan_id"],
        day=7,
        completed=True,
        tolerance="too_hard",
        notes="Fictional feedback: reduce next week's effort",
    ),
)
revision = service.revise_plan(
    session_id,
    plan["plan_id"],
    completed_through=7,
)
```

Feedback tolerance is `comfortable`, `too_hard`, `symptoms`, or `unknown`. `answer_updates` can carry newly reported structured symptoms or other changed information. Unspecified symptoms create a pending clarification and block replanning. `too_hard` reduces remaining duration/intensity limits. Completed days are preserved verbatim, even when their historical dose exceeds the new limits; the revised plan states the forward validation scope.

`Session.version` tracks all persisted state changes for concurrency. `profile_version` tracks health/planning evidence changes. Health changes invalidate cached summaries and calculations and mark issued plans stale. Historical issued plans remain available, but must not be presented as current recommendations. Provider results can only commit if the session still matches the pre-call version; a concurrent correction, consent update, or deletion prevents stale results from being saved.

```python
from sexybanana_intake import FitnessIntakeService, SQLiteStore

service = FitnessIntakeService(store=SQLiteStore("./private_data/intake.sqlite"))
session = service.create_session()
exported = service.export_session(session.session_id)

# Restore into another store, not over an existing session ID:
restored_service = FitnessIntakeService()
restored = restored_service.import_session(exported)
assert restored.consent.external_ai is False
service.delete_session(session.session_id)
```

`MemoryStore` is isolated and thread-safe but not durable. `SQLiteStore` uses parameterized queries, version comparisons, rollback journaling, secure deletion, file mode 0600, and database compaction on deletion. It stores session-owned answers, histories, plans, and caches together. There are no automatic external health files.

Local SQLite content is not encrypted by this package. Use appropriate host storage protection or implement an encrypted store for deployment. Secure deletion does not erase host backups, snapshots, previously exported files, copies held by the caller, or data already sent to a provider. The host manages those boundaries. Report attachments are references; the library does not fetch or delete externally owned attachment bytes.

JSON imports are limited to 10 MB and must match the supported specification/format versions. Duplicate JSON keys and nonfinite numbers are rejected. Imported consent and reviewed constraints are never trusted automatically; prior plans become stale and must be revalidated. Exporting is a sensitive action; the host must authorize the requester and destination.

## Privacy and model trust boundary

`Consent` defaults to no external processing. Sensitive section IDs are `reproductive_and_hormonal`, `psychosocial_environment`, `medication_and_exposure`, `reports_and_update`, and `laboratory_reports`. Report/attachment extraction also requires `attachments=True`. Consent can be replaced or withdrawn using `update_consent`.

Planning uses a minimized projection of known information, excluding raw reports, attachments, unnecessary identifiers, and unauthorized sensitive sections. Local rules still enforce relevant constraints even when those sections are omitted from external model context. The host is responsible for accurate classification of free-text submissions before transmission.

Authoritative schemas and allowed activity IDs are in the system message; original answers and report text are isolated in a data message. Candidate quotations must exist verbatim in the submitted message. Models cannot assign system IDs, audit history, source authority, or verification states, even inside nested records. User confirmation is still required because matching a quotation does not guarantee a correct interpretation.

Component logs contain provider name, attempt, duration, and a safe error code. They do not log keys, request bodies, full responses, or raw health records. Third-party HTTP logging configured by the host is outside this guarantee and should not record sensitive payloads.

## Errors and troubleshooting

```python
from sexybanana_intake import IntakeError

try:
    result = service.generate_plan(session_id)
except IntakeError as exc:
    application_error = exc.to_dict()
    # {'code': ..., 'message': ..., 'retryable': ...}
```

Business blockers return `Readiness`/`PlanResult`; technical or malformed-input failures raise `IntakeError`.

| Codes | Meaning and action |
| --- | --- |
| `configuration`, `provider_not_configured`, `unsupported_language` | Check constructor arguments, credentials/model configuration, and English-only presentation |
| `consent_required`, `scope_required`, `sensitive_consent_required`, `attachment_consent_required`, `invalid_consent` | Obtain or correct the specific authorization; do not silently enable it |
| `invalid_request`, `invalid_message`, `invalid_answer`, `invalid_path`, `system_field` | Use declared typed fields and envelopes; do not submit system fields |
| `correction_required` | Use `update_answer` instead of silently replacing established data |
| `version_conflict`, `idempotency_conflict` | Reload current state; do not reuse a request ID with changed content |
| `not_found`, `session_exists` | Use the correct owned session/plan or import into an empty store slot |
| `invalid_spec`, `incompatible_session`, `invalid_import`, `invalid_identifier`, `invalid_reference` | Check versions, field definitions, unique typed IDs, and local references |
| `invalid_constraint`, `no_scope` | Supply a supported, evidenced activity scope; do not invent professional permission |
| `authentication`, `provider_request`, `provider_task` | Verify access, endpoint, selected model, supported parameters, and operation |
| `rate_limit`, `timeout`, `network`, `provider_unavailable` | Bounded adapter retries were exhausted; consider retrying later |
| `empty_output`, `truncated_output`, `invalid_output`, `ungrounded_output`, `invalid_plan` | Provider output was not accepted; inspect safe diagnostics and request an explicit new attempt if appropriate |
| `invalid_calendar` | Supply a valid ISO date and IANA timezone |
| `emergency_active` | Handle the warning; use structured corrections only if the recorded information is inaccurate |

A missing body-fat value is not fixed by inserting a population average. Missing permission is not fixed by switching to an external provider silently. A provider failure is not fixed by reporting the offline fake as a real AI result.

## Architecture and extension points

| Module | Responsibility |
| --- | --- |
| `models.py` | Strict public envelopes, statuses, metadata, constraints, candidate shapes, feedback, identifiers |
| `specification.py` | Safe DSL parsing, type/reference resolution, recursive validation, units, paths, graph hydration |
| `localization.py` | English section labels, critical question wording, matrix labels, options, secondary-field presentation |
| `rules.py` | B01–B12 targets, R01–R13 evaluation, freshness, sufficiency, and allowed scope |
| `metrics.py` | Explicit numeric formulas, comparability, time/source prerequisites, traceable derived results |
| `catalog.py` | Bounded exercise vocabulary, functional requirements, equipment inventory interpretation |
| `providers.py` | DeepSeek configuration/transport, versioned extraction/plan prompts, offline fake provider |
| `planning.py` | Weekly schedules, candidate validation, trusted plan enrichment, Markdown rendering |
| `storage.py` | Store protocol, in-memory snapshots, durable SQLite and optimistic writes |
| `service.py` | Public workflow, authorization, confirmation, audit, summary, generation, revisions, import/export/deletion |
| `errors.py` | Stable redacted error contract |

The source YAML remains a DSL, not a JSON Schema. It is packaged under `resources/` using package data, so runtime does not depend on a developer's Downloads directory. Loading rejects unsafe constructors, duplicate keys, unresolved types, duplicate fields/items/rules, and recursive record definitions. Field rows must have exactly five columns. Only the documented rule IDs are supported until new handlers and tests are added.

Compatibility decisions: matrix containers are structural; unknown enum options normalize to missingness; `other_text` and `attachment_refs` are Answer extensions; B10's “unverified” is represented by existing verification/source fields rather than an invented status; system IDs are not health questions; partial dates retain their actual precision. English wording overrides Chinese presentation requirements without translating or replacing original evidence. Secondary optional prompts use readable English identifiers where a specialized wording override is not defined.

To add a model provider, implement `LLMProvider` with `external: bool`, `name: str`, and synchronous `generate(task, data, contract) -> dict`. Support `extract` and `plan`, preserve the system/data boundary, and never claim external networking is local to evade consent. Keep vendor objects out of public return values. Add transport and output-rejection tests.

To add storage, implement `SessionStore.create`, `load`, `save(session, expected_version)`, and `delete`. Reads must return isolated snapshots; save must compare the expected version atomically and must not recreate a deleted session. Preserve all session-owned histories and remove them on deletion.

To add a field, update the versioned specification, type/reference validation as needed, English presentation, decision rules if relevant, and tests. To add a rule, update both the accepted ID registry and executable handler; a YAML sentence alone is not executable logic. To add an exercise, define its equipment, daily-function requirements, trusted instructions, category, validation behavior, and tests. Avoid adding a new activity by merely accepting arbitrary model-generated text.

Question presentation, summaries, and rendering are deterministic in this version. Separate versioned model prompts cover extraction and candidate planning. This choice preserves fixed screening qualifiers and avoids outsourcing arithmetic or rule priority to the model.

## Tests and build verification

From this component directory after installing the development extra:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
python examples/offline_demo.py
python examples/api_walkthrough.py
```

All default tests are offline and use fictional information and synthetic keys. HTTP tests use `httpx.MockTransport`; they do not contact DeepSeek. Tests cover all twelve required YAML behavior cases, all branch handlers, strict data contracts, authorization, injection boundaries, persistence, deletion, concurrency, plan schema/constraints, and revisions. Additional regression tests cover evidence identity, historical symptoms, withdrawn links, and conflicting reviewed scopes.

The live example is opt-in and chargeable. Passing the offline tests does not establish that a real account key is active or that every selected model consistently produces an acceptable plan.

Build outputs are a wheel and source distribution. A wheel smoke test must load the packaged YAML and run a fictional plan outside the source checkout, confirming that resource paths and dependencies are self-contained.

## Current limitations and host responsibilities

- No live UI, account system, medical identity verification, deployment, or connection to the camera loop is included.
- No real DeepSeek key is bundled or tested automatically. The transport is verified with mocks; live-account verification is a separate explicit step.
- No OCR, image diagnosis, automatic attachment download, or arbitrary report parsing is included. Text records and source references are supported.
- The full intake DSL is available, but automated planning is restricted to the shipped introductory catalog and supported reviewed scopes. Disease-specific prescriptions and advanced periodization need additional reviewed implementations.
- Arbitrary clinical free text cannot be completely validated by string rules. The component preserves uncertainty, uses explicit screening and confirmation, and may request review rather than interpret it automatically.
- English localization includes carefully worded critical questions and readable optional field prompts. It is not a validated English translation of a standardized clinical questionnaire.
- Only exact supported unit conversions and conservative comparability rules are implemented; there is no universal normal-value or medication-interaction database.
- No automatic calendar booking, research reuse, external backup deletion, or encryption is provided. The main application owns authentication, access policy, actual consent collection, secure deployment, and provider/account configuration.
- Existing SexyBanana posture-recognition code is preserved. The main application may import this component when it is ready to add an intake flow.

No GitHub push, remote pull request, release, or deployment is needed to use this local component.

<!-- GENERATED_REFERENCE_START -->
## Complete method and model reference

Generated from the shipped source. Public entry points are stable integration contracts; underscored methods are implementation details. Every callable below is documented here so developers can follow the internal data flow without guessing.

### `catalog.py`

| Signature | Responsibility |
| --- | --- |
| `equipment_from_text(text: str) -> set[str]` | Recognize explicit positive equipment inventory; reject ambiguous negated entries. |
| `weekday_availability(text: str) -> list[int] \| None` | Parse explicit positive weekday availability; ask for clarification on negated schedules. |
| `excluded_activities(text: str) -> set[str]` | Honor explicit supported exercise exclusions; broader wording stays in model context. |

### `errors.py`

| Signature | Responsibility |
| --- | --- |
| `IntakeError.__init__(self, code: str, message: str, *, retryable: bool=False)` | Construct or fulfill the documented interface contract. |
| `IntakeError.to_dict(self) -> dict` | Return a JSON-compatible error envelope. |

### `localization.py`

| Signature | Responsibility |
| --- | --- |
| `english_name(identifier: str) -> str` | Humanize stable English DSL names for secondary optional field prompts. |
| `question(spec: Specification, path: str, field: FieldDefinition, reason: str='Optional information relevant to your training.') -> Question` | Build deterministic English questions so a model cannot omit screening qualifiers. |

### `metrics.py`

| Signature | Responsibility |
| --- | --- |
| `comparable(left: Answer \| None, right: Answer \| None, *, same_time: bool=True) -> tuple[bool, str]` | Require documented compatible conditions; do not infer comparability from numbers. |
| `result(metric: str, number: float \| None, unit: str \| None, answers: list[Answer], formula: str, reason: str='') -> dict` | Build a traceable derived-result envelope, including unavailable results. |
| `paired_metrics(record: dict) -> list[dict]` | Describe paired measurements only when their actual construct and protocol agree. |
| `latest(measurements: list[Answer]) -> Answer \| None` | Select a latest valid dated observation, never an arbitrary last-entered reading. |
| `derive(session: Session, spec: Specification) -> list[dict[str, Any]]` | Calculate supported metrics using explicit prerequisite checks and answer references. |

### `models.py`

| Signature | Responsibility |
| --- | --- |
| `now() -> str` | Return an aware UTC timestamp, never a fabricated observation timestamp. |
| `identifier(kind: str) -> str` | Generate a typed UUID identifier. |
| `Answer.check_status(self) -> Answer` | Enforce missingness without converting unknown into a negative answer. |

### `planning.py`

| Signature | Responsibility |
| --- | --- |
| `training_days(session: Session, readiness: Readiness, start_date: str \| None=None) -> list[int]` | Select a feasible repeated weekly schedule from explicit weekday availability. |
| `plan_contract(session: Session, readiness: Readiness, start_date: str \| None, timezone: str \| None) -> dict` | Build the model's bounded schedule contract; reject ambiguous calendar input. |
| `validate_candidate(raw: dict, session: Session, readiness: Readiness, contract: dict) -> CandidatePlan` | Reject invalid shapes, impossible schedules, unsupported activities, or excess loads. |
| `normalize_strength_timing(raw: dict, max_minutes: float \| None=None) -> dict` | Normalize model timing arithmetic without adding exercise or intensity. |
| `finalize(candidate: CandidatePlan, session: Session, readiness: Readiness, provider: str, start_date: str \| None, timezone: str \| None) -> dict` | Attach provenance and trusted instructions to a validated candidate. |
| `render_plan_markdown(plan: dict) -> str` | Render a validated plan without regenerating advice or executing embedded HTML. |

### `providers.py`

| Signature | Responsibility |
| --- | --- |
| `LLMProvider.generate(self, task: str, data: dict, contract: dict) -> dict` | Construct or fulfill the documented interface contract. |
| `DeepSeekConfig.from_env(cls) -> DeepSeekConfig` | Load credentials without reading .env automatically or printing secret values. |
| `DeepSeekProvider.__init__(self, config: DeepSeekConfig, *, transport: httpx.BaseTransport \| None=None, sleeper: Callable[[float], None]=time.sleep)` | Construct or fulfill the documented interface contract. |
| `DeepSeekProvider.generate(self, task: str, data: dict, contract: dict) -> dict` | Call a bounded JSON endpoint with an authoritative contract and isolated user data. |
| `FakeProvider.__init__(self, responses: list[dict] \| None=None)` | Construct or fulfill the documented interface contract. |
| `FakeProvider.generate(self, task: str, data: dict, contract: dict) -> dict` | Replay extraction fixtures or create a bounded offline candidate from the contract. |

### `rules.py`

| Signature | Responsibility |
| --- | --- |
| `usable(answer: Answer) -> bool` | Only current valid answers can support decisions; missingness is never negative. |
| `get(session: Session, path: str) -> Answer` | Read a top-level or matrix answer, returning a nonpersistent unknown placeholder. |
| `value(session: Session, path: str, default: Any=None) -> Any` | Read an answer value only when its status and verification permit use. |
| `records(session: Session, path: str) -> list[dict]` | Return known repeated records without treating an unknown field as an empty answer. |
| `rv(record: dict, key: str, default: Any=None) -> Any` | Read a record child without inferring meaning from missing values. |
| `branch_targets(session: Session) -> dict[str, list[str]]` | Resolve B01-B12 into follow-up targets; never create unreported diagnoses. |
| `evaluate(session: Session, spec: Specification, screen_max_age_hours: float=24) -> Readiness` | Evaluate current facts deterministically; unknown or unsupported scopes remain explicit. |

### `service.py`

| Signature | Responsibility |
| --- | --- |
| `FitnessIntakeService.__init__(self, provider: LLMProvider \| None=None, store: SessionStore \| None=None, spec: Specification \| None=None, *, questions_per_turn: int=3, screen_max_age_hours: float=24)` | Construct or fulfill the documented interface contract. |
| `FitnessIntakeService.create_session(self, *, consent: Consent \| dict \| None=None, language: str='en') -> Session` | Create an empty English session; no health answers or external consent are assumed. |
| `FitnessIntakeService.privacy_notice() -> str` | Return the English data-use notice for the main application's consent flow. |
| `FitnessIntakeService._model(model: type, raw: Any)` | Validate a public typed argument without leaking its contents through exceptions. |
| `FitnessIntakeService._check_consent_sections(consent: Consent) -> None` | Reject undeclared sensitive-section authorization names. |
| `FitnessIntakeService.get_session(self, session_id: str) -> Session` | Return a fully hydrated isolated snapshot, including nested Answer objects. |
| `FitnessIntakeService._read(self, session_id: str, expected_version: int \| None) -> Session` | Load and optionally compare the caller's optimistic concurrency version. |
| `FitnessIntakeService._save(self, session: Session, *, health_changed: bool=False, reason: str='State updated') -> None` | Commit a version atomically and invalidate every dependent result after health changes. |
| `FitnessIntakeService.update_consent(self, session_id: str, consent: Consent \| dict, *, expected_version: int \| None=None) -> Session` | Replace external-processing authorization without implying new health evidence. |
| `FitnessIntakeService.list_sections(self, session_id: str) -> list[dict]` | Return every source module, counts, and English labels regardless of branching. |
| `FitnessIntakeService._readiness(self, session: Session) -> Readiness` | Evaluate both confirmed facts and unresolved explicit emergency candidates. |
| `FitnessIntakeService.evaluate_readiness(self, session_id: str) -> Readiness` | Return decision-specific sufficiency and flags without a model call or medical clearance. |
| `FitnessIntakeService.get_next_questions(self, session_id: str, *, section: str \| None=None, limit: int \| None=None, reopen: bool=False) -> list[Question]` | Return up to three questions; explicitly reopening permits revisiting declined answers. |
| `FitnessIntakeService._turn(self, session_id: str, message: str='') -> TurnResult` | Compose a stable result from current questions, pending candidates, and flags. |
| `FitnessIntakeService._fingerprint(data: Any) -> str` | Hash request content for idempotency without retaining a duplicate raw payload. |
| `FitnessIntakeService._duplicate(self, session: Session, request_id: str \| None, fingerprint: str) -> bool` | Reject reuse of an idempotency key for a different payload. |
| `FitnessIntakeService.submit_answers(self, session_id: str, answers: dict[str, Answer \| dict], *, expected_version: int \| None=None, request_id: str \| None=None) -> TurnResult` | Submit explicit answers; repeated records append, scalar corrections require update_answer. |
| `FitnessIntakeService._apply(self, session: Session, path: str, raw: Answer \| dict, *, replace: bool, reason: str) -> None` | Normalize and audit an answer while preserving stable IDs and unaffected records. |
| `FitnessIntakeService._graph_ids(self, session: Session) -> set[str]` | Collect current evidence IDs for explicit withdrawn-reference tracking. |
| `FitnessIntakeService.update_answer(self, session_id: str, path: str, answer: Answer \| dict, *, reason: str='User correction', expected_version: int \| None=None, request_id: str \| None=None) -> TurnResult` | Replace or withdraw one stable path, preserving historical values and issued plans. |
| `FitnessIntakeService._require_provider(self, session: Session, sections: set[str], *, attachments: bool=False) -> LLMProvider` | Enforce explicit external consent for each sensitive category before dispatch. |
| `FitnessIntakeService.submit_message(self, session_id: str, message: str, *, message_sections: list[str] \| None=None, expected_version: int \| None=None, request_id: str \| None=None) -> TurnResult` | Extract grounded candidates for confirmation; literal single-question answers need no model. |
| `FitnessIntakeService._check_model_authority(data: Any) -> None` | Reject forged source authority or identifiers inside recursive extraction data. |
| `FitnessIntakeService.confirm_candidates(self, session_id: str, paths: list[str], *, accept: bool=True, expected_version: int \| None=None) -> TurnResult` | Explicitly accept or reject selected candidates; acceptance never upgrades source authority. |
| `FitnessIntakeService.set_constraints(self, session_id: str, constraints: list[Constraint \| dict], *, expected_version: int \| None=None) -> Session` | Record host-reviewed scope tied to existing evidence; never let the model call this. |
| `FitnessIntakeService._summary(self, session: Session) -> dict` | Build the full YAML output contract deterministically, preserving evidence and uncertainty. |
| `FitnessIntakeService.build_summary(self, session_id: str) -> dict` | Calculate and persist a traceable summary without sending health data to a model. |
| `FitnessIntakeService._model_plan_context(self, session: Session) -> dict` | Minimize planning context; omit raw attachments and unauthorized sensitive sections. |
| `FitnessIntakeService.generate_plan(self, session_id: str, *, start_date: str \| None=None, timezone: str \| None=None, expected_version: int \| None=None) -> PlanResult` | Generate a bounded candidate once, validate it, and return a 14-day plan or business blocker. |
| `FitnessIntakeService._generate(self, session: Session, *, start_date: str \| None, timezone: str \| None, base_plan: dict \| None=None, completed_through: int=0) -> PlanResult` | Run the shared initial/revision flow; stale snapshots cannot commit provider results. |
| `FitnessIntakeService.submit_feedback(self, session_id: str, feedback: Feedback \| dict, *, expected_version: int \| None=None, request_id: str \| None=None) -> TurnResult` | Record execution feedback; symptoms require explicit clarification before replanning. |
| `FitnessIntakeService.revise_plan(self, session_id: str, plan_id: str, *, completed_through: int, expected_version: int \| None=None) -> PlanResult` | Replan remaining days of the same 14-day period; preserve all earlier executed days. |
| `FitnessIntakeService.render_plan_markdown(plan: dict) -> str` | Render an already issued plan; do not use rendering as a substitute for validation. |
| `FitnessIntakeService.export_session(self, session_id: str) -> str` | Return the complete sensitive JSON snapshot; the host controls its destination. |
| `FitnessIntakeService.import_session(self, data: str \| dict) -> Session` | Restore a validated snapshot into an empty store slot; never grant imported consent. |
| `FitnessIntakeService.delete_session(self, session_id: str) -> None` | Delete all component-managed data for a session; external files/backups are host-owned. |

### `specification.py`

| Signature | Responsibility |
| --- | --- |
| `unique_mapping(loader: UniqueLoader, node: Any, deep: bool=False) -> dict` | Reject duplicate YAML map entries, including duplicate enum options. |
| `convert(value: float, original_unit: str, target_unit: str) -> float` | Convert explicitly compatible dimensions; reject unknown conversions. |
| `Specification.__init__(self, path: str \| Path \| None=None)` | Construct or fulfill the documented interface contract. |
| `Specification._fields(rows: list) -> dict[str, FieldDefinition]` | Parse exactly five columns and reject duplicate field IDs. |
| `Specification._sources(self, refs: list[str]) -> None` | Validate source citations without treating their URLs as executable actions. |
| `Specification._validate_type(self, type_: str) -> None` | Resolve primitive and named types in the DSL. |
| `Specification._check_record_cycles(self) -> None` | Reject recursive record definitions that would create unbounded forms. |
| `Specification.definition(self, path: str) -> FieldDefinition` | Resolve section.field, matrix item, record ID child, or measurement ID paths. |
| `Specification.blank(self, field: FieldDefinition) -> Answer` | Initialize matrix children independently; container status is structural only. |
| `Specification.new_responses(self) -> dict[str, dict[str, Answer]]` | Initialize all sections without inventing negative health information. |
| `Specification.normalize(self, field: FieldDefinition, raw: Answer \| dict, *, importing: bool=False) -> Answer` | Validate a field recursively, retaining invalid evidence without using it. |
| `Specification._bounds(field: FieldDefinition, value: Any, unit: str \| None) -> None` | Check physical/domain bounds only, never universal clinical normal ranges. |
| `Specification.locate(self, session: Session, path: str) -> tuple[dict \| list, str \| int, FieldDefinition]` | Resolve a concrete stable path to its mutable container and definition. |
| `Specification.walk(self, session: Session) -> Iterator[tuple[str, FieldDefinition, Answer]]` | Yield every current answer, including nested and unasked children. |
| `Specification.validate_session(self, session: Session) -> Session` | Hydrate imported nested answers and reject version, ID, and reference errors. |

### `storage.py`

| Signature | Responsibility |
| --- | --- |
| `SessionStore.create(self, session: Session) -> None` | Construct or fulfill the documented interface contract. |
| `SessionStore.load(self, session_id: str) -> Session` | Construct or fulfill the documented interface contract. |
| `SessionStore.save(self, session: Session, expected_version: int) -> None` | Construct or fulfill the documented interface contract. |
| `SessionStore.delete(self, session_id: str) -> None` | Construct or fulfill the documented interface contract. |
| `MemoryStore.__init__(self)` | Construct or fulfill the documented interface contract. |
| `MemoryStore.create(self, session: Session) -> None` | Insert a new session; do not overwrite an existing identifier. |
| `MemoryStore.load(self, session_id: str) -> Session` | Return an isolated snapshot or a redacted not-found error. |
| `MemoryStore.save(self, session: Session, expected_version: int) -> None` | Commit only when the stored version still matches the caller's snapshot. |
| `MemoryStore.delete(self, session_id: str) -> None` | Remove the session, including history, plans, and cached data. |
| `SQLiteStore.__init__(self, path: str \| Path)` | Construct or fulfill the documented interface contract. |
| `SQLiteStore._connect(self) -> sqlite3.Connection` | Open a short-lived connection with secure deletion and rollback journaling. |
| `SQLiteStore.create(self, session: Session) -> None` | Insert a session atomically without replacing existing data. |
| `SQLiteStore.load(self, session_id: str) -> Session` | Read an isolated snapshot from disk. |
| `SQLiteStore.save(self, session: Session, expected_version: int) -> None` | Atomically compare and replace a session version. |
| `SQLiteStore.delete(self, session_id: str) -> None` | Delete all session-owned content and compact the database; external backups are host-owned. |

### Pydantic model fields

All models forbid undeclared fields and nonfinite typed numbers. The domain validator additionally checks dynamic Answer values against the YAML type. `Any` is used only where the DSL determines the actual field type.

#### `MeasurementMetadata`

| Field | Type | Default |
| --- | --- | --- |
| `observed_at` | `<class 'str'>` | 'unknown' |
| `date_precision` | `Literal['day', 'month', 'year', 'approximate', 'unknown']` | 'unknown' |
| `original_value` | `Any` | None |
| `original_unit` | `<class 'str'>` | 'unknown' |
| `method` | `<class 'str'>` | 'unknown' |
| `device` | `dict[str, Any]` | Generated independently per instance |
| `setting` | `str \| dict[str, Any]` | 'unknown' |
| `quality` | `Literal['unknown', 'acceptable_per_documented_protocol', 'limited', 'invalid']` | 'unknown' |
| `assessor` | `<class 'str'>` | 'unknown' |
| `preparation` | `dict[str, Any]` | Generated independently per instance |
| `protocol` | `str \| dict[str, Any]` | 'unknown' |
| `context` | `dict[str, Any]` | Generated independently per instance |
| `estimate` | `dict[str, Any]` | Generated independently per instance |
| `quality_reason` | `<class 'str'>` | '' |
| `reference` | `dict[str, Any]` | Generated independently per instance |

#### `Answer`

| Field | Type | Default |
| --- | --- | --- |
| `answer_id` | `<class 'str'>` | Generated independently per instance |
| `status` | `Literal['answered', 'not_asked', 'unknown', 'not_measured', 'declined', 'not_applicable', 'invalid']` | 'not_asked' |
| `value` | `Any` | None |
| `unit` | `str \| None` | None |
| `original_text` | `str \| None` | None |
| `answered_at` | `str \| None` | None |
| `observed_at` | `str \| None` | None |
| `date_precision` | `Literal['day', 'month', 'year', 'approximate', 'unknown']` | 'unknown' |
| `source_type` | `Literal['self_report', 'clinician_report', 'supervised_measurement', 'home_measurement', 'wearable', 'derived', 'other', 'unknown']` | 'unknown' |
| `source_detail` | `<class 'str'>` | '' |
| `note` | `<class 'str'>` | '' |
| `report_refs` | `list[str]` | Generated independently per instance |
| `related_record_ids` | `list[str]` | Generated independently per instance |
| `history` | `list[dict[str, Any]]` | Generated independently per instance |
| `validation` | `Literal['unchecked', 'user_confirmed', 'source_checked', 'inconsistent', 'invalid']` | 'unchecked' |
| `measurement_metadata` | `MeasurementMetadata \| None` | None |
| `other_text` | `<class 'str'>` | '' |
| `attachment_refs` | `list[str]` | Generated independently per instance |
| `issues` | `list[str]` | Generated independently per instance |

#### `Consent`

| Field | Type | Default |
| --- | --- | --- |
| `external_ai` | `<class 'bool'>` | False |
| `sensitive_sections` | `list[str]` | Generated independently per instance |
| `attachments` | `<class 'bool'>` | False |
| `purpose` | `<class 'str'>` | 'Fitness intake and fourteen-day planning' |
| `recorded_at` | `<class 'str'>` | Generated independently per instance |

#### `Constraint`

| Field | Type | Default |
| --- | --- | --- |
| `source_answer_ids` | `list[str]` | Required |
| `reviewed_by` | `<class 'str'>` | Required |
| `allowed_exercise_ids` | `list[str]` | Required |
| `max_rpe` | `<class 'float'>` | 4.0 |
| `max_session_minutes` | `float \| None` | None |
| `max_days_per_week` | `int \| None` | None |
| `professional_scope` | `<class 'bool'>` | False |
| `note` | `<class 'str'>` | '' |

#### `Session`

| Field | Type | Default |
| --- | --- | --- |
| `session_id` | `<class 'str'>` | Generated independently per instance |
| `participant_id` | `<class 'str'>` | Generated independently per instance |
| `spec_id` | `<class 'str'>` | Required |
| `spec_version` | `<class 'str'>` | Required |
| `format_version` | `<class 'str'>` | '1.0' |
| `version` | `<class 'int'>` | 0 |
| `profile_version` | `<class 'int'>` | 0 |
| `created_at` | `<class 'str'>` | Generated independently per instance |
| `updated_at` | `<class 'str'>` | Generated independently per instance |
| `language` | `Literal['en']` | 'en' |
| `consent` | `<class 'Consent'>` | Generated independently per instance |
| `responses` | `dict[str, dict[str, Answer]]` | Required |
| `audit_history` | `list[dict[str, Any]]` | Generated independently per instance |
| `derived_results` | `list[dict[str, Any]]` | Generated independently per instance |
| `constraints` | `list[Constraint]` | Generated independently per instance |
| `questions` | `list[str]` | Generated independently per instance |
| `pending` | `dict[str, dict[str, Any]]` | Generated independently per instance |
| `requests` | `dict[str, str]` | Generated independently per instance |
| `broken_references` | `dict[str, str]` | Generated independently per instance |
| `plans` | `list[dict[str, Any]]` | Generated independently per instance |
| `feedback` | `list[dict[str, Any]]` | Generated independently per instance |
| `summary` | `dict[str, Any] \| None` | None |
| `needs_update` | `<class 'bool'>` | False |

#### `Question`

| Field | Type | Default |
| --- | --- | --- |
| `question_id` | `<class 'str'>` | Required |
| `field_path` | `<class 'str'>` | Required |
| `text` | `<class 'str'>` | Required |
| `answer_type` | `<class 'str'>` | Required |
| `unit` | `str \| None` | None |
| `options` | `dict[str, str]` | Generated independently per instance |
| `allowed_statuses` | `list[str]` | Generated independently per instance |
| `reason` | `<class 'str'>` | 'Optional information relevant to your training.' |

#### `Flag`

| Field | Type | Default |
| --- | --- | --- |
| `rule_id` | `<class 'str'>` | Required |
| `description` | `<class 'str'>` | Required |
| `severity` | `Literal['emergency', 'prompt_professional_review', 'clarification_needed', 'adaptation_needed', 'monitoring_note']` | Required |
| `answer_ids` | `list[str]` | Generated independently per instance |
| `evidence` | `list[str]` | Generated independently per instance |
| `next_step` | `<class 'str'>` | Required |
| `resolved` | `<class 'bool'>` | False |

#### `Readiness`

| Field | Type | Default |
| --- | --- | --- |
| `status` | `Literal['ready', 'limited', 'needs_more_info', 'needs_review', 'emergency']` | Required |
| `flags` | `list[Flag]` | Required |
| `missing` | `list[dict[str, Any]]` | Required |
| `allowed_exercise_ids` | `list[str]` | Required |
| `planning_scope` | `<class 'str'>` | Required |
| `max_rpe` | `<class 'float'>` | 4.0 |
| `max_minutes` | `<class 'float'>` | 0.0 |
| `max_days` | `<class 'int'>` | 0 |
| `rule_states` | `dict[str, Literal['triggered', 'not_triggered', 'indeterminate']]` | Generated independently per instance |

#### `ExerciseBlock`

| Field | Type | Default |
| --- | --- | --- |
| `exercise_id` | `<class 'str'>` | Required |
| `phase` | `Literal['warmup', 'main', 'cooldown']` | Required |
| `active_minutes` | `<class 'float'>` | Required |
| `rest_minutes` | `<class 'float'>` | 0.0 |
| `sets` | `int \| None` | None |
| `repetitions` | `int \| None` | None |
| `rpe` | `<class 'float'>` | Required |

#### `PlanDay`

| Field | Type | Default |
| --- | --- | --- |
| `day` | `<class 'int'>` | Required |
| `kind` | `Literal['training', 'rest', 'recovery']` | Required |
| `preparation_minutes` | `<class 'float'>` | 0.0 |
| `blocks` | `list[ExerciseBlock]` | Generated independently per instance |

#### `CandidatePlan`

| Field | Type | Default |
| --- | --- | --- |
| `days` | `list[PlanDay]` | Required |

#### `PlanResult`

| Field | Type | Default |
| --- | --- | --- |
| `status` | `Literal['ready', 'limited', 'needs_more_info', 'needs_review', 'emergency']` | Required |
| `readiness` | `<class 'Readiness'>` | Required |
| `plan` | `dict[str, Any] \| None` | None |

#### `TurnResult`

| Field | Type | Default |
| --- | --- | --- |
| `session_id` | `<class 'str'>` | Required |
| `version` | `<class 'int'>` | Required |
| `status` | `Literal['ready', 'limited', 'needs_more_info', 'needs_review', 'emergency']` | Required |
| `questions` | `list[Question]` | Generated independently per instance |
| `pending` | `dict[str, dict[str, Any]]` | Generated independently per instance |
| `flags` | `list[Flag]` | Generated independently per instance |
| `message` | `<class 'str'>` | '' |

#### `Feedback`

| Field | Type | Default |
| --- | --- | --- |
| `plan_id` | `<class 'str'>` | Required |
| `day` | `<class 'int'>` | Required |
| `completed` | `<class 'bool'>` | Required |
| `tolerance` | `Literal['comfortable', 'too_hard', 'symptoms', 'unknown']` | Required |
| `notes` | `<class 'str'>` | '' |
| `recorded_at` | `<class 'str'>` | Generated independently per instance |
| `answer_updates` | `dict[str, Any]` | Generated independently per instance |

### Complete English intake field directory

These are presentation prompts for the source DSL. The original YAML retains its original-language labels and notes. System identifiers are listed for integration reference but are never asked as health questions.

#### `profile`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `profile.participant_id` | `text` | None | Please share participant id for this participant id. You may skip or say you do not know. |
| `profile.age` | `number` | years | What is your current age in years? |
| `profile.sex_for_reference` | `text` | None | If an applicable reference equation needs it, what relevant physiological sex information would you voluntarily like to provide? |
| `profile.gender_pronouns` | `text` | None | What name or pronouns would you like us to use? This is optional and is not used as a physiological reference. |
| `profile.height` | `measurements` | cm | Would you like to share existing height measurements, including units, dates, and how they were measured? |
| `profile.weight` | `measurements` | kg | Would you like to share current or previous weight measurements, including units, dates, and devices? |
| `profile.weight_change_intended` | `bool` | None | Please share weight change intended for this weight change intended. You may skip or say you do not know. |
| `profile.weight_change_details` | `text` | None | Please share weight change details for this weight change details. You may skip or say you do not know. |
| `profile.hand_dominance` | `enum:dominance` | None | Please share hand dominance for this hand dominance. You may skip or say you do not know. |
| `profile.leg_dominance` | `enum:dominance` | None | Please share leg dominance for this leg dominance. You may skip or say you do not know. |
| `profile.occupation` | `text` | None | Please share occupation for this occupation. You may skip or say you do not know. |
| `profile.altitude_environment` | `text` | None | Please share altitude environment for this altitude environment. You may skip or say you do not know. |
| `profile.communication_access` | `text` | None | Please share communication access for this communication access. You may skip or say you do not know. |

#### `immediate_screen`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `immediate_screen.current_chest_discomfort` | `bool` | None | Do you currently have new, significant, or unexplained chest pressure, tightness, or pain? |
| `immediate_screen.severe_rest_dyspnea` | `bool` | None | Are you currently having marked difficulty breathing even at rest? |
| `immediate_screen.current_fainting_or_confusion` | `bool` | None | Are you currently fainting, close to fainting, or newly confused? |
| `immediate_screen.sudden_focal_neurology` | `bool` | None | Have you recently developed sudden weakness or numbness on one side, trouble speaking, or a major vision change, even if it has improved? |
| `immediate_screen.new_saddle_sensation_change` | `bool` | None | Have you recently developed reduced sensation around the groin, anus, or area that rests on a saddle? |
| `immediate_screen.new_bladder_bowel_control_change` | `bool` | None | Have you recently developed difficulty urinating, loss of bladder sensation, or changed bowel or bladder control? Distinguish this from a stable, previously assessed condition. |
| `immediate_screen.new_bilateral_leg_neurology` | `bool` | None | Have you recently developed back pain with numbness or weakness in both legs, or rapidly worsening difficulty walking? |
| `immediate_screen.major_trauma_or_rapid_pain` | `bool` | None | Have you recently had a major injury, sudden severe pain, or rapidly worsening pain? |
| `immediate_screen.current_fever_or_acute_illness` | `bool` | None | Do you currently have fever, an acute infection, or significant general illness? |
| `immediate_screen.recent_emergency_events` | `record:event` | None | Please share recent emergency events for this recent emergency events. You may skip or say you do not know. |
| `immediate_screen.screen_time` | `datetime` | None | When were the current symptom answers explicitly checked? |

#### `medical_history`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `medical_history.condition_screen` | `matrix:conditions` | None | Please share condition screen for this condition screen. You may skip or say you do not know. |
| `medical_history.conditions` | `record:condition` | None | Which diagnosed or currently investigated health conditions would you like to report? Report each separately, or explicitly report none. |
| `medical_history.family_history` | `record:family_event` | None | Please share family history for this family history. You may skip or say you do not know. |
| `medical_history.symptoms` | `record:symptom` | None | Do you have current or recurring symptoms relevant to activity? Include timing and triggers, or explicitly report none. |
| `medical_history.symptom_screen` | `matrix:symptoms` | None | Please share symptom screen for this symptom screen. You may skip or say you do not know. |
| `medical_history.hospitalization_events` | `record:event` | None | Please share hospitalization events for this hospitalization events. You may skip or say you do not know. |
| `medical_history.professional_restrictions` | `record:restriction` | None | Has a physician or rehabilitation professional given you any activity restrictions or allowed alternatives? Share the wording and source, or explicitly report none. |
| `medical_history.prior_screening` | `record:screening_result` | None | Please share prior screening for this prior screening. You may skip or say you do not know. |
| `medical_history.other_health_factors` | `record:other_factor` | None | Please share other health factors for this other health factors. You may skip or say you do not know. |

#### `injury_history`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `injury_history.ever_injury_or_surgery` | `bool` | None | Have you ever had an injury, operation, immobilization, or loss of function, including events that have recovered? |
| `injury_history.injuries` | `record:injury` | None | Describe each injury or surgery separately, including timing, side, current function, recovery, and existing restrictions. |
| `injury_history.implants_and_aids` | `record:device_aid` | None | Please share implants and aids for this implants and aids. You may skip or say you do not know. |
| `injury_history.current_pain_regions` | `multi:body_region` | None | Where do you currently have pain or discomfort? Select each relevant region, or explicitly select none. |
| `injury_history.persistent_impairments` | `record:impairment` | None | Please share persistent impairments for this persistent impairments. You may skip or say you do not know. |
| `injury_history.rehabilitation_documents` | `refs` | None | Please share rehabilitation documents for this rehabilitation documents. You may skip or say you do not know. |

#### `function`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `function.activities` | `matrix:daily_activities` | None | Please share activities for this activities. You may skip or say you do not know. |
| `function.movement_limits` | `record:movement_limit` | None | Please share movement limits for this movement limits. You may skip or say you do not know. |
| `function.falls_last_12_months` | `integer` | count | Please share falls last 12 months for this falls last 12 months. You may skip or say you do not know. |
| `function.falls_details` | `text` | None | Please share falls details for this falls details. You may skip or say you do not know. |
| `function.walking_tolerance` | `text` | None | From everyday experience, how long or far can you walk comfortably, and what makes you stop? No test is required. |
| `function.standing_tolerance` | `text` | None | Please share standing tolerance for this standing tolerance. You may skip or say you do not know. |
| `function.sitting_tolerance` | `text` | None | Please share sitting tolerance for this sitting tolerance. You may skip or say you do not know. |
| `function.sensory_access` | `text` | None | Please share sensory access for this sensory access. You may skip or say you do not know. |
| `function.cognitive_access` | `text` | None | Please share cognitive access for this cognitive access. You may skip or say you do not know. |
| `function.assistance_required` | `text` | None | Please share assistance required for this assistance required. You may skip or say you do not know. |
| `function.best_and_worst_days` | `text` | None | Please share best and worst days for this best and worst days. You may skip or say you do not know. |

#### `asymmetry`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `asymmetry.noticed_difference` | `bool` | None | Have you or someone else noticed a left-right difference? This does not by itself establish a medical problem. |
| `asymmetry.differences` | `record:asymmetry_report` | None | Please share differences for this differences. You may skip or say you do not know. |
| `asymmetry.paired_observations` | `record:paired_measurement` | None | Please share paired observations for this paired observations. You may skip or say you do not know. |
| `asymmetry.habitual_loading` | `text` | None | Please share habitual loading for this habitual loading. You may skip or say you do not know. |
| `asymmetry.compensations` | `text` | None | Please share compensations for this compensations. You may skip or say you do not know. |
| `asymmetry.limb_length_reports` | `text` | None | Please share limb length reports for this limb length reports. You may skip or say you do not know. |
| `asymmetry.progressive_wasting_or_weakness` | `bool` | None | Has one side been becoming thinner, progressively weaker, or less able to perform activities? |

#### `body_composition`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `body_composition.circumferences` | `record:circumference` | None | Please share circumferences for this circumferences. You may skip or say you do not know. |
| `body_composition.body_fat_percent` | `measurements` | % | Do you have an existing body-fat percentage measurement? It is fine if it has not been measured. |
| `body_composition.fat_mass` | `measurements` | kg | Please share fat mass for this fat mass. You may skip or say you do not know. |
| `body_composition.fat_free_mass` | `measurements` | kg | Please share fat free mass for this fat free mass. You may skip or say you do not know. |
| `body_composition.lean_soft_tissue_mass` | `measurements` | kg | Please share lean soft tissue mass for this lean soft tissue mass. You may skip or say you do not know. |
| `body_composition.device_muscle_mass` | `measurements` | kg | Please share device muscle mass for this device muscle mass. You may skip or say you do not know. |
| `body_composition.skeletal_muscle_mass` | `measurements` | kg | Please share skeletal muscle mass for this skeletal muscle mass. You may skip or say you do not know. |
| `body_composition.appendicular_lean_mass` | `measurements` | kg | Please share appendicular lean mass for this appendicular lean mass. You may skip or say you do not know. |
| `body_composition.regional_composition` | `record:regional_composition` | None | Please share regional composition for this regional composition. You may skip or say you do not know. |
| `body_composition.visceral_fat` | `record:lab_measurement` | None | Please share visceral fat for this visceral fat. You may skip or say you do not know. |
| `body_composition.body_water` | `record:lab_measurement` | None | Please share body water for this body water. You may skip or say you do not know. |
| `body_composition.bone_density` | `record:bone_report` | None | Please share bone density for this bone density. You may skip or say you do not know. |
| `body_composition.metabolic_rate` | `record:lab_measurement` | None | Please share metabolic rate for this metabolic rate. You may skip or say you do not know. |
| `body_composition.other_device_metrics` | `record:lab_measurement` | None | Please share other device metrics for this other device metrics. You may skip or say you do not know. |

#### `cardiovascular`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `cardiovascular.resting_heart_rate` | `measurements` | bpm | Do you have existing resting heart-rate readings? Include resting position, date, device, and units; an all-day average is different. |
| `cardiovascular.sleeping_heart_rate` | `measurements` | bpm | Please share sleeping heart rate for this sleeping heart rate. You may skip or say you do not know. |
| `cardiovascular.day_average_heart_rate` | `measurements` | bpm | Please share day average heart rate for this day average heart rate. You may skip or say you do not know. |
| `cardiovascular.heart_rate_variability` | `record:lab_measurement` | None | Please share heart rate variability for this heart rate variability. You may skip or say you do not know. |
| `cardiovascular.blood_pressure` | `record:blood_pressure` | None | Please share blood pressure for this blood pressure. You may skip or say you do not know. |
| `cardiovascular.orthostatic_records` | `record:lab_measurement` | None | Please share orthostatic records for this orthostatic records. You may skip or say you do not know. |
| `cardiovascular.ecg_and_cardiac_reports` | `refs` | None | Please share ecg and cardiac reports for this ecg and cardiac reports. You may skip or say you do not know. |
| `cardiovascular.clinician_hr_bp_limits` | `refs` | None | Please share clinician hr bp limits for this clinician hr bp limits. You may skip or say you do not know. |
| `cardiovascular.circulatory_symptoms` | `text` | None | Please share circulatory symptoms for this circulatory symptoms. You may skip or say you do not know. |

#### `respiratory`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `respiratory.resting_respiratory_rate` | `measurements` | breaths/min | Please share resting respiratory rate for this resting respiratory rate. You may skip or say you do not know. |
| `respiratory.resting_spo2` | `measurements` | % | Please share resting SpO2 for this resting SpO2. You may skip or say you do not know. |
| `respiratory.oxygen_therapy` | `text` | None | Please share oxygen therapy for this oxygen therapy. You may skip or say you do not know. |
| `respiratory.spirometry` | `record:spirometry` | None | Would you like to share existing spirometry results and their dates, units, method, quality, and professional interpretation? No new test is required. |
| `respiratory.other_pulmonary_tests` | `record:lab_measurement` | None | Please share other pulmonary tests for this other pulmonary tests. You may skip or say you do not know. |
| `respiratory.breathing_triggers` | `text` | None | Please share breathing triggers for this breathing triggers. You may skip or say you do not know. |
| `respiratory.inhaler_action_plan` | `text` | None | Please share inhaler action plan for this inhaler action plan. You may skip or say you do not know. |

#### `medication_and_exposure`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `medication_and_exposure.medications` | `record:medication` | None | Which prescription or nonprescription medications do you currently or recently use? Include names and existing exercise instructions, or explicitly report none. |
| `medication_and_exposure.supplements` | `record:medication` | None | Please share supplements for this supplements. You may skip or say you do not know. |
| `medication_and_exposure.allergies` | `record:allergy` | None | Please share allergies for this allergies. You may skip or say you do not know. |
| `medication_and_exposure.tobacco_nicotine` | `text` | None | Please share tobacco nicotine for this tobacco nicotine. You may skip or say you do not know. |
| `medication_and_exposure.alcohol` | `text` | None | Please share alcohol for this alcohol. You may skip or say you do not know. |
| `medication_and_exposure.caffeine` | `text` | None | Please share caffeine for this caffeine. You may skip or say you do not know. |
| `medication_and_exposure.other_substances` | `text` | None | Please share other substances for this other substances. You may skip or say you do not know. |
| `medication_and_exposure.recent_changes` | `text` | None | Please share recent changes for this recent changes. You may skip or say you do not know. |

#### `laboratory_reports`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `laboratory_reports.blood_tests` | `record:lab_measurement` | None | Please share blood tests for this blood tests. You may skip or say you do not know. |
| `laboratory_reports.imaging_reports` | `refs` | None | Please share imaging reports for this imaging reports. You may skip or say you do not know. |
| `laboratory_reports.neurological_tests` | `refs` | None | Please share neurological tests for this neurological tests. You may skip or say you do not know. |
| `laboratory_reports.clinical_summary` | `text` | None | Please share clinical summary for this clinical summary. You may skip or say you do not know. |
| `laboratory_reports.pending_evaluation` | `text` | None | Please share pending evaluation for this pending evaluation. You may skip or say you do not know. |

#### `reproductive_and_hormonal`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `reproductive_and_hormonal.relevance` | `bool` | None | Would you like to share reproductive or hormonal circumstances that may affect exercise? |
| `reproductive_and_hormonal.pregnancy_status` | `text` | None | If relevant and you wish to share, are you pregnant, possibly pregnant, or having this checked? |
| `reproductive_and_hormonal.gestational_age` | `number` | weeks | Please share gestational age for this gestational age. You may skip or say you do not know. |
| `reproductive_and_hormonal.pregnancy_complications` | `text` | None | Please share pregnancy complications for this pregnancy complications. You may skip or say you do not know. |
| `reproductive_and_hormonal.postpartum_details` | `text` | None | Please share postpartum details for this postpartum details. You may skip or say you do not know. |
| `reproductive_and_hormonal.breastfeeding` | `bool` | None | Please share breastfeeding for this breastfeeding. You may skip or say you do not know. |
| `reproductive_and_hormonal.menstrual_pattern` | `text` | None | Please share menstrual pattern for this menstrual pattern. You may skip or say you do not know. |
| `reproductive_and_hormonal.cycle_related_effects` | `text` | None | Please share cycle related effects for this cycle related effects. You may skip or say you do not know. |
| `reproductive_and_hormonal.menopause` | `text` | None | Please share menopause for this menopause. You may skip or say you do not know. |
| `reproductive_and_hormonal.hormonal_therapy` | `refs` | None | Please share hormonal therapy for this hormonal therapy. You may skip or say you do not know. |
| `reproductive_and_hormonal.pelvic_floor_symptoms` | `text` | None | Please share pelvic floor symptoms for this pelvic floor symptoms. You may skip or say you do not know. |

#### `nutrition_recovery`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `nutrition_recovery.diet_pattern` | `text` | None | Please share diet pattern for this diet pattern. You may skip or say you do not know. |
| `nutrition_recovery.energy_intake` | `record:lab_measurement` | None | Please share energy intake for this energy intake. You may skip or say you do not know. |
| `nutrition_recovery.protein_intake` | `record:lab_measurement` | None | Please share protein intake for this protein intake. You may skip or say you do not know. |
| `nutrition_recovery.food_restrictions` | `text` | None | Please share food restrictions for this food restrictions. You may skip or say you do not know. |
| `nutrition_recovery.hydration` | `text` | None | Please share hydration for this hydration. You may skip or say you do not know. |
| `nutrition_recovery.appetite_gi` | `text` | None | Please share appetite gi for this appetite gi. You may skip or say you do not know. |
| `nutrition_recovery.restrictive_or_compensatory_behaviors` | `text` | None | Please share restrictive or compensatory behaviors for this restrictive or compensatory behaviors. You may skip or say you do not know. |
| `nutrition_recovery.possible_underfueling` | `text` | None | Please share possible underfueling for this possible underfueling. You may skip or say you do not know. |
| `nutrition_recovery.sleep_hours` | `number` | hours/day | Approximately how many hours do you sleep per day, and over what recent period? |
| `nutrition_recovery.sleep_quality` | `text` | None | How have sleep onset, awakenings, daytime sleepiness, and recovery on waking been recently? |
| `nutrition_recovery.shift_work` | `text` | None | Please share shift work for this shift work. You may skip or say you do not know. |
| `nutrition_recovery.fatigue_baseline` | `text` | None | How does everyday fatigue affect you, and how long has it been present? |
| `nutrition_recovery.delayed_exacerbation` | `bool` | None | After minor physical or mental activity, do you develop substantial, lasting whole-body worsening hours later or the next day, beyond ordinary local muscle soreness? |
| `nutrition_recovery.delayed_exacerbation_details` | `text` | None | What activity triggers the worsening, how long is the delay, how long does it last, and what helps recovery? |
| `nutrition_recovery.orthostatic_intolerance` | `bool` | None | Does standing up repeatedly cause dizziness, palpitations, weakness, or near-fainting? Do not test this by pushing yourself to symptoms. |
| `nutrition_recovery.recent_infection_recovery` | `text` | None | Please share recent infection recovery for this recent infection recovery. You may skip or say you do not know. |

#### `psychosocial_environment`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `psychosocial_environment.stress` | `text` | None | Please share stress for this stress. You may skip or say you do not know. |
| `psychosocial_environment.mental_health_support` | `text` | None | Please share mental health support for this mental health support. You may skip or say you do not know. |
| `psychosocial_environment.fear_and_pain_expectations` | `text` | None | Please share fear and pain expectations for this fear and pain expectations. You may skip or say you do not know. |
| `psychosocial_environment.body_image_preferences` | `text` | None | Please share body image preferences for this body image preferences. You may skip or say you do not know. |
| `psychosocial_environment.exercise_compulsion` | `text` | None | Please share exercise compulsion for this exercise compulsion. You may skip or say you do not know. |
| `psychosocial_environment.support_and_access` | `text` | None | Please share support and access for this support and access. You may skip or say you do not know. |
| `psychosocial_environment.environmental_triggers` | `text` | None | Please share environmental triggers for this environmental triggers. You may skip or say you do not know. |
| `psychosocial_environment.equipment_accessibility` | `text` | None | Please share equipment accessibility for this equipment accessibility. You may skip or say you do not know. |
| `psychosocial_environment.touch_and_media_preferences` | `text` | None | Please share touch and media preferences for this touch and media preferences. You may skip or say you do not know. |

#### `activity_history`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `activity_history.current_activities` | `record:activity` | None | What activities do you currently do, how often, for how long, at what effort, and with what immediate or next-day response? You may explicitly report none. |
| `activity_history.sedentary_time` | `number` | hours/day | Please share sedentary time for this sedentary time. You may skip or say you do not know. |
| `activity_history.steps` | `measurements` | steps/day | Please share steps for this steps. You may skip or say you do not know. |
| `activity_history.training_history` | `text` | None | What training and exercises are you currently familiar with? Distinguish current experience from distant past experience. |
| `activity_history.recent_break` | `text` | None | Please share recent break for this recent break. You may skip or say you do not know. |
| `activity_history.prior_program_response` | `text` | None | Please share prior program response for this prior program response. You may skip or say you do not know. |
| `activity_history.usual_working_loads` | `record:existing_performance` | None | Please share usual working loads for this usual working loads. You may skip or say you do not know. |
| `activity_history.existing_fitness_tests` | `record:existing_performance` | None | Please share existing fitness tests for this existing fitness tests. You may skip or say you do not know. |
| `activity_history.existing_cpet` | `record:existing_performance` | None | Please share existing cpet for this existing cpet. You may skip or say you do not know. |
| `activity_history.exercise_adverse_history` | `text` | None | Have you had adverse reactions during or after exercise? Describe what happened and when, or explicitly report none. |

#### `goals_and_constraints`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `goals_and_constraints.goals` | `multi:goals` | None | What would you like training to help you achieve? Select your goals; you may describe priorities separately. |
| `goals_and_constraints.goal_details` | `record:goal` | None | Please share goal details for this goal details. You may skip or say you do not know. |
| `goals_and_constraints.days_per_week` | `integer` | days/week | How many days per week can you realistically train, from zero to seven? |
| `goals_and_constraints.session_duration` | `number` | min | How many minutes can you allow per session, including preparation, warm-up, and rest? |
| `goals_and_constraints.time_preferences` | `text` | None | Which dates or times can you train? You may list weekday names or say that any day is available. |
| `goals_and_constraints.equipment` | `text` | None | What equipment and space can you use? Name items explicitly, such as none, a chair, a wall, or a stationary bike. |
| `goals_and_constraints.supervision` | `text` | None | Please share supervision for this supervision. You may skip or say you do not know. |
| `goals_and_constraints.preferences` | `text` | None | Which activities do you prefer or want to avoid? You may explicitly report no preferences. |
| `goals_and_constraints.tracking_preferences` | `text` | None | Please share tracking preferences for this tracking preferences. You may skip or say you do not know. |
| `goals_and_constraints.other_constraints` | `record:other_factor` | None | Please share other constraints for this other constraints. You may skip or say you do not know. |

#### `reports_and_update`

| Path | Type | Unit | English prompt |
| --- | --- | --- | --- |
| `reports_and_update.reports` | `record:report` | None | Please share reports for this reports. You may skip or say you do not know. |
| `reports_and_update.unmentioned_factors` | `text` | None | Is there anything else about your health, body, past experiences, or circumstances that could affect training? |
| `reports_and_update.user_corrections` | `text` | None | Is there information you would like to correct, withdraw, or mark uncertain? |
| `reports_and_update.changes_since_last` | `text` | None | Have there been new symptoms, diagnoses, medications, injuries, or life changes since the last review? |
| `reports_and_update.reviewed_at` | `datetime` | None | When did you last review this information? |

#### Record `event`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `event_name` | `text` | None |
| `date` | `date` | None |
| `cause` | `multi:cause` | None |
| `hospital_treatment` | `text` | None |
| `bedrest_immobilization` | `text` | None |
| `before_vs_now` | `text` | None |
| `current_state` | `enum:trajectory` | None |
| `linked_records` | `refs` | None |

#### Record `condition`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `name` | `text` | None |
| `category` | `text` | None |
| `diagnostic_status` | `enum:diagnostic_status` | None |
| `diagnosed_when` | `date` | None |
| `current_control` | `enum:control` | None |
| `symptoms_and_triggers` | `text` | None |
| `recent_flare` | `text` | None |
| `treatment` | `text` | None |
| `exercise_effect` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `family_event`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `relation` | `text` | None |
| `event` | `text` | None |
| `age_at_event` | `number` | years |
| `confirmed` | `enum:diagnostic_status` | None |
| `details` | `text` | None |

#### Record `symptom`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `name` | `text` | None |
| `region` | `multi:body_region` | None |
| `side` | `enum:laterality` | None |
| `onset_date` | `date` | None |
| `onset_type` | `enum:onset` | None |
| `current` | `bool` | None |
| `last_episode` | `datetime` | None |
| `frequency_duration` | `text` | None |
| `contexts` | `multi:activity_context` | None |
| `triggers_relief` | `text` | None |
| `pain_intensity` | `number` | score_0_10 |
| `functional_effect` | `text` | None |
| `associated_features` | `text` | None |
| `trend` | `enum:trajectory` | None |
| `recovery_pattern` | `text` | None |
| `evaluated` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `injury`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `event_name` | `text` | None |
| `cause` | `multi:cause` | None |
| `mechanism` | `text` | None |
| `onset_date` | `date` | None |
| `region` | `multi:body_region` | None |
| `side` | `enum:laterality` | None |
| `diagnosis` | `text` | None |
| `diagnostic_status` | `enum:diagnostic_status` | None |
| `tissue_or_structure` | `text` | None |
| `treatment` | `text` | None |
| `surgery_details` | `text` | None |
| `immobilization` | `text` | None |
| `complications` | `text` | None |
| `rehabilitation` | `text` | None |
| `last_assessment` | `text` | None |
| `pre_event_function` | `text` | None |
| `current_function` | `text` | None |
| `residual_domains` | `multi:function_domain` | None |
| `residual_details` | `text` | None |
| `symptom_free_but_limited` | `bool` | None |
| `return_to_activity` | `text` | None |
| `recurrence` | `text` | None |
| `trajectory` | `enum:trajectory` | None |
| `limitations` | `refs` | None |
| `linked_records` | `refs` | None |

#### Record `impairment`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `description` | `text` | None |
| `domains` | `multi:function_domain` | None |
| `region` | `multi:body_region` | None |
| `side` | `enum:laterality` | None |
| `onset_date` | `date` | None |
| `onset` | `enum:onset` | None |
| `before_vs_now` | `text` | None |
| `affected_tasks` | `text` | None |
| `severity` | `enum:functional_difficulty` | None |
| `compensation_or_aids` | `text` | None |
| `trend` | `enum:trajectory` | None |
| `cause_evidence` | `text` | None |
| `professional_plan` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `restriction`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `issuer_role` | `enum:professional_role` | None |
| `issued_on` | `date` | None |
| `original_instruction` | `text` | None |
| `reason` | `text` | None |
| `region_side` | `text` | None |
| `restricted_movements` | `text` | None |
| `load_intensity_limits` | `text` | None |
| `duration_frequency_limits` | `text` | None |
| `allowed_alternatives` | `text` | None |
| `expires_or_review` | `date` | None |
| `return_criteria` | `text` | None |
| `status_now` | `text` | None |
| `report_refs` | `refs` | None |

#### Record `movement_limit`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `task` | `text` | None |
| `side` | `enum:laterality` | None |
| `difficulty` | `enum:functional_difficulty` | None |
| `reasons` | `multi:limitation_reason` | None |
| `conditions` | `text` | None |
| `tolerated_variant` | `text` | None |
| `after_effects` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `asymmetry_report`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `domain` | `text` | None |
| `region` | `text` | None |
| `left_description` | `text` | None |
| `right_description` | `text` | None |
| `noticed_on` | `date` | None |
| `evidence` | `enum:evidence_kind` | None |
| `trend` | `enum:trajectory` | None |
| `context` | `text` | None |
| `associated_features` | `text` | None |
| `clinical_interpretation` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `paired_measurement`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `metric_name` | `text` | None |
| `construct` | `text` | None |
| `region_task` | `text` | None |
| `left` | `measurement` | None |
| `right` | `measurement` | None |
| `left_repeats` | `measurements` | None |
| `right_repeats` | `measurements` | None |
| `protocol` | `text` | None |
| `order_and_rest` | `text` | None |
| `pain_fatigue_effort` | `text` | None |
| `prosthesis_or_support` | `text` | None |
| `reference_direction` | `text` | None |
| `measurement_error` | `text` | None |
| `professional_interpretation` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `circumference`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `site` | `text` | None |
| `side` | `enum:laterality` | None |
| `value` | `measurement` | cm |
| `landmark` | `text` | None |
| `muscle_state` | `text` | None |
| `edema_or_recent_load` | `text` | None |

#### Record `regional_composition`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `region` | `text` | None |
| `metric_original_name` | `text` | None |
| `value` | `measurement` | None |
| `measurement_definition` | `text` | None |
| `device_reference` | `text` | None |
| `report_refs` | `refs` | None |

#### Record `bone_report`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `site` | `text` | None |
| `bmd` | `measurement` | g/cm2 |
| `t_score` | `number` | None |
| `z_score` | `number` | None |
| `method_reference` | `text` | None |
| `clinician_conclusion` | `text` | None |
| `report_refs` | `refs` | None |

#### Record `blood_pressure`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `systolic` | `measurement` | mmHg |
| `diastolic` | `measurement` | mmHg |
| `pulse` | `measurement` | bpm |
| `arm` | `enum:laterality` | None |
| `posture_rest` | `text` | None |
| `cuff_device` | `text` | None |
| `sequence` | `integer` | count |
| `medication_and_symptoms` | `text` | None |

#### Record `spirometry`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `date` | `date` | None |
| `vc` | `measurement` | L |
| `svc` | `measurement` | L |
| `fvc` | `measurement` | L |
| `fev1` | `measurement` | L |
| `fev1_fvc` | `measurement` | ratio |
| `pef` | `measurement` | L/s |
| `bronchodilator_context` | `text` | None |
| `reference_results` | `text` | None |
| `quality_grade` | `text` | None |
| `conclusion` | `text` | None |
| `report_refs` | `refs` | None |

#### Record `lab_measurement`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `name` | `text` | None |
| `value` | `measurement` | None |
| `specimen_or_context` | `text` | None |
| `reference_interval` | `text` | None |
| `report_interpretation` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `medication`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `name` | `text` | None |
| `ingredients` | `text` | None |
| `reason` | `text` | None |
| `dose_unit` | `text` | None |
| `route_frequency` | `text` | None |
| `time_relative_exercise` | `text` | None |
| `start_end_change` | `text` | None |
| `side_effects` | `text` | None |
| `exercise_instructions` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `allergy`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `trigger` | `text` | None |
| `reaction` | `text` | None |
| `severity_history` | `text` | None |
| `action_plan` | `text` | None |

#### Record `device_aid`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `name_type` | `text` | None |
| `site_side` | `text` | None |
| `installed_or_started` | `date` | None |
| `function_and_fit` | `text` | None |
| `specific_restrictions` | `text` | None |
| `training_adaptations` | `text` | None |
| `linked_records` | `refs` | None |

#### Record `screening_result`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `tool_name_version` | `text` | None |
| `completed_at` | `date` | None |
| `original_result` | `text` | None |
| `followup_completed` | `text` | None |
| `current_relevance` | `text` | None |
| `report_refs` | `refs` | None |

#### Record `activity`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `name` | `text` | None |
| `frequency` | `number` | sessions/week |
| `duration` | `number` | min |
| `intensity_experience` | `text` | None |
| `months_consistent` | `number` | months |
| `symptoms_after` | `text` | None |
| `adaptations` | `text` | None |

#### Record `existing_performance`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `name` | `text` | None |
| `observed_date` | `date` | None |
| `side` | `enum:laterality` | None |
| `metrics` | `record:lab_measurement` | None |
| `sets_reps_load` | `text` | None |
| `protocol` | `text` | None |
| `effort_symptoms` | `text` | None |
| `measurement_or_estimate` | `text` | None |
| `professional_interpretation` | `text` | None |
| `report_refs` | `refs` | None |

#### Record `goal`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `description` | `text` | None |
| `priority` | `integer` | rank |
| `baseline` | `text` | None |
| `desired_change` | `text` | None |
| `time_horizon` | `text` | None |
| `tradeoffs` | `text` | None |

#### Record `report`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `report_id` | `text` | None |
| `type_title` | `text` | None |
| `exam_date` | `date` | None |
| `issuer_role` | `text` | None |
| `content_or_attachment` | `text` | None |
| `extraction_location` | `text` | None |
| `extraction_confirmed` | `bool` | None |
| `limitations` | `text` | None |

#### Record `other_factor`

Each record has a generated `record_id`; every field below uses an Answer envelope.

| Field | Type | Unit |
| --- | --- | --- |
| `description` | `text` | None |
| `timing` | `text` | None |
| `exercise_impact` | `text` | None |
| `existing_advice` | `text` | None |
| `linked_records` | `refs` | None |

Regenerate this appendix after changing methods, models, or the DSL:

```bash
python tools/generate_reference.py
```
