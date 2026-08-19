# Benchmark results

| Metric | basic_rag | prompt_safe_rag | ponyguard |
|---|---|---|---|
| answer_em | 0.0291 | 0.0874 | 0.0777 |
| answer_f1 | 0.1533 | 0.1865 | 0.1260 |
| unanswerable_f1 | 0.5421 | 0.5867 | 0.5991 |
| hallucinated_answer_rate | 0.0843 | 0.0556 | 0.0682 |
| unsupported_claim_rate | 0.0959 | 0.0800 | 0.1000 |
| grounding_validity_rate | 1.0000 | 1.0000 | 1.0000 |
| citation_coverage | 1.0000 | 1.0000 | 1.0000 |
| scope_match_rate | 0.0000 | 0.0000 | 0.0000 |
| grounded_refusal_rate | 0.0000 | 0.0000 | 0.6077 |
| explanation_grounding_rate | 0.0000 | 0.0000 | 1.0000 |
| mean_coverage_probes | 0.0000 | 0.0000 | 0.0000 |
| unsupported_numeric_answer_rate | 0.0000 | 0.0000 | 0.0000 |
| false_abstain_on_direct_evidence | 0.0000 | 0.0000 | 0.0000 |
| over_abstention_rate | 0.5728 | 0.6019 | 0.6990 |
| false_ask_rate | 0.0000 | 0.0000 | 0.1300 |
| meaningful_ask_rate | 0.0000 | 0.0000 | 0.0000 |
| contextual_clarification_rate | 0.0000 | 0.0000 | 0.0000 |
| mean_latency_ms | 13903.8796 | 13995.3264 | 27236.6529 |
| mean_llm_calls | 2.1650 | 2.2700 | 4.0300 |
