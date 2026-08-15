# Project Policy

## Dynamic reasoning only

Production code must not hard-code a domain fact, entity, answer, language phrase, question pattern, or special-case outcome. A new observed question is a regression test, not a rule to add to the pipeline.

Every `ASK`, `ANSWER`, or `ABSTAIN` decision must be produced from the question's semantic slots and retrieved evidence. `ASK` requires a missing schema slot; `ANSWER` requires validated evidence; `ABSTAIN` requires a recorded evidence or scope gap. A follow-up answer must be retrieved and checked again; user clarification is never factual evidence.

The permitted fixed policy is deliberately small: the versioned output schema, its finite slot/action enums, literal citation validation, conflict checks, and generic fallback wording when structured generation fails. Dataset examples and tests may use concrete facts only as fixtures; they must not change runtime behavior.

When adding a capability, first extend the schema or prompt generically, then add diverse tests. Do not add an entity-specific regex, retrieval query, prompt example, answer, option list, or UI branch.
