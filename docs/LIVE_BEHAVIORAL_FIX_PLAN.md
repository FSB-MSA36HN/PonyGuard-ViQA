# PonyGuard live behavioural remediation plan

## Status and evidence

This plan is based on the real 26-case development run in
`runs/ponyguard/ponyguard_behavioral_live_predictions.jsonl`, not on the frozen
benchmark. All 26 requests used the configured local fallback
`Qwen/Qwen3-8B-MLX-4bit` because Gemini returned `429`.

Observed execution flow:

1. Retrieval completed for every request.
2. Semantic evidence analysis ran for every request.
3. The decision/generation/claim-gate flow completed without a process crash.
4. The final decisions were 8 `ANSWER`, 15 `ABSTAIN`, and 3 `ASK`.

The flow is mechanically complete, but it is not semantically reliable enough
yet. The current report says 6/26 passed; this undercounts quality because its
token-F1 rule wrongly fails correct expanded answers such as `28% người Pháp…`
against a gold value of `28%`. That reporting flaw must be fixed separately
from the pipeline failures.

Latency is also high: median 32.3 s/request, mean 34.3 s/request. The median
semantic-evidence stage alone is 21.6 s. Evidence recovery, clarification
adjudication and grounding retries add more calls on difficult requests.

## Confirmed strengths

- A direct causal answer was correct, grounded and safely cited.
- Several unsupported-premise cases correctly returned `ABSTAIN` with a source
  explanation.
- Literal citation validation stopped some otherwise plausible answers from
  being shown as facts.
- The process did not use the frozen test split for this diagnostic run.

## Confirmed defects

### 1. Live evaluation is scoring short answers incorrectly

The answer `28% người Pháp không theo tôn giáo nào` and a dated response that
contains `1881` are correct, but the current F1 threshold treats them as
failures because the reference answer is very short. The report therefore
cannot be used as a quality gate yet.

### 2. Clear direct evidence can still become `ABSTAIN`

Examples include the Mekong Delta height and the Hanoi hospital list. Traces
show a direct candidate or support, but the final grounded generation uses a
quote/answer pair that fails literal validation, or the semantic model emits a
negative prose verdict despite direct source text. This is a false abstention
caused by inconsistent evidence hand-off between extractor, generator and
claim gate.

### 3. The system can answer a question whose premise is contradicted

For the cholesterol-transfer case, it answered with the source's `HDL → …`
fact even though the question explicitly said `LDL → …`. For the Austrian army
case, it treated “fought for” as equivalent to “reinforced”. Literal quotation
alone proves that a fact exists; it does not prove that the fact answers the
asked relation.

### 4. Missing-context questions frequently bypass `ASK`

`Con hươu cao cổ có mấy?`, `Ông ấy sinh năm bao nhiêu?`, `Câu đó xảy ra khi
nào?`, and `Họ đã làm gì?` all became `ABSTAIN`. Their semantic output omitted
the requirement fields, but the Python `Requirement` default is clear, so a
partial/malformed model contract is accidentally treated as a complete
question. Conversely, two clear but unsupported questions were incorrectly
turned into `ASK` for invented `scope`/`target` gaps.

### 5. Retrieval and evidence recovery are not robust for paraphrases

The Encyclopédie-author and definition cases failed even though their source
facts exist in the corpus. The current recovery path only activates for a
syntactically incomplete semantic result; it does not recover when a complete
but unsupported analysis is wrong. Refusal explanations may then cite merely
top-ranked but irrelevant observations.

### 6. `SIMPLE_INFERENCE` is promised but not implemented end-to-end

The arithmetic difference case abstained. The literal quote validator rightly
rejects a derived number that is absent from a single quote, but there is no
structured operand/formula contract for validating permitted arithmetic.

### 7. The live suite lacks multi-turn and provider coverage

It tests single-turn `ASK`, but not `ASK → clarification → retrieve again →
ANSWER/ABSTAIN`. It also only measures Qwen fallback behaviour, not the normal
Gemini path, because Gemini was rate limited.

## Design rules

- Preserve the existing corpus, FAISS retriever, three-system architecture and
  frozen test manifest.
- Do not add entity-, language- or question-specific rules. All remediation
  must use versioned schemas, generic evidence bindings and dynamic prompts.
- `ASK` is only for a required semantic slot proven absent from the request.
  A clear request with insufficient/contradictory evidence is `ABSTAIN`.
- `ANSWER` needs a validated semantic relation as well as a literal source
  quote. A quote that merely mentions the same nouns is insufficient.
- User clarification defines intent only. It must never count as factual
  evidence.

## Implementation milestones

### M1 — Make the live diagnostic report trustworthy

1. Replace one global answer-F1 gate with answer-type-aware matching:
   numeric/date normalized containment, list set overlap, and token F1 only for
   explanatory text.
2. Store expected evidence type and expected source/chunk identifiers in the
   diagnostic fixture; check retrieval and citation separately from answer
   wording.
3. Report action accuracy, answer correctness, grounding validity,
   clarification quality, evidence-relation validity and latency independently.
4. Mark any unavailable provider and fallback model in the report header.

Acceptance: the `28%`, `1881`, and `20/8/1945` style answers pass when their
meaning and citation are valid; an unsupported but well-written response still
fails.

