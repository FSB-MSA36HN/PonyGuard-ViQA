from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import Action, Chunk, PonyGuardState, Requirement, missing_requirements_from_question, normalize_text
from .llm import LocalLLM
from .retrieval import Retriever

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{item.chunk_id}] {item.text}" for item in chunks)


def _prediction(sample: dict[str, Any], system: str, decision: Action, answer: str, chunks: list[Chunk], stats: list[Any], trace: dict[str, Any] | None = None, reason: str = "") -> dict[str, Any]:
    result = {
        "sample_id": sample.get("sample_id"), "system": system, "question": sample["question"],
        "gold": {"expected_action": sample.get("expected_action"), "answers": sample.get("gold_answers", [])},
        "prediction": {"decision": decision, "answer": answer, "reason": reason},
        "retrieval": {"chunk_ids": [chunk.chunk_id for chunk in chunks], "document_ids": [chunk.document_id for chunk in chunks], "texts": [chunk.text for chunk in chunks], "scores": [chunk.score for chunk in chunks]},
        "performance": {"latency_ms": sum(s.latency_ms for s in stats), "input_tokens": sum(s.input_tokens for s in stats), "output_tokens": sum(s.output_tokens for s in stats), "llm_calls": len(stats)},
    }
    if trace is not None: result["trace"] = trace
    return result


class BasicRAG:
    def __init__(self, retriever: Retriever, llm: LocalLLM, top_k: int = 5): self.retriever, self.llm, self.top_k = retriever, llm, top_k
    def run(self, sample: dict[str, Any]) -> dict[str, Any]:
        chunks = self.retriever.retrieve(sample["question"], self.top_k)
        result = self.llm.generate(f"{prompt('basic_rag_v2.txt')}\nQuestion: {sample['question']}\nContext:\n{context(chunks)}")
        return _prediction(sample, "basic_rag", "ANSWER", result.text, chunks, [result])


class PromptSafeRAG(BasicRAG):
    def run(self, sample: dict[str, Any]) -> dict[str, Any]:
        chunks = self.retriever.retrieve(sample["question"], self.top_k)
        parsed, result = self.llm.json(f"{prompt('prompt_safe_rag_v2.txt')}\nQuestion: {sample['question']}\nContext:\n{context(chunks)}")
        decision = parsed.get("decision", "ABSTAIN")
        if decision not in ("ANSWER", "ABSTAIN"): decision = "ABSTAIN"
        return _prediction(sample, "prompt_safe_rag", decision, str(parsed.get("answer", "")), chunks, [result])


