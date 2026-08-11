# PonyGuard — Contextual clarification for ambiguous Vietnamese questions

## Goal

Make `ASK` useful for questions that have a named entity but an incomplete or ambiguous requested attribute. For example, **“Hiện tại Việt Nam có mấy?”** must not be answered, retrieved as though it meant population, or clarified with a generic question. PonyGuard should ask a contextual question such as:

> Tôi cần biết “mấy” đang nói đến loại thông tin nào: mấy người, mấy tỉnh/thành, hay mấy cấp học?

This change applies only to PonyGuard. Basic RAG remains an intentionally unguarded baseline.

## Current root cause

`missing_requirements_from_question()` only recognises a bare ending such as `có bao nhiêu?`. It does not recognise Vietnamese ellipsis such as `có mấy?`, `bao nhiêu cái?`, `thế nào?`, or an attribute represented only by a vague placeholder. The current requirement LLM cannot override the deterministic guard, so it cannot safely promote these cases to `ASK`.

## Decision contract v4

Extend `Requirement` and the requirement prompt with:

- `ambiguity_type`: `NONE | MISSING_ENTITY | MISSING_ATTRIBUTE | AMBIGUOUS_ATTRIBUTE`.
- `clarification_options`: zero to three short, question-relevant attribute candidates.
- `clarification_question`: one Vietnamese question generated from the confirmed ambiguity and options.

The deterministic guard remains the authority for whether `ASK` is allowed.

### Precedence

1. A confirmed missing referent/entity → `ASK`.
2. A confirmed missing or ambiguous requested attribute → `ASK`.
3. A clear question with no validated support → `ABSTAIN`.
4. A clear question with validated direct/simple-inference support → `ANSWER`.

Evidence must never turn an incomplete request into an `ANSWER`; clarification only defines the request, and the next turn must still retrieve and validate evidence.

## Implementation steps

### 1. Deterministic ambiguity detector

Update the shared guard in `src/ponyguard_viqa/core.py` rather than adding UI-specific rules.

- Keep existing pronoun/referent detection.
- Detect terminal incomplete quantity forms: `có mấy?`, `có bao nhiêu?`, `bao nhiêu cái?`, `mấy cái?`, including punctuation and case variants.
- Do not mark clear attribute phrases as ambiguous: `mấy cấp học`, `mấy tỉnh`, `bao nhiêu người`, `bao nhiêu loài thực vật`.
- Return structured missing requirement metadata, not only a string list, so the clarification builder can identify `AMBIGUOUS_ATTRIBUTE`.
- Preserve the existing follow-up rule: once the user supplies clarification, do not ask the same requirement again.

The implementation will be deliberately rule-based for eligibility. It prevents an LLM from inventing `ASK` for an otherwise clear question and keeps the benchmark policy reproducible.

### 2. Contextual clarification builder

Add one shared builder used by `PonyGuard.clarification_question()`.

- For a named entity plus quantity ellipsis, provide two or three concise category examples relevant to the entity/question pattern.
- Prefer options extracted by the requirement analyzer; validate that every option is an attribute phrase, not a fact or answer.
- If options are absent/invalid, use a safe generic contextual fallback: `Bạn muốn biết số lượng gì về Việt Nam, ví dụ dân số, tỉnh/thành hay cấp học?`
- Do not claim one option is correct. Options are examples, not retrieved evidence.
- Do not repeat/paraphrase the full original question.
- Limit options to three and the clarification to one sentence.

For the example request, the expected action is `ASK`; a valid clarification contains the word `mấy`/`số lượng`, the entity `Việt Nam`, and at least two category choices.

### 3. Prompt/schema update

Create `requirement_analyzer_v4.txt` and bump prompt/policy metadata.

- Request `ambiguity_type` and `clarification_options` in structured JSON.
- Explain that options are suggestions only and are permitted only when ambiguity was detected.
- Keep LLM output advisory: the deterministic guard confirms the ambiguity and controls the final action.
- Reject malformed fields and fall back to deterministic template wording.

### 4. Pipeline and UI integration

- Apply the guard after v4 requirement extraction as today.
- Store ambiguity type, option validation/rejections, and final clarification wording in PonyGuard trace.
- Render the exact contextual clarification in the existing follow-up field.
- Keep follow-up UI exclusive to `ASK`; `ABSTAIN` continues to show evidence rationale only.
- Do not use follow-up text as factual evidence; retrieve/evidence-check again after it is appended.

### 5. Evaluation

Add a separate clarification fixture set; do not modify `data/benchmark/test.jsonl` or its manifest.

Required cases:

| Input | Expected action | Clarification expectation |
|---|---|---|
| `Hiện tại Việt Nam có mấy?` | `ASK` | Mentions missing quantity category and at least two options. |
| `Việt Nam có bao nhiêu cấp học?` | `ANSWER` when direct evidence exists | Never asks for the attribute again. |
| `Việt Nam có bao nhiêu loài thực vật?` | `ANSWER` when direct evidence exists | Never asks. |
| `Ông ấy sinh năm bao nhiêu?` | `ASK` | Asks for the person/entity. |
| `Việt Nam có bao nhiêu vệ tinh tự nhiên?` with no support | `ABSTAIN` | Does not ask merely because evidence is missing. |
| Follow-up `... mấy?` + `Tôi hỏi mấy cấp học.` | retrieve then `ANSWER`/`ABSTAIN` based on corpus | No repeated clarification. |

Report these from the isolated clarification set:

- ASK precision/recall;
- False ASK Rate on clear answerable questions;
- Meaningful ASK Rate;
- Contextual Clarification Rate: valid ASK responses that name the missing dimension and offer at least two relevant options.

### 6. Verification and rollout

1. Run unit tests for detector, option validator, fallback builder, repeated-follow-up behavior, and `ASK`/`ABSTAIN` precedence.
2. Run existing grounding regressions and full test suite.
3. Run dataset verification and benchmark smoke in mock mode.
4. Run clarification set and validation only to tune wording/options; freeze the policy/config before any final test benchmark.
5. Check UI manually for the example and confirm that the second user turn executes retrieval instead of treating clarification as evidence.

## Non-goals

- No web search, new model, fine-tuning, NLI classifier, or retriever change.
- No attempt to infer the intended meaning of `mấy` from general-world knowledge.
- No changes to Basic RAG behavior or the frozen final benchmark split.

## Acceptance criteria

The work is complete only when the example returns `ASK` with a short contextual choice question; clear questions with an explicit attribute still return `ANSWER` when grounded; lack of evidence still returns `ABSTAIN`; and all existing safety/grounding tests remain green.
