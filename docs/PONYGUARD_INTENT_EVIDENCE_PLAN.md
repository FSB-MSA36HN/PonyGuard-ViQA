# PonyGuard intent/evidence remediation plan

Baseline: live behavioural **17/26**, report timestamp 2026-08-16 13:20 +07,
predictions in `runs/ponyguard/ponyguard_behavioral_live_predictions.jsonl`.
This document is the guide for the current work. Follow it in order; do not
skip to a later change because an earlier one is slow.

## 1. Root-cause classification (traced, per case)

Derived by reading every failing row's `trace.requirements`,
`trace.evidence.support`, `trace.evidence.support_rejections` and
`retrieval.chunk_ids` — not the aggregate report.

| Case | Class | Decisive trace evidence |
| --- | --- | --- |
| `live_answer_person` | `retrieval_miss` | Top-9 contains only the partial `gồm Rousseau` allegation; the gold source is outside the bounded set. `CONTRADICTED` is the correct verdict for the chunk supplied. |
| `live_answer_definition` | `retrieval_miss` | All 9 retrieved chunks are unrelated. `support: []` with zero rejections is the extractor behaving correctly on absent evidence. |
| `live_simple_inference` | `relation_rejection` (structural) | Operands literal and correct, `inference_proof` populated, arithmetic exact. Rejected on the *composed* relation verdict before the proof is ever validated. |
| `live_answer_reason` | `relation_rejection` (structural) | Same shape: a causal/derived `evidence_relation` is never literally stated, so it can only score `CONTRADICTED`. |
| `live_ask_time` | `intent_miss` (unsafe) | An unresolved temporal deictic collapses to `time_scope: UNSPECIFIED` with `missing_requirements: []`; a retrieved fact is then answered. |
| `live_ask_entity` | `intent_miss` | A pronoun is accepted as a filled `entity`. |
| `live_ask_attribute` | `intent_miss` | `requested_attribute` is filled with a value that is not a span of the question. |
| `live_ask_country` | `intent_miss` (underspecification) | The entity span is self-contained but names a class whose instance is unselected. |
| `live_ask_scope` | `intent_miss` (underspecification) | Both slots are self-contained spans; the set boundary is unbounded. |

**Correction to `docs/AGENT_HANDOFF_LIVE_RELIABILITY.md`:** its confirmed root
cause #3 classifies `live_answer_definition` as an evidence-extraction miss.
The trace shows a retrieval miss. Two of the nine failures are therefore not
reachable from intent or evidence work, so the ceiling without touching
retrieval is **24/26**.

## 2. Shared architectural bottlenecks

Three findings that are measurable in the trace, not case-specific.

### B1 — the only working `ASK` signal is an empty slot string

All three passing `ASK` cases emit `entity: ""` and are caught by the
deterministic empty-slot rule in `enforce_requirement_contract`. All five
failing cases fill every slot with a token lifted from the question and emit
`missing_requirements: []`. The model-emitted `question_complete` judgement has
**0/5 recall** on them, and its false positives are what forced the
"more than two alleged gaps → clear them all" suppression in
`apply_clarity_guard`.

