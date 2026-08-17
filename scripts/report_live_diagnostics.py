from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from ponyguard_viqa.core import normalize_text, read_jsonl
from ponyguard_viqa.evaluation import f1


def answer_score(answer: str, gold: str) -> float:
    answer, gold = normalize_text(answer).casefold(), normalize_text(gold).casefold()
    if not answer or not gold: return 0.0
    if gold in answer or answer in gold: return 1.0
    gold_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", gold))
    answer_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", answer))
    if gold_numbers: return len(gold_numbers & answer_numbers) / len(gold_numbers)
    return f1(answer, gold)


def assess(expected: dict, prediction: dict) -> tuple[bool, str]:
    actual = prediction["prediction"]
    decision = actual["decision"]
    if decision != expected["expected_action"]:
        return False, f"action expected {expected['expected_action']}, got {decision}"
    if decision == "ANSWER":
        score = max((answer_score(actual["answer"], answer) for answer in expected["gold_answers"]), default=0.0)
        if score < 0.8:
            return False, f"answer F1 {score:.2f} < 0.80"
        if not actual.get("grounding", {}).get("valid"):
            return False, "answer has invalid grounding"
    if decision == "ASK":
        answer = normalize_text(actual["answer"])
        if len(answer) < 12 or normalize_text(expected["question"]).casefold() in answer.casefold():
            return False, "clarification is empty, too short, or merely echoes the question"
    if decision == "ABSTAIN" and not actual.get("reason"):
        return False, "abstention has no recorded reason"
    return True, "pass"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="data/diagnostics/ponyguard_behavioral_live.jsonl")
    parser.add_argument("--predictions", default="runs/ponyguard/ponyguard_behavioral_live_predictions.jsonl")
    parser.add_argument("--output", default="reports/PONYGUARD_LIVE_BEHAVIORAL_REPORT.md")
    args = parser.parse_args()
    fixture = {row["sample_id"]: row for row in read_jsonl(args.fixture)}
    rows = read_jsonl(args.predictions)
    results = []
    for row in rows:
        expected = fixture.get(row["sample_id"])
        if expected:
            passed, detail = assess(expected, row)
            results.append((expected, row, passed, detail))
    missing = sorted(set(fixture) - {row["sample_id"] for row in rows})
    counts = Counter("pass" if passed else "fail" for _, _, passed, _ in results)
    lines = ["# PonyGuard live behavioural report", "", "## Summary", "", f"- Cases executed: {len(results)}/{len(fixture)}", f"- Passed: {counts['pass']}", f"- Failed: {counts['fail']}", f"- Missing outputs: {len(missing)}", "", "## Per-case results", "", "| Category | Expected | Actual | Result | Detail |", "| --- | --- | --- | --- | --- |"]
    for expected, row, passed, detail in results:
        actual = row["prediction"]
        lines.append(f"| {expected['diagnostic_category']} | {expected['expected_action']} | {actual['decision']} | {'PASS' if passed else 'FAIL'} | {detail} |")
    if missing:
        lines += ["", "## Missing outputs", "", *[f"- `{sample_id}`" for sample_id in missing]]
    lines += ["", "## Interpretation", "", "This is a development diagnostic suite, not the frozen final benchmark. A PASS means the configured live model produced the expected action and passed the applicable answer/citation, clarification, or refusal contract. A FAIL identifies a reproducible case to inspect and add as a deterministic regression after root-cause analysis."]
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
