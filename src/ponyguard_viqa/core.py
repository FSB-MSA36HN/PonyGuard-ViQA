from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

Action = Literal["ANSWER", "ASK", "ABSTAIN"]


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def stable_hash(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode()).hexdigest()


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\r\n", "\n").replace("\n", " ").split())


def add_clarification(question: str, clarification: str) -> str:
    """Clarification defines the request; it is never injected as retrieved evidence."""
    return f"{normalize_text(question)}\n\nThông tin làm rõ từ người dùng: {normalize_text(clarification)}"


def missing_requirements_from_question(question: str) -> list[str]:
    """Only genuine underspecification is eligible for ASK; LLM labels cannot add it."""
    text = normalize_text(question).lower()
    if "thông tin làm rõ từ người dùng:" in text: return []
    if re.search(r"\b(ông ấy|bà ấy|người này|người đó|người kia|nó|họ)\b", text): return ["entity"]
    if re.search(r"\bcó bao nhiêu\s*[?!.]*$", text): return ["requested_attribute"]
    return []


def tokenise(value: str) -> list[str]:
    return re.findall(r"\w+", normalize_text(value).lower(), flags=re.UNICODE)


def load_config(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    config = yaml.safe_load(path.read_text()) or {}
    parent = config.pop("extends", None)
    if parent:
        base = load_config(path.parent / parent)
        base.update(config)
        return base
    return config


@dataclass
class Chunk:
    document_id: str
    chunk_id: str
    text: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Requirement:
    entity: str | None = None
    requested_attribute: str | None = None
    answer_type: str = "text"
    question_clear: bool = True
    missing_requirements: list[str] = field(default_factory=list)
    clarification_question: str = ""


@dataclass
class PonyGuardState:
    sample_id: str | None
    question: str
    requirements: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    reasoning: dict[str, Any] = field(default_factory=dict)
    decision: Action | None = None
    decision_reason: str = ""
    draft_answer: str = ""
    claims: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
