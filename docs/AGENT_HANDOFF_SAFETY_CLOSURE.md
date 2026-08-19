# PonyGuard safety-closure handoff

## Mission

You are continuing work on PonyGuard-ViQA. The pass-rate work is largely done;
**the open problem is safety**. Two questions still receive a confident wrong
`ANSWER` with a valid citation and a literal evidence quote:

| Case | Gold | Actual | Failure |
| --- | --- | --- | --- |
| `safe_rev_founder` | `ABSTAIN` | `ANSWER` | reversed actor/patient accepted |
| `live_ask_time` | `ASK` | `ANSWER` | answers despite an unresolved deictic time |

A confident wrong answer defeats the purpose of the system more than a missing
clarification does. **Prioritise closing these two over raising pass rate.**

Do not claim success until both are gone and a new pinned live run confirms it
on all three fixture suites.

## Non-negotiable policy

Read [`PROJECT_POLICY.md`](../PROJECT_POLICY.md) before editing.

- Never hard-code an entity, domain fact, answer, language phrase, question
  pattern, or observed case in production code.
- A diagnostic question belongs in a fixture/test, not a runtime branch.
- Do not alter `data/benchmark/test.jsonl`, its manifest, corpus, retriever, or
  the main-comparison split.
- Do not make user clarifications factual evidence.
- Preserve the common output schema and the comparable Basic RAG / Prompt-Safe
  RAG / PonyGuard setup.

### Additional rules earned the hard way in the previous session

Violating these produced three wrong conclusions. They are not optional.

1. **Always pin the provider** on diagnostic runs (`MODEL=local`). `build_llm`
   returns a `FallbackLLM` that silently degrades to local on `429`. One run
   mixed providers and produced an uninterpretable result.
2. **Any measurement naming a provider must record which provider served each
   call.** A capability comparison once reported `gemini-3.6-flash` at 29/36
   with an *identical failing-case list to local* — every call had fallen back.
   `scripts/measure_judgement_stages.py` now records `served_by`; keep it.
3. **One change, one live run.** A bundled change once took 17/26 → 14/26 and
   needed a full rollback.
4. **The noise floor is ±3 cases.** A score delta below that is not evidence.
   Require a trace showing the mechanism firing on the target case.
5. **Measure before building.** Four separate changes were refuted by
   measurement *before* implementation in the previous session; one of them
   would have executed zero times in production.
6. **Never add a rule justified only by "it fixes case X and does not break
   case Y."** That is fitting the fixture set. Two such rules were shipped and
   later removed — see *Removed rules* below.

## Current repository state

| Purpose | File |
| --- | --- |
| Pipeline, validators, direction check | `src/ponyguard_viqa/pipelines.py` |
| Schema, slot binding, literal helpers | `src/ponyguard_viqa/core.py` |
| LLM providers / fallback | `src/ponyguard_viqa/llm.py` |
| Intent prompt (has `slot_bindings`) | `prompts/intent_analyzer_v2.txt` |
| Relation verdict prompt | `prompts/relation_verifier_v1.txt` |
| Relation **direction** prompt | `prompts/relation_direction_v1.txt` |
| Fact extraction prompt | `prompts/fact_extractor_v1.txt` |
| Production config | `configs/ponyguard.yaml` |
| Roadmap + every measurement so far | `docs/PONYGUARD_OPTIMISATION_ROADMAP.md` |
| Prior session's analysis and run logs | `docs/PONYGUARD_INTENT_EVIDENCE_PLAN.md` |

### Three fixture suites — know which is which

| Suite | File | Command | Role |
| --- | --- | --- | --- |
| Tuned | `data/diagnostics/ponyguard_behavioral_live.jsonl` | `make live-behavioral MODEL=local` | 26 cases, **used for tuning** — optimistic |
| Held-out | `data/diagnostics/ponyguard_holdout_live.jsonl` | `make live-holdout MODEL=local` | 10 cases, **never tuned on** |
| Safety held-out | `data/diagnostics/ponyguard_safety_holdout.jsonl` | `make live-safety MODEL=local` | 12 reversal/mismatch cases + 3 correct-direction controls |

The safety suite deliberately contains correct-direction controls so a
degenerate "always `ABSTAIN`" system cannot score well. **Keep them.**

