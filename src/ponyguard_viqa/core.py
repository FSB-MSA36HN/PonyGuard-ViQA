from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

Action = Literal["ANSWER", "ASK", "ABSTAIN"]
MISSING_REQUIREMENT_SLOTS = frozenset({"entity", "requested_attribute", "country", "location", "time", "scope", "reference", "target"})
REQUIRED_REQUIREMENT_SLOTS = frozenset({"entity", "requested_attribute"})
SLOT_RESOLUTIONS = frozenset({"RESOLVED", "REFERENTIAL", "ABSENT"})
# The dimension an interrogative asks for is the requested value, never a missing
# input. Derived from the answer-type enum, so it holds for any question wording.
# Strictly the dimension the answer type *is*: a sibling dimension can still be a
# genuine missing input, as in a location question whose jurisdiction is a
# referential span ("the capital of that country is where?").
ANSWER_TYPE_SATISFIES = {"TIME": frozenset({"time"}), "DATE": frozenset({"time"}), "LOCATION": frozenset({"location"})}


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


def normalized_contains(text: str, part: str) -> bool:
    """Whitespace/case-insensitive literal evidence check."""
    return normalize_text(part).casefold() in normalize_text(text).casefold()


def answer_matches_quote(answer: str, quote: str) -> bool:
    """Reject a generated value when its numbers/dates/names are absent from its quote."""
    answer, quote = normalize_text(answer), normalize_text(quote)
    if not answer or not quote:
        return False
    if normalized_contains(quote, answer):
        return True
    numbers = re.findall(r"\d+(?:[.,]\d+)*", answer)
    if numbers:
        quote_numbers = {value.replace(",", ".") for value in re.findall(r"\d+(?:[.,]\d+)*", quote)}
        return all(value.replace(",", ".") in quote_numbers for value in numbers)
    words = [word for word in tokenise(answer) if len(word) >= 3 and word not in {"các", "được", "trong", "theo", "với", "của", "cho", "là"}]
    return bool(words) and all(word in tokenise(quote) for word in words)


def add_clarification(question: str, clarification: str) -> str:
    """Clarification defines the request; it is never injected as retrieved evidence."""
    return f"{normalize_text(question)}\n\nThông tin làm rõ từ người dùng: {normalize_text(clarification)}"


def resolved_question(question: str) -> str:
    """Use a complete follow-up question as the request, otherwise retain its context."""
    _, marker, clarification = question.partition("\n\nThông tin làm rõ từ người dùng:")
    clarification = normalize_text(clarification)
    return clarification if marker and clarification.endswith("?") else question


def intent_slot_bindings(question: str, raw: Any, answer_type: str = "") -> tuple[list[dict[str, Any]], list[str]]:
    """Bind each claimed slot to a literal question span, then decide resolution locally.

    A slot counts as unresolved only when the model quotes the question verbatim
    and labels that span referential, or declares a required slot absent. Any
    malformed, non-literal or optional-`ABSENT` binding is ignored, so a bad
    contract can never manufacture a clarification for a clear question. A slot
    the answer type shows the question is asking for is likewise never missing:
    an interrogative states the requested value, it does not reference one.
    """
    requested = ANSWER_TYPE_SATISFIES.get(normalize_text(str(answer_type)).upper(), frozenset())
    bindings: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        slot = normalize_text(str(item.get("slot", ""))).lower()
        status = normalize_text(str(item.get("status", ""))).upper()
        span = normalize_text(str(item.get("span", "")))
        if slot not in MISSING_REQUIREMENT_SLOTS or status not in SLOT_RESOLUTIONS:
            continue
        literal = bool(span) and normalized_contains(question, span)
        interrogative = slot in requested
        binding = {"slot": slot, "span": span, "status": status, "literal": literal, "interrogative": interrogative}
        if binding not in bindings:
            bindings.append(binding)
        if interrogative:
            continue
        if (status == "REFERENTIAL" and literal) or (status == "ABSENT" and slot in REQUIRED_REQUIREMENT_SLOTS):
            unresolved.append(slot)
    return bindings, list(dict.fromkeys(unresolved))


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
    # An omitted model field is unresolved, never implicitly a clear request.
    question_clear: bool = False
    missing_requirements: list[str] = field(default_factory=list)
    clarification_question: str = ""
    ambiguity_type: str = "NONE"
    clarification_options: list[str] = field(default_factory=list)
    population_scope: str = "UNSPECIFIED"
    time_scope: str = "UNSPECIFIED"
    inclusion_constraints: list[str] = field(default_factory=list)
    slot_bindings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PonyGuardState:
    sample_id: str | None
    question: str
    requirements: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    reasoning: dict[str, Any] = field(default_factory=dict)
    decision: Action | None = None
    decision_reason: str = ""
    draft_answer: str = ""
    claims: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
