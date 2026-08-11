from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from .core import tokenise, write_jsonl
from .llm import LocalLLM
from .pipelines import context, prompt
from .core import Chunk


def f1(prediction: str, gold: str) -> float:
    p, g = Counter(tokenise(prediction)), Counter(tokenise(gold))
    overlap = sum((p & g).values())
    if not overlap: return 0.0
    return 2 * overlap / (sum(p.values()) + sum(g.values()))


def audit_claims(prediction: dict[str, Any], llm: LocalLLM) -> list[dict[str, Any]]:
    if prediction["prediction"]["decision"] != "ANSWER": return []
    chunks = [Chunk(document_id=doc, chunk_id=cid, text=text) for doc, cid, text in zip(prediction["retrieval"]["document_ids"], prediction["retrieval"]["chunk_ids"], prediction["retrieval"].get("texts", []))]
    # The offline audit gets the identical retrieved evidence text from a stored optional trace when available.
    if prediction.get("trace", {}).get("retrieval", {}).get("chunks"):
        chunks = [Chunk(**item) for item in prediction["trace"]["retrieval"]["chunks"]]
    parsed, _ = llm.json(f"{prompt('claim_verifier_v1.txt')}\nAnswer: {prediction['prediction']['answer']}\nEvidence:\n{context(chunks)}")
    return parsed.get("claims", [])


def metrics(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in predictions if row["gold"]["expected_action"] == "ANSWER"]
    unanswerable = [row for row in predictions if row["gold"]["expected_action"] == "ABSTAIN"]
    answered = [row for row in predictions if row["prediction"]["decision"] == "ANSWER"]
    asks = [row for row in predictions if row["prediction"]["decision"] == "ASK"]
    clear_samples = [row for row in predictions if row["gold"]["expected_action"] != "ASK"]
    expected_asks = [row for row in predictions if row["gold"]["expected_action"] == "ASK"]
    correct_actions = sum(row["prediction"]["decision"] == row["gold"]["expected_action"] for row in predictions)
    tp = sum(row["gold"]["expected_action"] == "ABSTAIN" and row["prediction"]["decision"] == "ABSTAIN" for row in predictions)
    fp = sum(row["gold"]["expected_action"] == "ANSWER" and row["prediction"]["decision"] == "ABSTAIN" for row in predictions)
    fn = sum(row["gold"]["expected_action"] == "ABSTAIN" and row["prediction"]["decision"] != "ABSTAIN" for row in predictions)
    precision, recall = tp / max(1, tp + fp), tp / max(1, tp + fn)
    answer_f1 = [max((f1(row["prediction"]["answer"], answer) for answer in row["gold"]["answers"]), default=0.0) for row in answerable if row["prediction"]["decision"] == "ANSWER"]
    claims = [claim for row in predictions for claim in row.get("audit_claims", row.get("trace", {}).get("claims", []))]
    unsupported = [claim for claim in claims if claim.get("label") in ("UNSUPPORTED", "CONTRADICTED")]
    return {
        "count": len(predictions), "answer_em": sum(any(row["prediction"]["answer"].strip().lower() == answer.strip().lower() for answer in row["gold"]["answers"]) for row in answerable if row["prediction"]["decision"] == "ANSWER") / max(1, len(answerable)),
        "answer_f1": sum(answer_f1) / max(1, len(answerable)), "action_accuracy": correct_actions / max(1, len(predictions)),
        "unanswerable_precision": precision, "unanswerable_recall": recall, "unanswerable_f1": 2*precision*recall/max(1e-9, precision+recall),
        "false_answer_rate": sum(row["prediction"]["decision"] == "ANSWER" for row in unanswerable) / max(1, len(unanswerable)),
        "over_abstention_rate": sum(row["prediction"]["decision"] != "ANSWER" for row in answerable) / max(1, len(answerable)),
        "false_ask_rate": sum(row["prediction"]["decision"] == "ASK" for row in clear_samples) / max(1, len(clear_samples)),
        "meaningful_ask_rate": sum(row["gold"]["expected_action"] == "ASK" for row in asks) / max(1, len(asks)),
        "ask_recall": sum(row["prediction"]["decision"] == "ASK" for row in expected_asks) / max(1, len(expected_asks)),
        "unsupported_claim_rate": len(unsupported) / max(1, len(claims)),
        "hallucinated_answer_rate": sum(any(c.get("label") in ("UNSUPPORTED", "CONTRADICTED") for c in row.get("audit_claims", row.get("trace", {}).get("claims", []))) for row in answered) / max(1, len(answered)),
        "mean_latency_ms": statistics.mean([row["performance"]["latency_ms"] for row in predictions]) if predictions else 0,
        "p50_latency_ms": statistics.median([row["performance"]["latency_ms"] for row in predictions]) if predictions else 0,
        "p95_latency_ms": sorted([row["performance"]["latency_ms"] for row in predictions])[max(0, int(len(predictions) * .95) - 1)] if predictions else 0,
        "mean_input_tokens": statistics.mean([row["performance"]["input_tokens"] for row in predictions]) if predictions else 0,
        "mean_output_tokens": statistics.mean([row["performance"]["output_tokens"] for row in predictions]) if predictions else 0,
        "mean_llm_calls": statistics.mean([row["performance"]["llm_calls"] for row in predictions]) if predictions else 0,
        "estimated_cost_per_question": 0.0,  # local MLX inference; report hardware/energy separately if needed
    }


def markdown_table(results: dict[str, dict[str, Any]]) -> str:
    keys = ["answer_em", "answer_f1", "unanswerable_f1", "hallucinated_answer_rate", "unsupported_claim_rate", "over_abstention_rate", "false_ask_rate", "meaningful_ask_rate", "mean_latency_ms", "mean_llm_calls"]
    headers = " | ".join(["Metric", *results]); lines = [f"| {headers} |", "|" + "---|"*(len(results)+1)]
    for key in keys: lines.append("| " + " | ".join([key, *(f"{result[key]:.4f}" for result in results.values())]) + " |")
    return "\n".join(lines)