class PonyGuard:
    def __init__(self, retriever: Retriever, llm: LocalLLM, top_k: int = 5, enabled: dict[str, bool] | None = None):
        self.retriever, self.llm, self.top_k = retriever, llm, top_k
        self.enabled = {"requirement": True, "inference": True, "verification": True, **(enabled or {})}

    @staticmethod
    def decide(requirement: Requirement, evidence: dict[str, Any]) -> Action:
        if requirement.missing_requirements: return "ASK"
        answerable = evidence.get("answerable_from_evidence", evidence.get("evidence_sufficient"))
        if not all((evidence.get("entity_match"), evidence.get("attribute_match"), answerable)) or evidence.get("conflict_detected"): return "ABSTAIN"
        if not evidence.get("reasoning_allowed") or evidence.get("inference_level") == "UNSUPPORTED": return "ABSTAIN"
        return "ANSWER"

    @staticmethod
    def apply_clarity_guard(question: str, requirement: Requirement) -> Requirement:
        """The model may describe a requirement but may not invent an ASK state."""
        missing = missing_requirements_from_question(question)
        requirement.missing_requirements = missing
        requirement.question_clear = not missing
        if not missing: requirement.clarification_question = ""
        return requirement

    @staticmethod
    def decision_rationale(requirement: Requirement, evidence: dict[str, Any], decision: Action) -> str:
        if decision == "ASK": return f"Thiếu thông tin bắt buộc: {', '.join(requirement.missing_requirements)}."
        if decision == "ANSWER": return str(evidence.get("decision_rationale") or "Evidence đáp ứng entity, thuộc tính và mức suy luận cho phép.")
        if evidence.get("conflict_detected"): return "Các chunks có evidence mâu thuẫn."
        missing = evidence.get("missing_evidence") or []
        return str(evidence.get("decision_rationale") or (f"Evidence chưa đủ: {', '.join(missing)}." if missing else "Retrieved evidence chưa đủ để trả lời an toàn."))

    @staticmethod
    def final_gate(claims: list[dict[str, Any]], draft_answer: str) -> tuple[Action, str]:
        """Keep supported atomic claims; abstain when none of the answer survives."""
        good = [claim.get("text", "") for claim in claims if claim.get("label") in ("SUPPORTED", "INFERRED_SUPPORTED")]
        if not claims or len(good) == len(claims): return "ANSWER", draft_answer
        return ("ANSWER", " ".join(good)) if good else ("ABSTAIN", "Tài liệu hiện có không đủ bằng chứng để trả lời an toàn.")

    @staticmethod
    def clarification_question(requirement: Requirement, question: str = "") -> str:
        generated = requirement.clarification_question.strip()
        if generated and (not question or normalize_text(question).lower() not in normalize_text(generated).lower()): return generated
        if "entity" in requirement.missing_requirements:
            return f"Bạn đang hỏi {requirement.requested_attribute or 'thông tin này'} của ai hoặc đối tượng nào?"
        if "requested_attribute" in requirement.missing_requirements:
            return f"Bạn muốn biết thuộc tính hoặc thông tin nào về {requirement.entity or 'đối tượng đó'}?"
        return "Bạn có thể làm rõ chính xác thông tin cần hỏi không?"

    def run(self, sample: dict[str, Any]) -> dict[str, Any]:
        state = PonyGuardState(sample.get("sample_id"), sample["question"]); stats = []
        req_json, response = self.llm.json(f"{prompt('requirement_analyzer_v3.txt')}\nQuestion: {sample['question']}"); stats.append(response)
        requirement = Requirement(**{key: req_json.get(key) for key in Requirement.__dataclass_fields__ if key in req_json})
        requirement = self.apply_clarity_guard(sample["question"], requirement)
        state.requirements = requirement.__dict__
        chunks = self.retriever.retrieve(sample["question"], self.top_k); state.retrieval = {"chunks": [c.to_dict() for c in chunks]}
        evidence_json, response = self.llm.json(f"{prompt('evidence_checker_v2.txt')}\nRequirement: {json.dumps(state.requirements, ensure_ascii=False)}\nChunks:\n{context(chunks)}"); stats.append(response)
        evidence_json["answerable_from_evidence"] = bool(evidence_json.get("answerable_from_evidence", evidence_json.get("evidence_sufficient")))
        state.evidence = evidence_json; state.reasoning = {"level": evidence_json.get("inference_level"), "allowed": evidence_json.get("reasoning_allowed")}
        decision = self.decide(requirement, evidence_json) if self.enabled["requirement"] and self.enabled["inference"] else ("ANSWER" if evidence_json.get("evidence_sufficient") else "ABSTAIN")
        reason = self.decision_rationale(requirement, evidence_json, decision)
        state.decision, state.decision_reason = decision, reason
        if decision != "ANSWER":
            answer = self.clarification_question(requirement, sample["question"]) if decision == "ASK" else "Tài liệu hiện có không đủ bằng chứng để trả lời an toàn."
            state.final_answer = answer; state.metrics = {"llm_calls": len(stats)}
            return _prediction(sample, "ponyguard", decision, answer, chunks, stats, state.to_dict(), reason)
        supports = [chunk for chunk in chunks if chunk.chunk_id in evidence_json.get("supporting_chunk_ids", [])] or chunks[:1]
        draft = self.llm.generate(f"{prompt('basic_rag_v2.txt')}\nQuestion: {sample['question']}\nSupporting evidence:\n{context(supports)}"); stats.append(draft); state.draft_answer = draft.text
        verified, response = self.llm.json(f"{prompt('claim_verifier_v1.txt')}\nAnswer: {draft.text}\nEvidence:\n{context(supports)}"); stats.append(response)
        claims = verified.get("claims", []); state.claims = claims
        decision, answer = self.final_gate(claims, draft.text) if self.enabled["verification"] else ("ANSWER", draft.text)
        reason = self.decision_rationale(requirement, evidence_json, decision)
        state.decision, state.decision_reason, state.final_answer, state.metrics = decision, reason, answer, {"llm_calls": len(stats)}
        return _prediction(sample, "ponyguard", decision, answer, chunks, stats, state.to_dict(), reason)