## Latest results — this is your starting evidence

All runs pinned 100% local `Qwen/Qwen3-8B-MLX-4bit`, zero fallback.

| Suite | Result | Unsafe `ANSWER` |
| --- | ---: | --- |
| Tuned | **19/26** | `live_ask_time` |
| Held-out | **7/10** | none |
| Safety held-out | **10/12** | `safe_rev_founder` |

`make test` **136 passed**, `make behavior-test` **29 passed**.
Mean **3.50** LLM calls/question (down from 4.12).

Remaining non-safety failures, with cause already established:

- `live_answer_person`, `live_answer_definition` — **`retrieval_miss`**. The
  expected source is outside top-k; for the definition case *no* retrieved chunk
  mentions the phrase. Not reachable from validator work.
- `live_ask_attribute`, `live_ask_scope`, `live_ask_entity`,
  `hold_ask_location_*` — **`intent_miss`**, model-capability limited (below).
- `live_answer_list` — the model alleges a missing `country` on a fully
  specified question. Model noise; deliberately **not** papered over.
- `hold_abstain_unsupported_join`, `safe_rev_capital` — wrong action (`ASK`),
  but **not unsafe**.

## Confirmed root causes

1. **`safe_rev_founder` — relation-stage capability.** The support is `DIRECT`
   and passes the *full* relation gate (`premise_status: SUPPORTED`,
   `relation_match: true`, `attribute_match: true`). The verifier, whose stated
   job is to return `CONTRADICTED` on a wrong actor/patient direction, returns
   `MATCH`. No deterministic guard catches it: the entity is in both texts, the
   quote is literal, the answer sits inside the quote.

   The direction check (below) misses it because the model reports the source
   triple by **linear word order**, not semantic role: for
   *"phong trào Bauhaus **do** Walter Gropius thành lập"* it returns
   `source.subject = "phong trào Bauhaus"`, `relation = "do"`. This is
   **deterministic — 3/3 identical outputs** — and a semantic-role rewrite of
   the prompt made things *worse* (see *Rejected experiments*).

2. **`live_ask_time` — intent-stage capability.** The unresolved temporal
   deictic is never enumerated as a slot at all, so no guard can act on it. The
   pipeline then answers one of several time-keyed population figures present in
   the retrieved chunks.

3. **Both are the same class: the two judgement stages are unreliable on the
   local model, while extraction and deterministic validation work.** Evidence:
   intent measured **29/36**, relation **14/17** on local; and five intent cases
   fail on **all three** local models tested (3B, 7B, 8B) — see below.

4. **Model scaling does not fix it.** Intent measured on three local models:

   | Model | intent |
   | --- | ---: |
   | `Qwen2.5-3B-Instruct-4bit` | 23/36 |
   | `Qwen2.5-7B-Instruct-4bit` | 23/36 |
   | `Qwen3-8B-MLX-4bit` (production) | 29/36 |

   3B → 7B is **flat**; 7B → 8B is a generation change, not a size change. Five
   cases fail on all three. Do not assume a larger model closes this.

5. **The cross-provider comparison is still unmeasured.** Gemini exhausted quota
   twice. The last attempt completed **8/36 intent probes — all of them
   `expected_ask=False`**, i.e. only the easy "do not ask" cases. That `8/8` is
   **not** evidence that Gemini is better; no hard case was ever measured.

## Changes retained (all validated on held-out data)

- **Inference proof path.** `SIMPLE_INFERENCE` supports bypass the composed
  relation verdict — no source ever states a *derived* relation, so that verdict
  carries no information — and are proved by `inference_proof_is_valid`:
  literal operand quotes, value-in-quote, question binding per operand, and
  arithmetic recomputed in Python. Validated on unseen data by
  `hold_inference_two_chunks` (operands in two different chunks). Also removed
  one useless LLM call.
- **Dead-branch removal.** The question-only clarity audit on the `intent_first`
  path ran on 16 of 36 questions and produced **zero** decisions; removed.
  −12% LLM calls, **no** case changed. The evidence-backed adjudicator is
  retained for the `intent_first: false` path. **`fact_recovery` was measured
  load-bearing (2 rescues) — do not remove it.**
