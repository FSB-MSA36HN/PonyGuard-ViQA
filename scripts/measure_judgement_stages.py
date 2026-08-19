"""Measure the two judgement stages per provider, without running the pipeline.

Intent and relation are the stages whose output is a decision rather than an
extraction. Both are cheap to probe in isolation: intent carries no retrieved
context at all, and relation carries only the chunks a recorded run already
selected. This reports how each candidate provider does on both, so stage
routing is decided from measurement instead of assumption.

Read-only: it never writes to runs/ and changes no production behaviour.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ponyguard_viqa.core import Chunk, load_config, read_jsonl
from ponyguard_viqa.llm import GeminiLLM, LocalLLM, ProviderQuotaError, gemini_api_key
from ponyguard_viqa.pipelines import PonyGuard, context, prompt


def provider_llm(model_config: dict, model: str) -> LocalLLM:
    """Build one named provider with no automatic fallback.

    A measurement must not silently degrade to another model: an unavailable
    provider has to surface as an error, not as a second copy of the local
    result wearing the remote provider's label.
    """
    if model.startswith("gemini"):
        return GeminiLLM(model, gemini_api_key(), model_config["max_tokens"])
    return LocalLLM(model_config["name"] if model == "local" else model, "mlx", model_config["max_tokens"])

FIXTURES = ["data/diagnostics/ponyguard_behavioral_live.jsonl", "data/diagnostics/ponyguard_holdout_live.jsonl"]
PREDICTIONS = ["runs/ponyguard/ponyguard_behavioral_live_predictions.jsonl", "runs/ponyguard/ponyguard_holdout_live_predictions.jsonl"]


def intent_probe(pipeline: PonyGuard, row: dict) -> dict:
    """Run the production intent path and record whether it would ask."""
    try:
        requirement, response = pipeline.analyze_intent(row["question"], {})
    except (ProviderQuotaError, RuntimeError) as error:
        return {"sample_id": row["sample_id"], "error": str(error)}
    missing = list(requirement.missing_requirements) if requirement else []
    expected_ask = row["expected_action"] == "ASK"
    return {
        "sample_id": row["sample_id"], "expected_ask": expected_ask, "asked": bool(missing),
        "missing": missing, "correct": bool(missing) == expected_ask,
        "bindings": requirement.slot_bindings if requirement else [],
        "served_by": f"{response.provider}:{response.model}",
    }


def relation_probes(prediction_paths: list[str]) -> list[dict]:
    """Reuse the candidates a recorded run actually produced, with their chunks."""
    probes = []
    for path in prediction_paths:
        if not Path(path).exists():
            continue
        for row in read_jsonl(path):
            supports = PonyGuard.support_items(row.get("trace", {}).get("evidence", {}))
            direct = [item for item in supports if not PonyGuard.is_inference(item) and item.get("evidence_quote")]
            if not direct:
                continue
            chunks = [Chunk(d, c, t) for d, c, t in zip(row["retrieval"]["document_ids"], row["retrieval"]["chunk_ids"], row["retrieval"]["texts"])]
            probes.append({
                "sample_id": row["sample_id"], "question": row["question"], "chunks": chunks,
                "candidates": [{key: item.get(key, "") for key in ("chunk_id", "evidence_quote", "candidate_answer")} for item in direct[:2]],
                "expect_match": row["gold"]["expected_action"] == "ANSWER",
            })
    return probes


def relation_probe(llm, probe: dict) -> dict:
    request = (f"{prompt('relation_verifier_v1.txt')}\nQuestion: {probe['question']}\n"
               f"Candidates: {json.dumps(probe['candidates'], ensure_ascii=False)}\nChunks:\n{context(probe['chunks'])}")
    try:
        value, response = llm.json(request, 256)
    except (ProviderQuotaError, RuntimeError) as error:
        return {"sample_id": probe["sample_id"], "error": str(error)}
    verdicts = [str(item.get("verdict", "")).upper() for item in value.get("verdicts", []) if isinstance(item, dict)]
    matched = bool(verdicts) and all(verdict == "MATCH" for verdict in verdicts)
    return {
        "sample_id": probe["sample_id"], "expect_match": probe["expect_match"], "matched": matched,
        "verdicts": verdicts, "correct": matched == probe["expect_match"],
        "served_by": f"{response.provider}:{response.model}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True, help="providers to compare, e.g. local gemini-3.6-flash")
    parser.add_argument("--stages", nargs="+", default=["intent", "relation"], choices=["intent", "relation"])
    parser.add_argument("--output", default="reports/PONYGUARD_JUDGEMENT_CAPABILITY.md")
    args = parser.parse_args()

    config = load_config("configs/ponyguard.yaml")
    rows = [row for path in FIXTURES if Path(path).exists() for row in read_jsonl(path)]
    probes = relation_probes(PREDICTIONS) if "relation" in args.stages else []
    results: dict[str, dict] = {}

    for model in args.models:
        llm = provider_llm(config["model"], model)
        pipeline = PonyGuard(None, llm, stage_tokens=config["model"].get("stage_max_tokens"), intent_first=True)
        entry: dict = {}
        if "intent" in args.stages:
            entry["intent"] = [intent_probe(pipeline, row) for row in rows]
            print(f"[{model}] intent {sum(1 for r in entry['intent'] if r.get('correct'))}/{len(rows)}")
        if "relation" in args.stages:
            entry["relation"] = [relation_probe(llm, probe) for probe in probes]
            print(f"[{model}] relation {sum(1 for r in entry['relation'] if r.get('correct'))}/{len(probes)}")
        results[model] = entry

    lines = ["# Judgement-stage capability by provider", "",
             "Intent and relation probed in isolation. Intent runs the production path;",
             "relation replays candidates a recorded run produced. Read-only measurement.", ""]
    for stage in args.stages:
        lines += [f"## {stage}", "", "| Provider | Served by | Correct | Errors | Failing cases |", "| --- | --- | ---: | ---: | --- |"]
        for model, entry in results.items():
            items = entry.get(stage, [])
            errors = [item for item in items if item.get("error")]
            wrong = [item["sample_id"] for item in items if not item.get("error") and not item.get("correct")]
            served = sorted({item["served_by"] for item in items if item.get("served_by")}) or ["—"]
            lines.append(f"| `{model}` | {', '.join(f'`{s}`' for s in served)} | {sum(1 for i in items if i.get('correct'))}/{len(items) - len(errors)} | {len(errors)} | {', '.join(f'`{w}`' for w in wrong) or '—'} |")
        lines.append("")
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    Path(args.output).with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(args.output)
    for model, entry in results.items():
        for stage, items in entry.items():
            print(model, stage, Counter("error" if i.get("error") else "ok" if i.get("correct") else "wrong" for i in items))


if __name__ == "__main__":
    main()
