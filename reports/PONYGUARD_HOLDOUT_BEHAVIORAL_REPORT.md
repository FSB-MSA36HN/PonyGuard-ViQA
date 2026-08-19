# PonyGuard live behavioural report

## Summary

- Cases executed: 10/10
- Passed: 6
- Failed: 4
- Missing outputs: 0

## Per-case results

| Category | Expected | Actual | Result | Detail |
| --- | --- | --- | --- | --- |
| ASK / LOCATION question genuinely missing country (falsifies ANSWER_TYPE_SATISFIES) | ASK | ABSTAIN | FAIL | action expected ASK, got ABSTAIN |
| ASK / DATE question whose time input is referential (falsifies DATE->time suppression) | ASK | ASK | PASS | pass |
| ASK / LOCATION question with a bound place but unselected jurisdiction (falsifies Change C family rule) | ASK | ABSTAIN | FAIL | action expected ASK, got ABSTAIN |
| ASK / missing entity and scope (control that basic ASK still fires) | ASK | ASK | PASS | pass |
| ANSWER / clear LOCATION question must not become ASK | ANSWER | ANSWER | PASS | pass |
| ANSWER / clear DATE question must not become ASK | ANSWER | ANSWER | PASS | pass |
| ANSWER / SIMPLE_INFERENCE with operands in two different chunks | ANSWER | ANSWER | FAIL | answer F1 0.00 < 0.80 |
| ABSTAIN / reversed actor and patient | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / unsupported premise | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / unsupported numeric join must not pass the proof path | ABSTAIN | ASK | FAIL | action expected ABSTAIN, got ASK |

## Interpretation

This is a development diagnostic suite, not the frozen final benchmark. A PASS means the configured live model produced the expected action and passed the applicable answer/citation, clarification, or refusal contract. A FAIL identifies a reproducible case to inspect and add as a deterministic regression after root-cause analysis.