- **Relation direction check.** One call on the about-to-answer branch only;
  compares the question subject against the source subject/object by literal
  token overlap, in Python. Closed `hold_abstain_reversed_actor`.
  Measured precision **0 false positives in 8 live firings**; recall **1/2**.
- **Intent `slot_bindings`.** Per-slot span binding with a closed status enum,
  validated literally in Python. Pass-rate effect was **null**, but it is
  fail-safe and gives the trace visibility every diagnosis below depends on.

## Removed rules — do not reintroduce

Two rules shipped, then removed after falsification:

- `ANSWER_TYPE_SATISFIES` mapping `LOCATION → {location, country}` (narrowed to
  `{location}`).
- Change C's "resolved family covers an allegation" widening (removed; only
  exact-slot coverage remains).

Falsifiers they failed:

- *"Thủ đô của **nước đó** nằm ở đâu?"* — a `LOCATION` question whose
  jurisdiction is a referential span. Correct: `ASK country`. Old rules: `[]`.
- *"Thành phố **Springfield** nằm ở bang nào?"* — a resolved place does not
  settle which jurisdiction was meant. Correct: `ASK country`. Old rules: `[]`.

Removing them cost exactly **one** case (`live_answer_list`) and **only on the
tuned suite**; held-out was unchanged. That is the cleanest overfitting evidence
in the project: the rules' entire value sat on the set they were designed
against. Both falsifiers are now permanent tests in
`tests/test_intent_slot_binding.py`.

## Rejected experiments — do not repeat without new evidence

| Experiment | Measured outcome |
| --- | --- |
| Broad prompt rewrite + `top_k * 3` recovery | 17/26 → **14/26**, added unsafe `ANSWER`s. Fully rolled back. |
| Semantic-role direction prompt (`agent`/`patient`) | **Worse than v1**: 1 false positive on a correct answer, caught 1 instead of 2, and still missed `safe_rev_founder`. Deleted. |
| Per-chunk "answer alternatives" enumeration for ambiguity | **Recall 0/1, false positives 3/8.** Would have lost ~3 correct answers and fixed none. Not implemented. |
| Referentiality prompting on intent | Null result; 2/4 recall on true referentials, invented one false referential. |

**Pattern to internalise:** the ambiguity signal genuinely exists in the
retrieved chunks — it was verified by reading them — but this model cannot emit
it through any contract tried so far, at intent *or* extraction. Stop trying to
extract it by prompt.

## Required debugging workflow

Before editing anything, for a representative failing row:

1. Is the expected source among `retrieval.chunk_ids`?
2. How many `trace.evidence.valid_supports` are there? (Across all 36 recorded
   cases this is always **0 or 1**, never ≥2 — extraction collapses
   multiplicity. Any design assuming ≥2 will execute zero times.)
3. Which validation rule rejected it, exactly? See
   `trace.evidence.support_rejections`.
4. Did intent emit a `slot_bindings` entry for the dimension that matters, and
   with what status? Omission and mislabel are different failures.
5. For an unsafe `ANSWER`: did the relation verdict say `MATCH`, and did the
   direction check fire? Both are recorded per stage.
6. Record the class: `retrieval_miss`, `intent_miss`, `evidence_extraction_miss`,
   `relation_rejection`, `direction_miss`, `writer_failure`,
   `claim_gate_failure`, `provider_format_failure`.

## Improvement order

### 1. Consensus at the decision boundary — strongest evidence, do this first

The reversal leak is **intermittent, not systematic**: `safe_rev_builder` and
`hold_abstain_reversed_actor` use the **same entity pair** with different
wording, and only one leaked. Intermittency is exactly what sampling defeats.

Take the relation verdict (or the direction triple) **k times** and require
**unanimity** before allowing `ANSWER`; any disagreement → `ABSTAIN`. Cost is
+k calls on the about-to-answer branch only — the branch that already carries
the direction check, and the budget the dead-branch removal freed.

**Measure first** with `scripts/measure_judgement_stages.py`: how often does the
verdict change across k samples on (a) the correct-direction controls, and
(b) the reversal cases? If controls are stable and reversals are unstable, this
works and the effect size is known before any code changes.

### 2. Make the safety guards fail-closed, and expose the dial

Every guard currently fails **open**: a malformed contract keeps the support; a
tie in the direction check keeps the support. For a system whose purpose is
refusing to answer wrongly, require **positive** proof of alignment instead.

