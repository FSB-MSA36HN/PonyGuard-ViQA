# Behavioral verification report

Run date: 2026-08-15

## Deterministic policy suite

| Check | Result |
| --- | --- |
| Behavioural matrix (`make behavior-test`) | 27 passed |
| Full regression suite (`make test`) | 92 passed |
| Python compilation and diff whitespace validation | passed |

The matrix covers all supported `ASK` slots (`entity`, `requested_attribute`, `country`, `location`, `time`, `scope`, `reference`, `target`), `ANSWER` from direct and simple inference, and `ABSTAIN` from unavailable, mismatched, conflicting or scope-incomplete evidence. It also covers grounding/citation validation, baseline parity, follow-up completion, malformed structured output and provider fallback paths.

## Data and retrieval verification

| Source | Valid rows |
| --- | ---: |
| `data/raw/train.jsonl` | 28,454 |
| `data/raw/test.jsonl` | 7,301 |
| `data/raw/validation.jsonl` | 3,814 |

| Retrieval metric | Result |
| --- | ---: |
| Recall@1 | 0.566 |
| Recall@3 | 0.750 |
| Recall@5 | 0.818 |
| Recall@10 | 0.878 |
| MRR | 0.6704 |

## Scope and limit

These deterministic checks certify implementation contracts, not every possible natural-language phrasing or a live provider's probabilistic behavior. Run production-model comparisons only on `dev` and `validation`; the frozen `data/benchmark/test.jsonl` remains untouched until final evaluation.
