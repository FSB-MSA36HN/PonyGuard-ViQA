# PonyGuard reliability remediation plan v2

## Objective

Raise PonyGuard from the current live diagnostic result of **11/26 passing** to
a reliable evidence-first system. The target is not to make it answer more
often. The target is to make each action correct:

- `ANSWER` only when the retrieved text establishes the requested relation.
- `ASK` only when the request itself lacks a required meaning slot.
- `ABSTAIN` when the request is clear but the corpus evidence is absent,
  incompatible, contradicted, or insufficient.

All work stays within the current corpus, FAISS retriever, three-system
comparison and immutable final-test protocol. No entity-specific rules, answer
tables, or question-pattern exceptions are permitted.

## Evidence from the latest live run

The run used `Qwen/Qwen3-8B-MLX-4bit` on every stage because Gemini returned
`429`. It completed all 26 cases but produced:

| Group | Expected | Passed | Main failure |
| --- | ---: | ---: | --- |
| Direct `ANSWER` | 10 | 3 | direct evidence became `ASK`/`ABSTAIN` |
| `ABSTAIN` | 8 | 4 | clear unsupported requests became `ASK`; one mismatch became `ANSWER` |
| `ASK` | 8 | 4 | missing-context requests became `ABSTAIN` |

The full source of truth is
`runs/ponyguard/ponyguard_behavioral_live_predictions.jsonl` and its summary
is `reports/PONYGUARD_LIVE_BEHAVIORAL_REPORT.md`.

## Root-cause map

### RC1 — Intent extraction is overloaded and unstable

One large semantic prompt must simultaneously parse the request, decide
clarity, evaluate retrieved evidence, select a support quote, explain gaps,
and sometimes format JSON. With the fallback model it frequently omits fields
or invents optional missing slots. The pipeline then sees a partial contract:

- clear question → false `ASK` (`country`, `location`, `time`, `scope`);
- genuinely incomplete question → false `ABSTAIN` because no slot survives;
- unsupported clear question → false `ASK` instead of `ABSTAIN`.

### RC2 — A literal quote does not prove semantic relation alignment

The current support validator checks citation/quote/answer occurrence, but a
model can still label an incompatible relation as a match. This caused the
attribute-mismatch answer `tinh bột`. Conversely, a support can be valid while
the model's prose field says evidence is insufficient, causing false
abstention.

### RC3 — Evidence objects are not the single source of truth downstream

Extractor support, generated answer grounding, and claim verification can
disagree. Location/date/count cases had a direct support in trace but failed in
a later stage. The pipeline must not let a style-generation failure erase an
already validated answer fact.

### RC4 — Retrieval failures and evidence-policy failures are mixed together

Some paraphrases retrieve irrelevant chunks; others retrieve the right chunk
but still abstain. Current reports do not record expected source coverage, so
the team cannot tell whether to tune FAISS, query formulation or decision
logic.

### RC5 — Permitted inference has no production-grade proof path

The code can validate a simple arithmetic proof, but the prompt/pipeline do
not reliably route a valid two-operand calculation to that contract. Derived
answers therefore abstain or risk failing literal grounding.

### RC6 — The production provider is not actually the provider under test

Gemini `429` makes every live measurement a Qwen fallback measurement. This
changes JSON quality, latency and decisions. The system must report provider
state explicitly and must not treat fallback results as Gemini validation.

## Design invariants

1. Intent decides `ASK`; evidence never invents ambiguity after a clear intent
   was established.
2. A support must prove entity, attribute, role/direction, scope and premise
   status. Word overlap is never sufficient.
3. A validated fact is immutable: later prose generation may improve wording,
   but may not replace its answer/citation/relation.
4. A failure to parse model JSON is a recoverable format failure, not semantic
   evidence. One bounded repair is allowed; then the action fails closed.
5. Clarification changes only intent. The factual answer always requires a new
   retrieval/evidence pass.
6. All thresholds, prompts, schemas and provider choices are versioned in run
   metadata. The frozen final benchmark is read-only.

## Milestone 1 — Separate intent from evidence

### Change

Introduce a dedicated `IntentAnalyzer` stage before retrieval. It receives only
the user request and returns a strict JSON schema:

```json
{
  "resolved_slots": [{"name": "entity", "value": "...", "question_span": "..."}],
  "missing_slots": [{"name": "...", "why_required": "..."}],
  "requested_relation": {"subject": "...", "predicate": "...", "object_or_value": "..."},
  "answer_type": "...",
  "question_complete": true
}
```

Use provider-native structured output / JSON schema where available. Validate
all slot names, types and spans locally. If parsing fails, perform exactly one
intent-only repair; if it fails again, return a transparent system-format
abstention rather than treating the request as clear.

### Decision rule

- Non-empty validated `missing_slots` → `ASK` immediately; retrieval is not
  used to guess the missing meaning.
- Empty validated `missing_slots` → question is clear; no later stage may
  change it to `ASK`.
- A slot is allowed to be missing only when the intent schema cannot bind it to
  a span in the request. Optional specificity must not become a missing slot.

### Tests

Cover all eight slots, explicit subject/attribute questions, pronouns, terse
questions, comparisons, time references and multi-part requests. Assert both
the action and a non-echo clarification that identifies the known subject plus
the missing information.

## Milestone 2 — Build relation-bound evidence facts

### Change

Replace free-form support with an `EvidenceFact` contract produced after
retrieval:

