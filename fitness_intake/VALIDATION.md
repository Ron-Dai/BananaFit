# Validation Report

Validation date: 2026-09-12

Component version: 0.1.0

Python version: 3.12
Repository base commit: `830f99f22e54b9c220d21116201d7de77cc56ee4`

## Result

The component passed its complete local test suite and a paid, live end-to-end
integration test using fictional data through OpenRouter's OpenAI-compatible API
and the `deepseek/deepseek-chat` model.

The live flow successfully:

1. Connected to the configured external API over HTTPS.
2. Authenticated using the project owner's authorized development credential.
3. Extracted a fictional age from natural-language input.
4. Held the extracted value for explicit user confirmation.
5. Accepted a complete fictional structured fitness profile.
6. Generated a fourteen-day candidate plan.
7. Applied deterministic timing normalization to model-supplied strength blocks.
8. Validated schedule, exercise scope, equipment, session duration, RPE, rest days,
   and the no-automatic-progression rule.
9. Rendered the accepted plan as English Markdown.

## Automated checks

```text
121 passed
All checks passed!
PUBLIC_DEMONSTRATION_KEY_CONFIGURED
```

The test suite includes YAML parsing, branching and readiness rules, answer
normalization, consent enforcement, provider transport failures, plan validation,
feedback-driven revision, storage, deletion, imports, exports, and public service
methods. HTTP unit tests use synthetic credentials and mocked transports.

## Credential handling

A user-authorized free demonstration key is stored as a source fallback in
`src/sexybanana_intake/providers.py`, so the package and example work immediately
after cloning. Environment variables take priority over the fallback. Production
deployments should remove and rotate the fallback, then provide
`DEEPSEEK_API_KEY` through managed configuration. The OpenRouter defaults are:

```bash
export DEEPSEEK_BASE_URL=https://openrouter.ai/api/v1
export DEEPSEEK_MODEL=deepseek/deepseek-chat
export DEEPSEEK_TEMPERATURE=0
```

The host application is responsible for secret storage, user authentication,
authorization, rate limiting, and deployment controls.

After moving the key into `providers.py`, the live example was executed with
`DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, and `DEEPSEEK_BASE_URL` explicitly removed
from the process environment. It authenticated through the bundled fallback,
confirmed the fictional extracted age, returned `Planning status: ready`, and
produced a locally validated fourteen-day plan.

## Scope and limitations

This is an introductory fitness-support component, not a diagnostic system,
medical-clearance service, or emergency service. The shipped exercise catalog is
deliberately small. External provider behavior can change, so deployments should
keep local validation enabled and rerun the live fictional-data test after model,
gateway, prompt, or schema changes.
