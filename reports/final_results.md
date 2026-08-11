# Benchmark results (mock smoke test — not final)

| Metric | basic_rag | prompt_safe_rag | ponyguard |
|---|---|---|---|
| answer_em | 0.0000 | 0.0000 | 0.0000 |
| answer_f1 | 0.0294 | 0.0294 | 0.0000 |
| unanswerable_f1 | 0.0000 | 0.0000 | 0.0000 |
| hallucinated_answer_rate | 0.0000 | 0.0000 | 0.0000 |
| unsupported_claim_rate | 0.0000 | 0.0000 | 0.0000 |
| grounding_validity_rate | 1.0000 | 1.0000 | 1.0000 |
| citation_coverage | 1.0000 | 1.0000 | 1.0000 |
| unsupported_numeric_answer_rate | 0.0000 | 0.0000 | 0.0000 |
| false_abstain_on_direct_evidence | 0.0000 | 0.0000 | 0.0000 |
| over_abstention_rate | 0.0000 | 0.0000 | 1.0000 |
| false_ask_rate | 0.0000 | 0.0000 | 0.5000 |
| meaningful_ask_rate | 0.0000 | 0.0000 | 0.0000 |
| contextual_clarification_rate | 0.0000 | 0.0000 | 0.0000 |
| mean_latency_ms | 0.1040 | 0.1286 | 0.1478 |
| mean_llm_calls | 1.0000 | 1.0000 | 2.5000 |
