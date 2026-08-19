# PonyGuard live reliability handoff

## Mission

You are continuing work on PonyGuard-ViQA. Improve the production PonyGuard
pipeline from evidence and test results; do not patch individual questions.
The required behavior is:

- `ASK` only when the question itself lacks a required semantic slot.
- `ANSWER` only when retrieved text proves the requested relation and the
  answer, citation and literal evidence quote are valid.
- `ABSTAIN` when the question is clear but the retrieved evidence is absent,
  mismatched, contradictory, or insufficient.

The current problem is mixed reliability: several direct questions with
retrieved evidence still false-`ABSTAIN`, four true missing-slot cases are
false-`ABSTAIN`, and one missing-time case is an unsafe `ANSWER`. Do not claim
success until that unsafe answer is removed and a new live run confirms it.

## Non-negotiable policy

Read [`PROJECT_POLICY.md`](../PROJECT_POLICY.md) before editing.

- Never hard-code an entity, domain fact, answer, language phrase, question
  pattern, or observed case in production code.
- A diagnostic question belongs in a fixture/test, not in a runtime branch.
- Do not alter `data/benchmark/test.jsonl`, its manifest, corpus, retriever,
  or the main-comparison split while tuning this work.
- Do not make user clarifications factual evidence: after clarification,
  retrieve and verify again.
- Preserve the common output schema and comparable Basic RAG / Prompt-Safe
  RAG / PonyGuard setup.

## Current repository state

Important files:

| Purpose | File |
| --- | --- |
| Pipeline and evidence validation | `src/ponyguard_viqa/pipelines.py`, `src/ponyguard_viqa/core.py` |
| LLM providers / fallback | `src/ponyguard_viqa/llm.py` |
| Intent prompt | `prompts/intent_analyzer_v2.txt` |
| Evidence prompt | `prompts/semantic_evidence_v5.txt` |
| Relation prompt | `prompts/relation_verifier_v1.txt` |
| Production policy/config | `configs/ponyguard.yaml`, `PROJECT_POLICY.md` |
| Deterministic tests | `tests/test_behavioral_matrix.py`, `tests/test_grounding.py`, `tests/test_ambiguity.py`, `tests/test_reasoned_evidence.py` |
| Live fixture | `data/diagnostics/ponyguard_behavioral_live.jsonl` |
| Live runner/report | `scripts/run_system.py`, `scripts/report_live_diagnostics.py` |
| Existing remediation design | `docs/PONYGUARD_RELIABILITY_FIX_PLAN_V2.md` |

The current production path enables `intent_first: true`. It performs intent
analysis before retrieval. Clear questions then retrieve, extract evidence,
verify relations, and may use one bounded recovery/clarification-adjudication
path when no validated support is found. Valid direct facts are emitted through
the canonical answer plan without writer/claim calls.

## What was tested

### Fast deterministic tests

These use scripted models and validate contracts, not model intelligence:

```bash
make test
make behavior-test
```

They last passed at **103 tests** and **29 behavioral tests**, respectively.
Re-run after every code change.

### Live behavioral test

This invokes the actual retriever and active provider on 26 development-only
cases: direct answer forms, a simple inference, relation reversals,
unsupported questions, and eight kinds of missing context.

```bash
make live-behavioral
```

It writes:

- `runs/ponyguard/ponyguard_behavioral_live_predictions.jsonl`
- `runs/ponyguard/ponyguard_behavioral_live_predictions.metadata.json`
- `reports/PONYGUARD_LIVE_BEHAVIORAL_REPORT.md`

Inspect individual traces before proposing a fix. Every trace records intent,
retrieved chunks, support rejections, decision reason, per-stage provider,
calls and latency.

This suite is a diagnostic development suite, **not** the frozen benchmark.
It is acceptable to add generic, diverse regression fixtures here.

## Latest live result (must be the starting evidence)

Report timestamp: **2026-08-16 13:20 +07**.

| Metric | Result |
| --- | ---: |
| Executed | 26 / 26 |
| Passed | **17 / 26** |
| Failed | 9 / 26 |
| Actions | 7 `ANSWER` / 3 `ASK` / 16 `ABSTAIN` |
| Grounded `ANSWER` | 7 / 7 valid citation + literal quote |
| Median latency | 15.55 s |
| Mean latency | 22.04 s |
| Mean LLM calls | 4.12 (107 total) |

All eight unsupported/reversed/mismatched safety cases pass as `ABSTAIN`.
The latest run is **not acceptance-complete** because `live_ask_time` answered
despite an unresolved time reference.

Gemini was temporarily unavailable (`429`) on the live run. All 100 LLM stage
calls therefore used local `Qwen/Qwen3-8B-MLX-4bit`. Do not call this a Gemini
result. Provider/model and fallback reason must remain visible in reports.

## Confirmed root causes

1. **`live_answer_person`: retrieval miss.** The source containing the full
   answer is outside the bounded retrieved set (approximately rank 15); the
   selected chunk supports a different, partial allegation. This is not a
   validator-relaxation candidate.
2. **`live_answer_reason` and `live_simple_inference`: relation rejection.**
   Their expected source is in top-1, but the local verifier labels a causal
   relation / arithmetic operands `CONTRADICTED` before the valid proof path
   can accept it.
3. **`live_answer_definition`: evidence extraction miss.** Retrieval occurs
   after a malformed missing-slot flood is deferred, but extraction/recovery
   produces no support.
4. **`live_ask_attribute`, `live_ask_entity`, `live_ask_country`, and
   `live_ask_scope`: intent/clarity misses.** They proceed to retrieval with
   no missing requirements and finish `ABSTAIN`.