### M2 — Introduce a strict intent/requirement contract

1. Make semantic requirement fields tri-state (`known`, `missing`,
   `unresolved`) instead of inheriting `question_clear=True` from a dataclass
   default.
2. Require every claimed missing slot to include a generic slot-necessity
   explanation and an evidence span describing what is missing. A malformed or
   incomplete contract triggers one requirement-repair call, never implicit
   “clear”.
3. Validate `ASK` against the original question: the selected slot must be
   unresolved, not merely something the model would like to narrow.
4. If intent is clear after repair but evidence is insufficient, force
   `ABSTAIN`; do not invoke clarification adjudication as a second chance to
   invent a missing slot.
5. Generate the clarification from the missing-slot contract and verify that it
   names the known subject plus the information needed, without echoing the
   question.

Acceptance: all eight missing-slot diagnostic cases return useful `ASK`; clear
but unsupported relation/comparison cases return `ABSTAIN`.

### M3 — Bind evidence to the asked relation, not only to words

1. Extend each support object with `question_relation`, `evidence_relation`,
   `relation_match`, `premise_status` (`SUPPORTED`, `CONTRADICTED`,
   `UNSTATED`) and literal spans for entity, attribute and relation.
2. Validate every span against the cited chunk. Reject a support when entity,
   direction, agent/patient, quantity type, time or population differs from the
   request.
3. Treat `premise_status=CONTRADICTED` as `ABSTAIN` with a grounded correction
   explanation; do not silently answer a different question.
4. Pass only a canonical validated support (`candidate_answer` plus its exact
   quote) to answer generation. The generator cannot replace it with an
   unquoted synonym/list expansion.
5. Make the final claim verifier compare each draft claim to the same support
   object, including its relation binding.

Acceptance: cholesterol direction and “reinforced” versus “fought for” do not
produce `ANSWER`; direct numeric/list/location evidence reaches `ANSWER` when
its relation binding is valid.

### M4 — Recover evidence generically before abstaining

1. Invoke bounded evidence recovery when there is no valid support, regardless
   of whether the first semantic JSON was syntactically complete.
2. Recovery produces only the same strict support schema from retrieved chunks;
   it cannot answer directly.
3. If top-k has no relation-bound support, issue at most one generic
   slot-derived retrieval query using the extracted entity and requested
   attribute, merge unique chunks and rerun evidence extraction once.
4. Refusal text may cite only relation-bound observations. If none exist, say
   that no source matching the requested relation was retrieved; do not quote
   unrelated top-ranked text.
5. Tune recovery threshold, one-query limit and `top_k` on dev/validation only.

Acceptance: paraphrased direct-answer diagnostics improve without turning the
unsupported-premise cases into answers. The frozen final test remains untouched.

### M5 — Validate permitted SIMPLE_INFERENCE

1. Replace free-form inferred numbers with a small structured proof:
   `operation`, literal operand values, operand chunk IDs/quotes, result and
   unit.
2. Deterministically validate only allowed operations (`sum`, `difference`,
   `ratio`, and explicit one-hop comparison) and recompute the result.
3. Require compatible units, entity, time and population scope. Any missing
   operand, unit mismatch or multi-hop assumption is `ABSTAIN`.
4. Cite all operand chunks in the final answer and label the response as a
   calculation from the cited values.

Acceptance: the 97.3% minus 1.1% diagnostic returns `96.2 percentage points`
with two literal operands; an inference requiring external knowledge abstains.

### M6 — Restore performance after correctness is stable

1. Profile the revised stages separately for Gemini and Qwen fallback.
2. Combine requirement analysis and first evidence extraction into one strict
   structured call; retain one repair call only for malformed output.
3. Run recovery, clarification writer and claim verification only when their
   preconditions are met.
4. Reuse cached embedder/index/model within a process; keep stage timing and
   provider/fallback metadata per case.
5. Set latency targets after collecting a representative validation run, not
   from a single cold batch.

Acceptance: no reduction in action/citation scores; fewer calls on direct
answers and a lower median latency than the current 32.3 seconds on the same
fallback-model suite.

### M7 — Expand the evaluation protocol

1. Add deterministic regression tests for each observed failure class, not for
   its named entity.
2. Add live two-turn fixtures for each missing slot: relevant clarification
   resolves the slot and triggers retrieval again; irrelevant clarification
   leaves only the unresolved slot in the next `ASK`.
3. Run the diagnostic suite with the intended Gemini provider when quota is
   available, then separately with the local fallback; report both rather than
   mixing them.
4. Run the suite on dev/validation during iteration. Freeze configs/prompts,
   then run the final benchmark exactly once against the immutable test split.

## Exit criteria

- Corrected diagnostic reporting shows per-category results without short-answer
  false failures.
- 100% deterministic tests pass.
- All direct-evidence and all missing-slot live diagnostics pass with valid
  citations/clarifications on the selected provider.
- No known relation-reversal or unsupported-premise diagnostic returns an
  unqualified `ANSWER`.
- SIMPLE_INFERENCE uses a validated proof or abstains explicitly when proof is
  unavailable.
- The report records model/provider, fallback status, prompts, policy version,
  retrieved evidence, decisions and stage latencies for every case.