Treat this as one explicit, measurable policy dial rather than scattered
defaults. Sweep it, and report the pass-rate ↔ unsafe-rate curve on all three
suites so the trade-off is chosen with numbers rather than assumed.

### 3. Verify the answer, not the evidence — untested, plausible

Two attempts to make the model extract roles *from the source* have failed. Try
the opposite direction: compose the complete proposition from the **produced
answer** and the question relation — for the failing case that is
*"Phong trào Bauhaus đã thành lập Walter Gropius"* — and ask whether the source
entails it. Judging one finished proposition is an easier task than role
extraction, and the proposition is built by the pipeline, not by the model.

Measure precision on every correct `ANSWER` before wiring it in.

### 4. Cross-stage consistency — cheap, one observed signal

While measuring the rejected alternatives experiment, the enumeration stage
reported *no chunk states this relation* for `live_ask_time` while the extractor
had produced a support for it. Two stages disagreeing about whether evidence
exists at all is a usable red flag, and it points at the right case. Cheap to
test on recorded runs before touching production.

### 5. Capability routing — only when quota allows a real measurement

Run
`scripts/measure_judgement_stages.py --models local <model> --stages intent relation`
and **check the `served_by` column before believing any number**. Confirm hard
cases were actually measured, not only `expected_ask=False` ones. Only then
consider an optional `intent_llm` / relation provider on `PonyGuard`, defaulting
to `self.llm`.

Given the flat 3B → 7B curve, treat "a stronger model fixes this" as a
hypothesis to test, not a plan.

### 6. Retrieval — separate work, after safety

`live_answer_person` and `live_answer_definition` need retrieve-wide-then-rerank
while keeping the number of chunks passed to the LLM unchanged. Do **not**
simply widen `top_k`; that experiment regressed 17 → 14.

## Acceptance criteria

1. `make test` and `make behavior-test` pass.
2. All three suites run pinned (`MODEL=local`) and complete.
3. **Zero `ANSWER` on any case whose gold is not `ANSWER`**, across all three
   suites. This is the primary gate.
4. Tuned suite does not fall below **19/26**; held-out not below **7/10**;
   safety held-out not below **10/12**.
5. The three correct-direction controls in the safety suite still `ANSWER` — a
   guard that passes by refusing everything is a failure, not a fix.
6. No direct `ANSWER` without valid citation + literal quote + relation match.
7. No clear direct-answer fixture turned into `ASK` by optional
   country/location/time/scope.
8. Report action distribution, provider and fallback status, per-stage latency,
   LLM calls, and root-cause breakdown. State explicitly when results are
   local-only.
9. Every new rule ships with a **falsifier** — a fixture that would fail if the
   rule's specification is wrong, not merely one that passes.
10. Do not tune on or edit frozen benchmark files.

## Benchmark status — the missing deliverable

**No real benchmark has ever been run.** The committed `reports/final_results.md`
is labelled *"mock smoke test — not final"*.

`scripts/evaluate_all.py` now accepts `--model` and records `pinned_model` and
`limit` in `reports/benchmark_metadata.json`; before that fix it would have run
the whole benchmark on a silently mixed provider.

- Full frozen run: `.venv/bin/python scripts/evaluate_all.py --model local`
  — 2000 samples × 3 systems, estimated **~20 hours** on local Qwen.
- A 200-sample subsample (`--limit 200`) takes ~2.5 h. `test.jsonl` is shuffled
  (first 200 = 103 `ANSWER` / 97 `ABSTAIN`), so a prefix is a fair sample —
  but any report using it **must** say it is 200/2000, not the frozen benchmark.

Run the full benchmark once the safety gate above is closed and the diagnostic
config is frozen.

## Suggested first task

Do **not** write a new guard first. Start with the measurement in step 1:
sample the relation verdict k times on the safety suite's reversal cases and its
three correct-direction controls, and report the disagreement rate for each
group.

That single table decides whether consensus (step 1) or fail-closed (step 2) is
the right lever, and it costs nothing but local compute. If disagreement is high
on reversals and low on controls, implement consensus and expect
`safe_rev_founder` to close. If both groups are stable, consensus cannot help —
go to step 3.