5. **`live_ask_time`: unsafe intent miss.** The unresolved time reference is
   not marked missing, then a retrieved fact is accepted as `ANSWER`.
6. **Fallback provider remains the quality and latency bottleneck.** Mean
   local-stage work is 4.12 calls per question; retrieval is normally much
   smaller after warm-up.

## Changes already retained

- The clarity guard treats a large, internally inconsistent missing-slot set
  as malformed rather than immediately emitting an ungrounded `ASK`.
- A relation-verified support with a literal candidate answer can repair a
  nonliteral model quote to a literal source excerpt. This preserves the
  citation contract; it does not relax relation verification.
- Regression coverage was added for both contracts. `make test` is 103 passed
  and `make behavior-test` is 29 passed.

## Rejected experiment (do not reintroduce without new evidence)

An expanded recovery query (`top_k * 3`) and broad intent/relation prompt
rewrite caused a **14/26** live run and introduced unsafe `ANSWER`s for an
unsupported comparison and missing country. It was fully rolled back. The
current 17/26 result is the verified baseline after that rollback.

Do **not** conclude that retrieval is wrong until checking whether the
expected source chunk is in top-k. A source in top-k plus no validated support
is an extraction/validator issue, not a FAISS issue.

## Required debugging workflow

For each failing category, inspect a representative JSONL record before
editing:

1. Is the expected source among `retrieval.chunk_ids`?
2. Did `semantic_evidence` produce a candidate support/quote/value?
3. Which local validation rule rejected it, exactly?
4. Was the question declared incomplete by intent? Are the claimed missing
   slots truly absent from the user text?
5. Did a later writer/claim stage discard a previously valid fact?
6. Record the root-cause class: `retrieval_miss`, `intent_miss`,
   `evidence_extraction_miss`, `relation_rejection`, `writer_failure`,
   `claim_gate_failure`, or `provider_format_failure`.

Do not modify a prompt or validator until this chain is known for at least one
failing direct-answer case and one failing missing-slot case. Re-inspect the
current row before editing because local fallback output can vary across runs.

## Improvement order

### 1. Repair intent as an independent bounded contract

Intent decides only whether to `ASK`, before retrieval. Validate the intent
schema locally: allowed slots/types, non-empty values, and value/span binding
to the user question. Optional specificity must not become a missing required
slot. On a valid clear intent, no later evidence stage may turn it into `ASK`.

For an `ASK`, require a meaningful clarification: identify the resolved part
of the question and the missing semantic dimension; it must not echo the
question or be a vague phrase. Keep this generic and schema-driven.

### 2. Repair direct evidence acceptance without weakening relation safety

Use an explicit `EvidenceFact` / `AnswerPlan` built from the selected quote:

- validate chunk ID and literal quote;
- validate answer value against the quote;
- separately validate entity and relation direction against the **full source
  chunk**, not only a model-provided imperfect span;
- use an enum result: `MATCH`, `CONTRADICTED`, `UNSTATED`;
- accept a direct fact only on `MATCH`;
- reject reversed actor/patient, different attribute, wrong population/time,
  and unsupported premise on `CONTRADICTED` or `UNSTATED`.

The repair must not revert to word-overlap-only matching. It must be a generic
semantic relation check. If a direct fact passes, make its answer, quote and
citation immutable: response generation may phrase it, but cannot discard or
replace it. A writer failure should emit the canonical validated answer plan.

### 3. Add one bounded inference proof path

For `SIMPLE_INFERENCE`, require explicit operands, operator, calculation and
source quotes. Validate arithmetic deterministically. Any additional premise,
world knowledge, unclear scope, or unsupported join remains `ABSTAIN`.

### 4. Diagnose retrieval separately, then optimize latency

Only after intent/evidence are correct:

- record expected-source presence for development fixtures;
- do at most one generic, intent-derived re-query if clear intent had no
  valid fact; no recursive loops;
- cache loaded retriever/model and measure stage timings;
- skip relation/writer calls if there is no candidate fact;
- skip all evidence calls for a validated `ASK`.

Avoid new databases, services or multi-agent loops. The current FAISS index
and cache are sufficient until profiling proves otherwise.

## Acceptance criteria

Before claiming a fix:

1. `make test` and `make behavior-test` pass.
2. `make live-behavioral` completes all 26 cases.
3. Inspect every failed live row, not only the aggregate report.
4. No direct `ANSWER` is accepted without valid citation + literal evidence
   quote + relation match.
5. No clear direct-answer fixture is turned into `ASK` merely because of
   optional country/location/time/scope.
6. True terse/missing-slot fixtures receive meaningful non-echo `ASK`.
7. Unsupported/reversed/mismatched fixtures remain `ABSTAIN`.
8. Report action distribution, provider/fallback status, per-stage latency,
   LLM calls, and root-cause breakdown. State explicitly if Gemini is not
   available and results are fallback-only.
9. Do not tune on or edit frozen final benchmark files. Run the final benchmark
   only after diagnostic config is frozen.

## Suggested first task

Start with `live_ask_time` and one of `live_ask_attribute` /
`live_ask_entity`: trace intent output and clarity-adjudication output before
changing a prompt. The first fix must make `ASK` depend on a schema-bound
missing slot, not a language-specific pattern. Then separately trace
`live_simple_inference` through relation verification and deterministic proof
validation. Do not broaden retrieval or weaken `MATCH` requirements merely to
recover `live_answer_person`.