The contract asks the model for one global judgement ("is this question
complete?") that it cannot make reliably. The repair is to ask instead for a
per-slot, locally decidable claim bound to a verbatim span of the question, and
to compute `question_clear` in Python from those claims.

### B2 — `inference_proof_is_valid` is unreachable on the live path

`PonyGuard.inference_proof_is_valid` is a correct deterministic arithmetic
validator. It never executes: `validated_supports` rejects on
`premise_status != SUPPORTED` first, and a `SIMPLE_INFERENCE` support can never
earn `MATCH` because the relation verifier is asked whether the source states
the **derived** relation. No source states a derived relation — that is what
makes it an inference. The verifier is being asked the wrong proposition.

### B3 — two branches spend LLM calls and change no decisions

`clarification_adjudication` ran on 14 questions and returned `decision: null`
**14/14**, including on all four fixable `ASK` cases. `fact_recovery` ran on
~14 and recovered **0** supports. Roughly 28 of 107 calls changed nothing.

## 3. Sequencing rule

Changes land **one at a time**, each with its own deterministic regression test
and its own live run. A previous bundled experiment regressed 17 → 14 and
required a full rollback; attribution is worth the extra live runs.

After every change, in order:

```bash
make test && make behavior-test
```

then, only on green:

```bash
make live-behavioral
```

then inspect all 26 traces, not the aggregate.

## 4. Change A — per-slot intent contract with deterministic span binding

Targets `live_ask_time` (removes the unsafe `ANSWER`), `live_ask_entity`,
`live_ask_attribute`. Addresses **B1**.

Add a `slot_bindings` array to the intent schema. Each entry names a schema
slot, a **verbatim span of the question**, and a status from a closed enum:

- `RESOLVED` — the span fixes this dimension from the question alone.
- `REFERENTIAL` — the span points outside the question (anaphor, deictic,
  unselected reference) and needs an antecedent.
- `ABSENT` — the question states no such dimension.

Python then decides, in `core.intent_slot_bindings`:

- a binding is considered only when its slot is in `MISSING_REQUIREMENT_SLOTS`,
  its status is in the enum, and its span occurs literally in the question;
- `REFERENTIAL` with a literal span → the slot is unresolved;
- `ABSENT` on a required slot (`entity`, `requested_attribute`) → unresolved,
  matching the existing empty-string contract;
- `ABSENT` on any optional dimension → **never** unresolved.

That last rule is what protects acceptance criterion 5: the nine direct-answer
cases carry `ABSENT` time/country/location, not `REFERENTIAL`, so they cannot
be turned into `ASK`.

`apply_clarity_guard` must treat span-bound slots as evidence rather than
allegation:

- the flood-suppression rule applies only to unbound model-claimed slots;
- the "an extracted slot cannot also be missing" rules do not drop a slot whose
  binding says it is referential — that is exactly the pronoun case.

**Fail-safe direction.** A malformed, absent or non-literal binding falls back
to current behaviour. The change can only move `ABSTAIN → ASK` when the model
produces a literal span it labels unresolved, so it cannot silently create the
false-`ASK` drift that sank the earlier experiment.

**Out of scope for A:** `live_ask_country` and `live_ask_scope`. Both need an
underspecification judgement on a self-contained span, which risks false `ASK`
on the direct cases. Hold until A's live run shows no drift.

Prompt edit is additive: the new field plus its enum definition. No rewrite of
the existing clarity guidance.

Expected: **20/26**, unsafe `ANSWER` removed.

### 4.1 Run log — Change A, first live run

Result: **17/26**, unchanged, and **not a valid comparison**. Findings, in order
of importance:

1. **Provider mixing invalidates cross-run comparison.** The baseline ran 100%
   local `Qwen3-8B-MLX-4bit`. This run hit both `429` and `503` and executed
   mixed Gemini/local. `live_answer_percentage` flipped PASS → FAIL and
   `live_answer_reason` FAIL → PASS — neither is reachable by span binding.
   Diagnostic runs must pin one provider (`make live-behavioral MODEL=local`).
2. **The span-binding mechanism works; the model's use of it does not.** The
   contract is emitted and recorded in `trace.requirements.slot_bindings`, but
   recall on true referentials is **2/4**: `Họ` and `ở đó` were labelled
   `REFERENTIAL`, while a subject pronoun was labelled `RESOLVED` and a
   temporal deictic produced **no binding at all** — the dimension was simply
   never enumerated.
3. **One real regression, now fixed deterministically.** An interrogative
   (`Khi nào …?`) was labelled `time: REFERENTIAL`, turning a passing `ANSWER`
   into `ASK`. The requested value is not a missing input. `ANSWER_TYPE_SATISFIES`
   in `core.py` now suppresses a referential claim on the dimension the answer
   type shows the question is asking for. This is a closed-enum table over two
   schema fields, not a wording rule.

**Revised judgement on B1.** The diagnosis stands — the global `question_complete`
judgement is the bottleneck — but Change A substituted a *smaller* model
judgement, not a *deterministic* one, and a smaller unreliable judgement is
still unreliable. Only the parts that moved into Python (span literality,
required-slot absence, interrogative suppression) are actually dependable.

**Consequence for the next step.** Do not iterate further on referentiality
prompting until a pinned-provider run establishes a stable baseline and the
per-case variance is known. Two runs of different code both scored 17/26 while
four cases flipped in each direction; at that noise level a 3-case improvement
is unfalsifiable. Establishing measurement comes before Change B.

### 4.2 Run log — Change A, provider-pinned run

`make live-behavioral MODEL=local`, 100% local `Qwen3-8B-MLX-4bit`, zero
fallback — directly comparable to the 17/26 baseline.

Result: **18/26**, 100 LLM calls (3.85/question, down from 4.12), median 14.61 s,
mean 21.25 s. Actions 7 `ANSWER` / 5 `ASK` / 14 `ABSTAIN`.

**Change A's mechanism fired on 0 of its 3 target cases.**

| Target | Emitted binding | Outcome |
| --- | --- | --- |
| `live_ask_time` | no `time` binding at all | still unsafe `ANSWER` |
| `live_ask_entity` | `entity` span labelled `RESOLVED` | still `ABSTAIN` |
| `live_ask_attribute` | `requested_attribute` span labelled `RESOLVED` | still `ABSTAIN` |

The three deltas against baseline are **all model variance on paths Change A
does not touch**: `live_answer_reason` FAIL → PASS (relation verifier),
`live_ask_country` FAIL → PASS (empty-slot path; the intent call returned no
bindings at all), `live_answer_list` PASS → FAIL (the model alleged a missing
`country` on the legacy `missing_requirements` field; `apply_clarity_guard`
treats that identically before and after Change A).

The interrogative guard **is** confirmed working live: `live_answer_time`
carries `time: REFERENTIAL` with `interrogative: true`, is suppressed, and
answers correctly. It repairs a regression Change A introduced; it is not a
gain over baseline.

**Verdict on Change A: a null result on pass rate.** 17 → 18 is within variance.
What it delivered is diagnostic (`slot_bindings` in every trace), a
deterministic interrogative guard, and a fail-safe contract — not the three
cases it targeted.

**Variance floor.** At least three cases flip between runs on model
non-determinism alone. Single-run deltas below ±3 are not evidence. Any future
claim needs either a repeated run or a case whose trace shows the mechanism
firing.

**Stop investing in referentiality prompting.** Two runs agree the intent model
labels pronoun/deictic spans `RESOLVED` and omits dimensions it does not
notice. This is a model-capability limit, not a contract-shape problem, and no
further Python can extract a judgement the model never emits. The remaining
`ASK` failures should be revisited only with a stronger intent provider, not
with more prompt iterations.

## 5. Change B — operand-level verification for `SIMPLE_INFERENCE`

Targets `live_simple_inference`. Addresses **B2**.

For a `SIMPLE_INFERENCE` support, verify each **operand** rather than the
composed relation — every operand is a literally stated fact — then let
`inference_proof_is_valid` recompute the composition in Python. This is
strictly safer than a model judging a composition, because the arithmetic is
recomputed rather than asserted.

**As implemented.** The relation verdict is dropped for `SIMPLE_INFERENCE`
rather than re-asked per operand, and the proof carries the safety instead:

- `validated_supports` skips the four relation gates
  (`relation_match` / `attribute_match` / `premise_status` / verification-keys
  present) for an inference support only, and requires
  `inference_proof_is_valid` instead;
- `inference_proof_is_valid` now also takes the question and requires every
  operand to bind to it through the existing `entity_binding_is_literal`, so an
  unsupported join of two real-but-unrelated numbers fails on the operands;
- `verify_relations` no longer sends inference candidates at all — the useless
  call is removed, not merely ignored.

A second prompt (`prompts/relation_verifier_v2.txt`, present untracked from an
earlier session) would instead have the model judge each operand under an
id-keyed schema. It is deliberately **not** used: it re-adds an LLM call and
leaves the decision with a model, whereas literal quote + value-in-quote +
question binding + recomputed arithmetic settles the same question in Python.
Change A's failure was substituting one model judgement for another; this is
the opposite move. The file is left in place, unused.

The `DIRECT` relation gate is **not** touched.

Safety check already performed: `live_abstain_comparison` stays blocked, since
its recovery support is prose with no numeric operands and fails the operand
`answer_matches_quote` check.

Expected: **21/26**; `live_answer_reason` may follow but is not counted.

### 5.1 Run log — Change B, provider-pinned run

`make live-behavioral MODEL=local`, 100% local, zero fallback.

Result: **19/26** (baseline 17, Change A 18). 97 LLM calls (3.73/question, from
4.12), median 14.44 s, mean 20.44 s. Actions 8 `ANSWER` / 5 `ASK` / 13 `ABSTAIN`.

**The mechanism is confirmed firing, not merely a moved score.**
`live_simple_inference` answers `96,2 %` from operands `97,3` and `1,1`, both
literally quoted from the cited chunk, `operation: difference`, recomputed in
Python, labelled `INFERRED_SUPPORTED`, citation valid and quote literal. Its
accepted support carries `premise_status: None` and `relation_match: None` —
it was accepted *without* a relation verdict, exactly as designed. Cost fell
from 6 calls to 3.

The same trace also shows the guard working in the other direction: the first
extraction produced an invalid proof and was rejected
(`Inference proof không hợp lệ`); only the recovered, arithmetically valid proof
was accepted.

**Safety re-verified.** All eight unsupported/reversed/mismatched cases remain
`ABSTAIN` with zero valid supports, `live_abstain_comparison` included. All
eight `ANSWER`s carry a valid citation whose evidence quote occurs literally in
its cited source.

**Known cosmetic gap.** The inference answer renders as `96,2 %` while the gold
string is `96,2 điểm phần trăm`. The diagnostic report scores actions, so this
passes, but unit rendering for an inference result is not gold-string exact.

### 5.2 Remaining failures after Change B

| Case | Class | Reachable? |
| --- | --- | --- |
| `live_answer_person` | `retrieval_miss` | No — expected source outside top-k |
| `live_answer_definition` | `retrieval_miss` | No — no retrieved chunk mentions the phrase |
| `live_answer_list` | false `ASK` on the legacy `missing_requirements` field | Yes — see Change C |
| `live_ask_attribute`, `live_ask_entity`, `live_ask_scope` | `intent_miss` | Model-capability limited |
| `live_ask_time` | `intent_miss`, **still an unsafe `ANSWER`** | Model-capability limited |

**Acceptance is not met.** The handoff requires the `live_ask_time` unsafe
`ANSWER` to be gone before any success claim. It is still present: the
unresolved temporal deictic is not marked missing and a retrieved population
figure is answered.

## 5.5 Change C — a resolved dimension cannot also be alleged missing

Targets `live_answer_list`, a false `ASK` (acceptance criterion 5) where the
model alleged a missing `country` on a question that already binds
`location` to a literal span.

`apply_clarity_guard` now drops an alleged missing slot when a `RESOLVED`,
literally-bound binding already covers that slot **or** a slot in the same
`ANSWER_TYPE_SATISFIES` family. Allegations with nothing binding them survive,
so a genuinely unscoped question still asks.

### 5.6 Run log — Change C, provider-pinned run

`make live-behavioral MODEL=local`, 100% local, zero fallback.

Result: **20/26** (17 baseline → 18 → 19 → 20). 98 calls (3.77/question),
median 16.82 s, mean 21.47 s. Actions 9 `ANSWER` / 4 `ASK` / 13 `ABSTAIN`.

- `live_answer_list` fixed, as designed.
- Zero safety violations: all eight `ABSTAIN` fixtures hold.
- All nine `ANSWER`s carry valid grounding.
- `live_ask_time` remains an unsafe `ANSWER`. **Acceptance still not met.**

## 5.7 Phase 0 — held-out validation (run before any further tuning)

`data/diagnostics/ponyguard_holdout_live.jsonl`, 10 cases written to **falsify**
the guards added above, never used to tune them. Run with
`make live-holdout MODEL=local`, reported to
`reports/PONYGUARD_HOLDOUT_BEHAVIORAL_REPORT.md`.

Result: **6/10**. Findings ranked by importance.

### Finding 1 — a reversed actor/patient produced a grounded unsafe `ANSWER`

`hold_abstain_reversed_actor`: "Tập đoàn Lend Lease được Làng Olympic xây dựng ở
đâu?" is the source relation reversed. The pipeline answered
`Thung lũng Lower Lea` with a valid citation and a literal quote.

The support is `DIRECT` and passed the **full** relation gate:
`premise_status: SUPPORTED`, `relation_match: true`, `attribute_match: true`.
The relation verifier — whose stated job is to return `CONTRADICTED` on a
different "actor/patient direction" — returned `MATCH`. No deterministic guard
can catch this: entity binding holds, the quote is literal, the answer occurs in
the quote. **This is a model-capability failure in the relation stage**, the
exact mirror of the intent-stage failure, and it is more serious because it
yields a confident wrong answer rather than a missing clarification.

Not caused by Change B: that change bypasses gates only for
`SIMPLE_INFERENCE`, and this support is `DIRECT`.

**Consequence: the 20/26 figure overstates safety.** The tuned suite's eight
`ABSTAIN` fixtures pass, but a single unseen reversal leaks. Safety on reversals
is not robust; it was partly a property of the fixtures, not of the guard.

### Finding 2 — Change B generalises

`hold_inference_two_chunks` passed: operands drawn from **two different chunks**,
arithmetic recomputed in Python. Change B is validated on unseen data, not only
on the case it was designed against.

### Finding 3 — acceptance criterion 5 holds on unseen data

`hold_answer_location_clear` and `hold_answer_date_clear` both `ANSWER`. The
guards added in Changes A and C do not over-suppress into false `ASK`.

### Finding 4 — the falsifiers were inconclusive, not passed

`hold_ask_location_missing_country` and `hold_ask_location_family_country` both
failed (`ABSTAIN`, expected `ASK`) — but **upstream of the rules under test**.
The intent model emitted no `country` or `location` binding at all and alleged
nothing, so `ANSWER_TYPE_SATISFIES` and the Change C family rule never executed.

Stated plainly: the tests designed to falsify those two rules could not reach
them, because the model fails earlier. Those rules remain **unvalidated** —
neither confirmed nor refuted. They must not be treated as proven.

### Finding 5 — an unanswerable join produced a false `ASK`

`hold_abstain_unsupported_join` returned `ASK` (expected `ABSTAIN`) via the
empty-slot path. Not a safety failure, but a wrong action.

### Revised priorities

1. The reversal leak (Finding 1) outranks pass rate. A confident wrong answer is
   worse than four missing clarifications.
2. Findings 1 and 4 share one root cause: **the two judgement stages — intent
   and relation — are unreliable on the local model**, while the extraction and
   validation layers do their job. This is capability, not contract shape.
3. Do not add further guards to compensate. Two of the guards already added
   remain unvalidated; adding a third to patch the reversal would be fitting to
   fixtures, and no deterministic rule can decide actor/patient direction anyway.

## 6. Plan to 24/26

24/26 means the two confirmed `retrieval_miss` cases stay failing and every
other case passes. From 20/26 that is exactly the four `intent_miss` cases:
`live_ask_attribute`, `live_ask_entity`, `live_ask_scope`, `live_ask_time`.

All four fail the same way, and it is **not** a contract-shape problem — Change
A already gave the model a per-slot, span-bound contract and it still labels
pronoun and deictic spans `RESOLVED`, or omits the dimension entirely. Two
distinct model failure modes are visible in the traces:

| Mode | Evidence | Cases |
| --- | --- | --- |
| **Mislabel** — a referential span is called `RESOLVED` | `"ông ấy" → RESOLVED`, `"Toán học" → RESOLVED`, `"mấy" → RESOLVED` | `entity`, `scope`, `attribute` |
| **Omission** — the dimension is never enumerated | no `time` binding at all for `"khi đó"` | `time` |

### Phase 1 — Measure intent capability (no production change)

Nothing should be built until this exists. Add an intent-only A/B harness that
calls `intent_analyzer_v2` over all 26 fixtures on each available provider, with
no retrieval and no pipeline, and scores two things per case: did it emit a
binding for the dimension that matters, and did it label that binding correctly.

Cost is ~26 short calls per provider — the intent prompt carries no chunks. This
is the cheapest measurement in the system and it decides everything below.

Deliverable: a per-provider table of mislabel and omission counts.

### Phase 1 run log — measurement built, comparison blocked

`scripts/measure_judgement_stages.py`, read-only, probes both judgement stages
in isolation. Report: `reports/PONYGUARD_JUDGEMENT_CAPABILITY.md`.

**Local, validated (36 intent probes over both fixture files, 17 relation probes
replayed from recorded runs):**

| Stage | Correct | Failing |
| --- | ---: | --- |
| intent | 29/36 | the four `live_ask_*` misses, both holdout location falsifiers, the unsupported join |
| relation | 14/17 | `live_answer_person`, `hold_inference_two_chunks`, `hold_abstain_reversed_actor` |

**The cross-provider comparison did not happen.** The first run reported
`gemini-3.6-flash` at 29/36 and 14/17 — *identical scores and identical failing
sets to local*. That was a harness defect, not a finding: `build_llm` returns a
`FallbackLLM`, every Gemini call degraded to local on `429`, and the harness did
not record which provider served each call. All 36 intent bindings were
byte-identical across the two columns, which is what exposed it.

Fixed: the harness now builds each named provider with **no fallback** and
records `served_by` per probe. Re-measured, `gemini-3.6-flash` returns
`Gemini temporarily unavailable (429)` on all 36 probes — reported as 36 errors
instead of borrowed local results.

**Consequence: Phase 2 is not yet justified.** The claim "a stronger provider
fixes the judgement stages" is currently *unmeasured*, not supported. It must
not be implemented on the strength of the invalid first run. Re-run when quota
recovers, or measure a provider with available quota.

This is the second time in this work that silent provider fallback produced a
misleading result. Any measurement that names a provider must record which
provider actually served the call.

### Phase 2 — Route the intent stage by capability

Justified only if Phase 1 shows a provider that clears the four cases.

The brief calls for using the fallback model according to real capability.
Intent is the right stage to route: it is the only stage whose prompt carries no
retrieved context, so it is by far the cheapest to send to a stronger provider,
and it is the stage whose errors are unrecoverable — a wrong `ASK`/no-`ASK`
decision is made before any evidence exists. Extraction and relation stages run
over long chunk context where the local model already performs adequately (every
`DIRECT` answer and all eight safety cases pass locally).

Implementation: an optional `intent_llm` on `PonyGuard`, defaulting to the
existing `self.llm`, wired in `run_system.py`. No change to any other stage.
Per-stage provider is already recorded in the trace, so the effect is auditable.

### Phase 3 — Close the omission mode

Only if Phase 1 shows omission surviving on the stronger provider. The intent
contract would have to be complete over the slot enum rather than sparse, so a
dimension can be *declared* `ABSENT` but never silently skipped. A sparse
contract would then be an incomplete contract rather than an implicit "all
clear". This must stay fail-safe: an incomplete contract falls back to current
behaviour, never to a manufactured `ASK`.

### Phase 4 — The last two (beyond 24/26)

`live_answer_person` and `live_answer_definition` are retrieval misses. The
handoff forbids broadening `top_k` to recover them and the earlier experiment
that tried it regressed 17 → 14. Reaching 26/26 would need a genuine
second-stage retrieval design, which is out of scope for this work.

### Risks

- **Provider quota.** `429`/`503` were seen in this work. Routing intent
  remotely must degrade to local, and the report must state when it did —
  a fallback run is not a capability result.
- **Comparability.** Always pin (`MODEL=`) for diagnostic runs. Mixed-provider
  runs are not comparable and one already produced a misleading result here.
- **Variance.** The floor is ±3 cases. Any claim needs either a repeated run or
  a trace showing the mechanism firing on the target case.

## 7. Change D — remove the dead branches (only after the above)

`clarification_adjudication` becomes provably redundant once intent owns the
`ASK` decision, and `fact_recovery` has recovered nothing. Removing them is a
latency and call-count win that falls out of the architecture, not tuning.
Requires A's live run to confirm intent absorbs every `ASK` the auditor was
nominally there to catch.

## 7. Not touching

- Retrieval, `top_k`, the FAISS index, the retriever, the corpus, the manifest,
  `data/benchmark/test.jsonl` and the final-comparison split.
- The `DIRECT` relation gate and its `MATCH` requirement.
- The two confirmed `retrieval_miss` cases. The handoff forbids broadening
  retrieval to recover them, and the classification above shows validator work
  cannot reach them.

## 8. Constraints carried from `PROJECT_POLICY.md`

No entity, question, answer, language phrase or observed case in production
code. Every rule added here is schema-driven and operates on a closed slot enum
and a literal-substring check, never on a domain term. New live cases become
fixtures, never runtime branches.