```json
{
  "chunk_id": "...",
  "evidence_quote": "...",
  "answer_value": "...",
  "entity_binding": {"question_span": "...", "evidence_span": "..."},
  "relation_binding": {
    "question_relation": "...",
    "evidence_relation": "...",
    "status": "MATCH|CONTRADICTED|UNSTATED"
  },
  "scope_binding": {"time": "MATCH|UNSPECIFIED|MISMATCH", "population": "..."},
  "support_type": "DIRECT|SIMPLE_INFERENCE"
}
```

Use a small relation-verification prompt over the already-selected candidate
quote rather than asking the large evidence prompt to self-approve. Locally
validate IDs, literal spans, candidate value and enum fields. A missing or
invalid relation status is rejected.

### Decision rule

- `MATCH` + valid direct fact → candidate `ANSWER`.
- `CONTRADICTED` → `ABSTAIN`, explaining the source states a different
  relation; never silently correct and answer another question.
- `UNSTATED`, mismatch or no fact → `ABSTAIN`.

### Tests

Generic actor/patient reversal, direction reversal, attribute mismatch,
population mismatch, time mismatch and same-entity/different-value tests. Use
synthetic fixtures only; no production exception lists.

## Milestone 3 — Make validated facts authoritative

### Change

Create one immutable `AnswerPlan` from `EvidenceFact`:

```json
{"answer_value":"...","citation_chunk_ids":["..."],"evidence_quote":"...","support_type":"DIRECT"}
```

The response writer receives the plan and may add a short connective phrase,
but output is validated back against the plan. If prose fails validation, emit
the canonical `answer_value` plus its evidence quote instead of abstaining.
Claim verification consumes the same plan and cannot add claims outside it.

### Tests

Force a writer to paraphrase a name, omit a list member, alter a number and
produce malformed JSON. Every case must preserve the canonical fact or abstain
with `invalid_grounding`; none may discard an otherwise valid direct fact.

## Milestone 4 — Evidence recovery and retrieval diagnosis

### Change

For clear requests without a valid fact:

1. Record whether top-k contained the fixture's expected evidence chunk.
2. Run one bounded evidence-fact extraction/relation check over the existing
   top-k.
3. Only if expected relation evidence is absent, issue one generic query from
   intent's resolved entity + requested relation, merge unique chunks, then
   repeat extraction once.
4. Stop. Do not add recursive self-questioning or unbounded retrieval loops.

This keeps the same FAISS index/model but makes the recovery pathway explicit
and measurable.

### Reporting

Report `retrieval_miss`, `evidence_extraction_miss`, `relation_rejection`,
`writer_failure`, and `claim_gate_failure` separately. Refusal text may cite
only a relation-checked observation; otherwise it must say no matching source
was retrieved, not quote irrelevant material.

### Tests

Paraphrase, spelling/diacritic variation, a known-source retrieval miss and an
irrelevant top-k result. Tune only on dev/validation.

## Milestone 5 — Finish SIMPLE_INFERENCE safely

### Change

Route a clear request whose relation requires arithmetic or a one-hop join to
an `InferencePlan` with two literal operands, a permitted operation, unit and
result. The deterministic validator recomputes the result and checks shared
entity/time/population scope. The final answer names it as a calculation from
the cited values.

### Rule

Allow only `sum`, `difference`, `ratio`, and explicit one-hop comparison. Any
external assumption, hidden conversion, missing unit or third fact is
`ABSTAIN`.

### Tests

Valid difference/ratio, incompatible units, hidden denominator, conflicting
operands and unsupported multi-hop join.

## Milestone 6 — Provider and latency discipline

### Change

1. Record `requested_provider`, `actual_provider`, fallback reason and retry
   count for every stage.
2. Respect Gemini retry-after/backoff for transient `429/503` once before
   fallback; never silently call a different model without trace metadata.
3. Benchmark Gemini and local Qwen separately. A result is only comparable to
   results from the same configured provider/model.
4. After correctness passes, reduce calls: intent parse once, direct evidence
   fast path once, skip writer/claim verifier for `ASK`/`ABSTAIN`, and invoke
   recovery only after a verified miss.

### Acceptance

Measure both warm and cold latency. Target a substantial reduction from the
current 32.3-second median fallback latency without reducing action or
grounding scores.

## Milestone 7 — Evaluation and release gate

### Diagnostic fixture upgrades

Add expected action, expected evidence chunk IDs, expected answer matcher,
expected missing slots, relation class and multi-turn continuation to every
development fixture. Keep it separate from final test.

### Correctness metrics

- action accuracy by `ANSWER` / `ASK` / `ABSTAIN`;
- direct-answer correctness and citation/relationship validity;
- false answer on contradiction/mismatch;
- false abstain on direct evidence;
- false ask on clear questions;
- ASK slot precision/recall and clarification quality;
- inference-proof validity;
- retrieval recall by evidence type;
- per-stage latency and provider/fallback rate.

### Exit criteria

1. `100%` deterministic contract/regression tests pass.
2. No relation-reversal or attribute-mismatch diagnostic returns `ANSWER`.
3. No clear direct-evidence diagnostic returns `ASK`.
4. Every `ASK` names the known subject and the exact missing slot; it never
   echoes the question.
5. The live development suite reaches at least `90%` action correctness with
   zero unsupported `ANSWER` cases on the selected provider, then is repeated
   for fallback provider and reported separately.
6. Only after config/prompt/provider are frozen may the immutable final test be
   run once.

## Delivery sequence

Implement and test Milestones 1–3 first; they address every current critical
wrong-action class. Run the live suite and inspect traces. Implement Milestone
4 only for measured retrieval misses, Milestone 5 for inference failures, then
Milestone 6 after correctness is stable. Do not tune against the frozen test at
any point.
