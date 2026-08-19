# PonyGuard live behavioural report

## Summary

- Cases executed: 12/12
- Passed: 10
- Failed: 2
- Missing outputs: 0

## Per-case results

| Category | Expected | Actual | Result | Detail |
| --- | --- | --- | --- | --- |
| CONTROL / correct direction, agent asked | ANSWER | ANSWER | PASS | pass |
| CONTROL / correct direction, container asked | ANSWER | ANSWER | PASS | pass |
| CONTROL / correct direction, destination asked | ANSWER | ANSWER | PASS | pass |
| ABSTAIN / agent and patient swapped | ABSTAIN | ANSWER | FAIL | action expected ABSTAIN, got ANSWER |
| ABSTAIN / container and contained swapped | ABSTAIN | ASK | FAIL | action expected ABSTAIN, got ASK |
| ABSTAIN / source and destination swapped | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / invader and invaded swapped | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / builder and built swapped | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / influence direction reversed | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / a number is present in context but belongs to another entity | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / several population figures present, none for the asked year | ABSTAIN | ABSTAIN | PASS | pass |
| ABSTAIN / a founding year is present but belongs to another studio | ABSTAIN | ABSTAIN | PASS | pass |

## Interpretation

This is a development diagnostic suite, not the frozen final benchmark. A PASS means the configured live model produced the expected action and passed the applicable answer/citation, clarification, or refusal contract. A FAIL identifies a reproducible case to inspect and add as a deterministic regression after root-cause analysis.
