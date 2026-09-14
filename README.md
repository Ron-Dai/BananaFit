This is a project aimed to point out inaccurate posture while working out. the feature we should have:

* recognizing what is the equipment for
* explain the usage, what muscle does it train
* plan workout routine based on equiment scanned and your plan
* warmup advice
* recognizing user's posture(mediapipe)
* give out professional advice simultaneously

## Integrated application backend

`server.py` now starts the existing camera pipelines together with account, questionnaire,
workout-plan, calendar, Personal exercise, workout-session, and live coach-metric APIs. The React
frontend keeps its existing visual design and reads these APIs through the development proxy.

See [`controller/README.md`](controller/README.md) for the architecture, database relationships,
API response contracts, local setup, integration guidance, and verification commands.
