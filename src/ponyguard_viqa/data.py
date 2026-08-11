from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from .core import normalize_text, read_jsonl, stable_hash, write_jsonl

SEED = 42


def extract_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept Hugging Face SQuAD-like rows and normalize answer variants."""
    context = normalize_text(str(raw.get("context", "")))
    answers = raw.get("answers") or {}
    if isinstance(answers, dict):
        answers = answers.get("text", [])
    impossible = bool(raw.get("is_impossible", False))
    return [{
        "question": normalize_text(str(raw.get("question", ""))), "context": context,
        "gold_answers": [normalize_text(str(x)) for x in answers if str(x).strip()],
        "is_answerable": not impossible, "expected_action": "ANSWER" if not impossible else "ABSTAIN",
        "plausible_answers": [normalize_text(str(x)) for x in (raw.get("plausible_answers") or [])],
        "source": "UIT-ViQuAD2.0",
    }]


def normalize_raw(raw_dir: str | Path, output: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(raw_dir).glob("*.jsonl")):
        for raw in read_jsonl(path):
            rows.extend(extract_rows(raw))
    for index, row in enumerate(rows, 1):
        row["sample_id"] = f"viquad_{index:06d}"
    write_jsonl(output, rows)
    return rows


def eda(rows: list[dict[str, Any]]) -> dict[str, Any]:
    questions = [row["question"] for row in rows]
    lengths = [len(row["context"].split()) for row in rows]
    return {
        "samples": len(rows), "answerable": sum(row["is_answerable"] for row in rows),
        "unanswerable": sum(not row["is_answerable"] for row in rows),
        "duplicate_questions": len(questions) - len(set(questions)),
        "mean_context_words": sum(lengths) / max(1, len(lengths)),
        "missing_questions": sum(not q for q in questions),
    }


def stratified_splits(rows: list[dict[str, Any]], sizes=(2000, 1000, 2000), seed=SEED) -> dict[str, list[dict[str, Any]]]:
    by_action: dict[str, list[dict[str, Any]]] = {"ANSWER": [], "ABSTAIN": []}
    for row in rows:
        by_action[row["expected_action"]].append(row)
    rng = random.Random(seed)
    for group in by_action.values(): rng.shuffle(group)
    offsets = {key: 0 for key in by_action}
    output: dict[str, list[dict[str, Any]]] = {}
    for name, size in zip(("dev", "validation", "test"), sizes):
        half = size // 2
        selected = []
        for action in ("ANSWER", "ABSTAIN"):
            part = by_action[action][offsets[action]:offsets[action] + half]
            if len(part) != half:
                raise ValueError(f"Need {half} {action} samples for {name}; dataset has too few")
            offsets[action] += half
            selected.extend(part)
        rng.shuffle(selected)
        output[name] = selected
    return output


def write_splits(rows: list[dict[str, Any]], out_dir: str | Path) -> dict[str, str]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, split in stratified_splits(rows).items():
        target = out_dir / f"{name}.jsonl"
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite frozen split: {target}")
        write_jsonl(target, split)
        digest = stable_hash([row["sample_id"] for row in split])
        (out_dir / f"{name}.manifest.json").write_text(json.dumps({"seed": SEED, "ids_sha256": digest, "count": len(split)}, indent=2))
        results[name] = digest
    return results


def verify_frozen_split(path: str | Path) -> None:
    path = Path(path); manifest = path.with_suffix(".manifest.json")
    if not manifest.exists(): raise FileNotFoundError(f"Missing frozen split manifest: {manifest}")
    expected = json.loads(manifest.read_text()).get("ids_sha256")
    actual = stable_hash([row["sample_id"] for row in read_jsonl(path)])
    if expected != actual: raise RuntimeError(f"Frozen split hash mismatch: {path}")


def clarification_set(rows: list[dict[str, Any]], limit: int = 100) -> list[dict[str, Any]]:
    """Deterministic separate ASK set; source examples are never mixed into main metrics."""
    candidates = [row for row in rows if row["is_answerable"] and len(row["question"].split()) >= 4]
    output = []
    for index, row in enumerate(candidates[:limit], 1):
        words = row["question"].split()
        question = "Người này " + " ".join(words[1:])
        output.append({"sample_id": f"clarify_{index:03d}", "question": question, "context": row["context"], "expected_action": "ASK", "missing_requirement": "entity", "source": "UIT-ViQuAD2.0-derived"})
    return output


def corpus(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = normalize_text(row["context"])
        if key: seen.setdefault(key, {"document_id": f"doc_{len(seen)+1:06d}", "text": key, "metadata": {"source": row["source"]}})
    return list(seen.values())
