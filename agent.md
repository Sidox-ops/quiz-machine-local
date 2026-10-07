# Local quiz model contract

This file documents the local pipeline. It is not sent wholesale to Ollama.
Stage-specific prompts and schemas live next to their orchestration in
`backend/quiz_engine.py`; deterministic rules live in
`backend/quiz_reliability.py`.

## Authority

Microsoft Learn evidence in the selected certification/domain/objective scope is
the factual authority. Model memory cannot override it. When the available local
corpus cannot support one objectively best answer, generation stops for that
candidate.

## Stages

1. Select one learning objective and retrieve one to three semantic chunks.
2. Generate only the question, four stable `opt_*` options, the correct option
   ID, and supporting source IDs.
3. Validate the candidate against the same evidence. This stage may use model
   thinking, but the trace is discarded and never becomes pipeline context.
4. Freeze and fingerprint the canonical question.
5. Generate ID-bound capability rationales for the already-fixed answer.
6. Assemble learner-facing explanations from canonical option text in code.
7. Reject any fingerprint, source, option, answer, explanation, or presentation
   order mismatch before persistence and again before scoring.

## Non-negotiable rules

- A/B/C/D are presentation labels derived from list position, never answer keys.
- Shuffling changes only `presentation_option_ids`, never option objects or IDs.
- Explanations cannot choose or mutate the correct answer.
- Model-produced rationales cannot name option letters, option IDs, products, or
  option text; the server binds them to frozen text.
- Duplicate/equivalent service aliases, unsupported evidence, cross-scope chunks,
  ambiguous generic vector-search stems, and stale explanations are rejected.
- Only the failed candidate or explanation is retried, with small bounded loops.
