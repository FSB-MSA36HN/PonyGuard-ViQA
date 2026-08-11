from __future__ import annotations
import argparse, json, random
from collections import Counter
from pathlib import Path
from ponyguard_viqa.core import read_jsonl

def category(row):
    if row["gold"]["expected_action"] == "ABSTAIN" and row["prediction"]["decision"] == "ANSWER": return "UNSUPPORTED_INFERENCE"
    if row["gold"]["expected_action"] == "ANSWER" and row["prediction"]["decision"] != "ANSWER": return "OVER_ABSTENTION"
    evidence = row.get("trace", {}).get("evidence", {})
    if not evidence.get("entity_match", True): return "ENTITY_MISMATCH"
    if not evidence.get("attribute_match", True): return "ATTRIBUTE_MISMATCH"
    return "ANSWER_GENERATION_ERROR"

def main():
    p = argparse.ArgumentParser(); p.add_argument("--predictions", default="runs/ponyguard/test_predictions.jsonl"); p.add_argument("--limit", type=int, default=100); args = p.parse_args()
    failures = [row for row in read_jsonl(args.predictions) if row["gold"]["expected_action"] != row["prediction"]["decision"]]
    random.Random(42).shuffle(failures); failures = failures[:args.limit]
    report = {"counts": Counter(category(row) for row in failures), "examples": [{"sample_id": r["sample_id"], "category": category(r), "question": r["question"], "prediction": r["prediction"]} for r in failures]}
    Path("reports/error_analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=dict)); print(json.dumps(report["counts"], indent=2, default=dict))

if __name__ == "__main__": main()
