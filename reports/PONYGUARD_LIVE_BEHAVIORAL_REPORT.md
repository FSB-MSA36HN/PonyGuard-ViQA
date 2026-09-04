# PonyGuard live behavioural report

## Summary

- Cases executed: 26/26
- Passed: 18
- Failed: 8
- Missing outputs: 0

## Per-case results

| Category | Expected | Actual | Result | Detail |
| --- | --- | --- | --- | --- |
| ANSWER / direct numeric / paraphrase | ANSWER | ABSTAIN | FAIL | action expected ANSWER, got ABSTAIN |
| ANSWER / direct person | ANSWER | ABSTAIN | FAIL | action expected ANSWER, got ABSTAIN |
| ANSWER / direct date / paraphrase | ANSWER | ANSWER | PASS | pass |
| ANSWER / direct location / paraphrase | ANSWER | ANSWER | PASS | pass |
| ANSWER / direct count | ANSWER | ANSWER | PASS | pass |
| ANSWER / direct list / paraphrase | ANSWER | ASK | FAIL | action expected ANSWER, got ASK |
| ANSWER / causal explanation / paraphrase | ANSWER | ANSWER | PASS | pass |
| ANSWER / definition | ANSWER | ABSTAIN | FAIL | action expected ANSWER, got ABSTAIN |
| ANSWER / time | ANSWER | ANSWER | PASS | pass |
| ANSWER / SIMPLE_INFERENCE / arithmetic | ANSWER | ANSWER | PASS | pass |
| ABSTAIN / relation reversed | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / unsupported premise | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / attribute mismatch | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / actor reversed | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / causal direction reversed | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / unsupported event | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / unsupported comparison | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / unsupported intent | ABSTAIN | ABSTAIN | PASS | pass |
| ASK / missing requested_attribute / terse | ASK | ABSTAIN | FAIL | action expected ASK, got ABSTAIN |
| ASK / missing entity / pronoun | ASK | ABSTAIN | FAIL | action expected ASK, got ABSTAIN |
| ASK / missing country | ASK | ASK | PASS | pass |
| ASK / missing reference | ASK | ASK | PASS | pass |
| ASK / missing target | ASK | ASK | PASS | pass |
| ASK / missing scope | ASK | ABSTAIN | FAIL | action expected ASK, got ABSTAIN |
| ASK / missing time reference | ASK | ANSWER | FAIL | action expected ASK, got ANSWER |
| ASK / missing entity and location | ASK | ASK | PASS | pass |

## Interpretation

This is a development diagnostic suite, not the frozen final benchmark. A PASS means the configured live model produced the expected action and passed the applicable answer/citation, clarification, or refusal contract. A FAIL identifies a reproducible case to inspect and add as a deterministic regression after root-cause analysis.
