# PonyGuard Reasoned Evidence Agent — Implementation Plan

## Objective

Upgrade PonyGuard from a binary evidence gate to a corpus-grounded reasoning agent. It may inspect its own evidence coverage with bounded retrieval probes, ask the user only when the request is genuinely underspecified, and explain every refusal with cited evidence and concrete coverage gaps.

The system remains corpus-only. It does not use web search, hidden free-form reasoning, or model knowledge as evidence.

## Policy

1. `ASK`: a missing entity, attribute, or user-selectable scope makes the request incomplete.
2. `ABSTAIN`: the request is clear but evidence has no verified answer, is temporally stale, covers only a narrower population, or conflicts.
3. `ANSWER`: verified quotes match entity, requested attribute, population scope, and requested time; only direct/simple inference is permitted.
4. A narrower fact is never silently substituted for a broader request. It becomes a grounded explanation and optional safe rephrase.

For “Hà Nội có mấy học sinh ở tất cả các trường học hiện nay?”, `982.579` is useful supporting evidence but not an answer: it is explicitly for primary/secondary/high-school students in 2009.

## Pipeline v5

```text
requirement + scope extraction
→ deterministic ambiguity gate
→ main retrieval
→ scope audit against literal evidence quotes
→ bounded coverage probes (maximum two retrieval-only self-queries)
→ decision planner
→ ANSWER or grounded refusal / ASK
→ claim verifier and final gate for ANSWER only
```

## Changes

### Requirement contract

Add `population_scope`, `time_scope`, and `inclusion_constraints` to `Requirement`. Deterministic patterns detect `hiện nay/hiện tại`, explicit years, and `tất cả/toàn bộ/mọi`; these constrain an advisory LLM extraction rather than relying on it.

### Evidence scope audit

Create `evidence_scope_auditor_v1.txt`. Every support includes a literal quote, candidate answer, evidence time/population, match flags, and mismatch reasons. The existing quote/candidate validator remains mandatory.

### Coverage probes

When a verified support is close but has time/population mismatch, run at most two deterministic retrieval probes created from the original entity/attribute/scope. Store their query strings and chunks in trace. They may corroborate the coverage gap, but cannot create an answer unless re-audited and validated.

### Grounded refusal

Use deterministic rendering rather than a free-form LLM explanation:

- `reason_summary`
- `supported_facts` with chunk IDs and quotes
- `coverage_gaps`
- `safe_rephrase`

The same content is returned in the `ABSTAIN` answer and visible in the UI.

### UI

For `ABSTAIN`, render a “Why this cannot be confirmed” panel containing the source-supported partial fact, scope/time gaps, and safe rephrase. For `ASK`, retain contextual options. `ANSWER` retains grounding and claim verification.

## Tests and metrics

Regression cases cover Hanoi 982,579 (broad/current → `ABSTAIN`; school-year 2009 → `ANSWER`), clear no-evidence refusal, ambiguous scope `ASK`, and no repeated follow-up clarification.

Report scope match rate, temporal match rate, grounded refusal rate, explanation grounding rate, useful rephrase rate, false answer under scope mismatch, coverage-probe count, latency, and token overhead. Do not alter frozen test data; tuning is limited to dev/validation.

## Acceptance criteria

The Hanoi broad/current question cites the 2009 school-level statistic and explicitly says why it cannot be used as a present-day all-schools total. A narrow 2009 question answers with the cited number. All existing grounding, ASK, and frozen split tests pass.
