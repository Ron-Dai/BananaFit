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
2. Authenticated using a runtime environment variable.
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
120 passed in 17.37s
All checks passed!
PUBLIC_DEMONSTRATION_KEY_CONFIGURED
```

The test suite includes YAML parsing, branching and readiness rules, answer
normalization, consent enforcement, provider transport failures, plan validation,
feedback-driven revision, storage, deletion, imports, exports, and public service
methods. HTTP unit tests use synthetic credentials and mocked transports.

## Credential handling

A user-authorized free demonstration key is stored in the tracked `.env` file so
the example works immediately after cloning. The example loads it without
overriding any environment variables supplied by the host. Production deployments
should override `DEEPSEEK_API_KEY` with their own managed credential. The OpenRouter
example uses:

```bash
export DEEPSEEK_BASE_URL=https://openrouter.ai/api/v1
export DEEPSEEK_MODEL=deepseek/deepseek-chat
export DEEPSEEK_TEMPERATURE=0
```

The host application is responsible for secret storage, user authentication,
authorization, rate limiting, and deployment controls.

## Scope and limitations

This is an introductory fitness-support component, not a diagnostic system,
medical-clearance service, or emergency service. The shipped exercise catalog is
deliberately small. External provider behavior can change, so deployments should
keep local validation enabled and rerun the live fictional-data test after model,
gateway, prompt, or schema changes.
