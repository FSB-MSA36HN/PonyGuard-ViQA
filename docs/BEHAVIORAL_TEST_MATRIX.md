# PonyGuard behavioral test matrix

Run the deterministic behavioural suite with:

```bash
make behavior-test
```

Run the complete regression suite with:

```bash
make test
```

The behavioural matrix is intentionally separate from the frozen benchmark. It uses scripted LLM outputs and small source fixtures to make every policy outcome reproducible; it does not make a live-provider quality claim.

| Area | Coverage | Automated verifier |
| --- | --- | --- |
| Direct answers | Literal grounded count/value, definition, date and source-level entity binding | `test_grounding.py` |
| Controlled inference | `DIRECT`, `SIMPLE_INFERENCE`, unsupported inference | `test_behavioral_matrix.py` |
| Clarification | All eight missing slots, contextual options, non-echo questions and follow-up resolution | `test_behavioral_matrix.py`, `test_ambiguity.py` |
| Abstention | No evidence, entity/attribute mismatch, conflicts, time/population mismatch, subset-versus-total, and grounded explanations | `test_behavioral_matrix.py`, `test_reasoned_evidence.py` |
| Comparable baselines | Basic RAG and Prompt-Safe RAG share literal citation/quote contract | `test_behavioral_matrix.py`, `test_grounding.py` |
| Grounding attacks | Wrong chunk, nonliteral quote, wrong numeric value, answer echo, near-name entity and malformed entity spans | `test_grounding.py` |
| Resilience | Fenced/broken JSON, partial semantic contract, repair failure, empty Gemini MAX_TOKENS response and temporary-provider fallback | `test_core.py`, `test_ambiguity.py` |
| Conversation | Slot completion, legacy-session recovery and complete-question replacement | `test_ambiguity.py`, `test_core.py` |

The separate `data/benchmark/clarification_test.jsonl` remains a report-only data set. It currently contains entity-only examples and is not used as the sole guard for clarification quality. The matrix above covers every supported schema slot without changing `data/benchmark/test.jsonl` or its manifest.

## Acceptance criteria

All deterministic rows must pass. A production-model run is evaluated separately on dev/validation only, because provider availability and generative variation cannot be truthfully certified by a fixed unit test. Before a final benchmark, run data verification, retrieval evaluation, the behavioural suite and the full test suite.
