from __future__ import annotations

import json
import re
from time import perf_counter
from pathlib import Path
from typing import Any

from .core import Action, Chunk, PonyGuardState, Requirement, answer_matches_quote, missing_requirements_from_question, normalized_contains, normalize_text, question_ambiguity
from .llm import LocalLLM
from .retrieval import Retriever

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{item.chunk_id}] {item.text}" for item in chunks)


def _prediction(sample: dict[str, Any], system: str, decision: Action, answer: str, chunks: list[Chunk], stats: list[Any], trace: dict[str, Any] | None = None, reason: str = "", grounding: dict[str, Any] | None = None, timings: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "sample_id": sample.get("sample_id"), "system": system, "question": sample["question"],
        "gold": {"expected_action": sample.get("expected_action"), "answers": sample.get("gold_answers", [])},
        "prediction": {"decision": decision, "answer": answer, "reason": reason, "grounding": grounding or {"valid": False, "citation_chunk_ids": [], "evidence_quote": ""}},
        "retrieval": {"chunk_ids": [chunk.chunk_id for chunk in chunks], "document_ids": [chunk.document_id for chunk in chunks], "texts": [chunk.text for chunk in chunks], "scores": [chunk.score for chunk in chunks]},
        "performance": {"latency_ms": sum(s.latency_ms for s in stats), "input_tokens": sum(s.input_tokens for s in stats), "output_tokens": sum(s.output_tokens for s in stats), "llm_calls": sum(s.calls for s in stats), "stages": timings or {}},
    }
    if trace is not None: result["trace"] = trace
    return result


def validate_grounding(value: dict[str, Any], chunks: list[Chunk]) -> tuple[dict[str, Any], list[str]]:
    """Validate LLM-provided literal evidence without a second model or dependency."""
    ids = value.get("citation_chunk_ids", [])
    if not isinstance(ids, list) or not ids:
        return {"valid": False, "citation_chunk_ids": [], "evidence_quote": ""}, ["Thiếu citation_chunk_ids."]
    quote, answer = str(value.get("evidence_quote", "")).strip(), str(value.get("answer", "")).strip()
    cited = [chunk for chunk in chunks if chunk.chunk_id in ids]
    if len(cited) != len(set(ids)):
        return {"valid": False, "citation_chunk_ids": ids, "evidence_quote": quote}, ["Citation chunk ID không thuộc retrieved context."]
    if not any(normalized_contains(chunk.text, quote) for chunk in cited):
        return {"valid": False, "citation_chunk_ids": ids, "evidence_quote": quote}, ["Evidence quote không xuất hiện nguyên văn trong cited chunk."]
    if not answer_matches_quote(answer, quote):
        return {"valid": False, "citation_chunk_ids": ids, "evidence_quote": quote}, ["Answer có giá trị không xuất hiện trong evidence quote."]
    return {"valid": True, "citation_chunk_ids": ids, "evidence_quote": quote}, []


def _timed_json(llm: LocalLLM, label: str, value: str, max_tokens: int, timings: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    started = perf_counter(); parsed, response = llm.json(value, max_tokens); elapsed = (perf_counter()-started)*1000
    timings[label] = {"ms": round(elapsed, 2), "llm_calls": response.calls, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "cold_model_load_ms": round(response.model_load_ms, 2)}
    return parsed, response


def grounded_generation(llm: LocalLLM, instruction: str, question: str, chunks: list[Chunk], max_tokens: int, timings: dict[str, Any], label: str = "answer") -> tuple[dict[str, Any], list[Any], list[str]]:
    """One structured call plus one format-only retry when grounding is invalid."""
    request = f"{instruction}\nQuestion: {question}\nContext:\n{context(chunks)}"
    value, response = _timed_json(llm, label, request, max_tokens, timings)
    grounding, errors = validate_grounding(value, chunks)
    if grounding["valid"]:
        return value, [response], []
    repair = (f"{instruction}\nSửa JSON trước để answer, citation_chunk_ids và evidence_quote đều được grounded. "
              f"Chỉ dùng Context sau, không đổi câu hỏi.\nQuestion: {question}\nContext:\n{context(chunks)}\nPrevious JSON: {json.dumps(value, ensure_ascii=False)}")
    value, retry = _timed_json(llm, f"{label}_grounding_retry", repair, max_tokens, timings)
    grounding, errors = validate_grounding(value, chunks)
    value["grounding"] = grounding
    return value, [response, retry], errors


class BasicRAG:
    def __init__(self, retriever: Retriever, llm: LocalLLM, top_k: int = 5, stage_tokens: dict[str, int] | None = None): self.retriever, self.llm, self.top_k, self.stage_tokens = retriever, llm, top_k, {"answer": 128, **(stage_tokens or {})}
    def run(self, sample: dict[str, Any]) -> dict[str, Any]:
        timings: dict[str, Any] = {}; chunks = self.retriever.retrieve(sample["question"], self.top_k); timings["retrieval"] = getattr(self.retriever, "last_timing", {})
        value, stats, errors = grounded_generation(self.llm, prompt("basic_rag_v3.txt"), sample["question"], chunks, self.stage_tokens["answer"], timings)
        grounding = value.get("grounding") or validate_grounding(value, chunks)[0]
        decision: Action = "ANSWER" if grounding["valid"] else "ABSTAIN"
        answer = str(value.get("answer", "")) if decision == "ANSWER" else "Tài liệu hiện có không đủ bằng chứng đã kiểm chứng để trả lời an toàn."
        return _prediction(sample, "basic_rag", decision, answer, chunks, stats, reason="" if grounding["valid"] else "invalid_grounding", grounding=grounding, timings=timings)


class PromptSafeRAG(BasicRAG):
    def run(self, sample: dict[str, Any]) -> dict[str, Any]:
        timings: dict[str, Any] = {}; chunks = self.retriever.retrieve(sample["question"], self.top_k); timings["retrieval"] = getattr(self.retriever, "last_timing", {})
        parsed, stats, errors = grounded_generation(self.llm, prompt("prompt_safe_rag_v3.txt"), sample["question"], chunks, self.stage_tokens["answer"], timings)
        decision = parsed.get("decision", "ABSTAIN")
        if decision not in ("ANSWER", "ABSTAIN"): decision = "ABSTAIN"
        grounding = parsed.get("grounding") or validate_grounding(parsed, chunks)[0]
        if decision == "ANSWER" and not grounding["valid"]: decision = "ABSTAIN"
        answer = str(parsed.get("answer", "")) if decision == "ANSWER" else "Tài liệu hiện có không đủ bằng chứng đã kiểm chứng để trả lời an toàn."
        return _prediction(sample, "prompt_safe_rag", decision, answer, chunks, stats, reason="" if grounding["valid"] else "invalid_grounding", grounding=grounding, timings=timings)


class PonyGuard:
    def __init__(self, retriever: Retriever, llm: LocalLLM, top_k: int = 5, enabled: dict[str, bool] | None = None, stage_tokens: dict[str, int] | None = None):
        self.retriever, self.llm, self.top_k = retriever, llm, top_k
        self.enabled = {"requirement": True, "inference": True, "verification": True, **(enabled or {})}
        self.stage_tokens = {"requirement": 80, "evidence": 256, "answer": 128, "verification": 128, **(stage_tokens or {})}

    @staticmethod
    def decide(requirement: Requirement, evidence: dict[str, Any]) -> Action:
        if requirement.missing_requirements: return "ASK"
        if not all((evidence.get("entity_match"), evidence.get("attribute_match"), evidence.get("valid_supports"))) or evidence.get("conflict_detected"): return "ABSTAIN"
        if not evidence.get("reasoning_allowed") or evidence.get("inference_level") == "UNSUPPORTED": return "ABSTAIN"
        return "ANSWER"

    @staticmethod
    def apply_clarity_guard(question: str, requirement: Requirement) -> Requirement:
        """The model may describe a requirement but may not invent an ASK state."""
        missing, ambiguity = question_ambiguity(question)
        requirement.missing_requirements = missing
        requirement.question_clear = not missing
        requirement.ambiguity_type = ambiguity
        if ambiguity == "AMBIGUOUS_ATTRIBUTE" and not requirement.entity:
            match = re.search(r"^(?:hiện tại\s+)?(.+?)\s+(?:có\s+)?(?:bao\s+nhiêu|mấy)(?:\s+(?:cái|người))?\s*[?!.]*$", normalize_text(question), re.I)
            if match: requirement.entity = match.group(1).strip()
        requirement.clarification_options = PonyGuard.valid_options(requirement.clarification_options) if ambiguity == "AMBIGUOUS_ATTRIBUTE" else []
        if ambiguity == "AMBIGUOUS_ATTRIBUTE" and not requirement.clarification_options: requirement.clarification_options = ["người", "tỉnh/thành", "cấp học"]
        if not missing: requirement.clarification_question = ""
        return requirement

    @staticmethod
    def valid_options(options: Any) -> list[str]:
        if not isinstance(options, list): return []
        value = []
        for option in options:
            option = normalize_text(str(option))
            if 2 <= len(option) <= 40 and option not in value and not re.search(r"\d", option): value.append(option)
            if len(value) == 3: break
        return value

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
        if not claims: return "ABSTAIN", "Tài liệu hiện có không đủ bằng chứng để trả lời an toàn."
        if len(good) == len(claims): return "ANSWER", draft_answer
        return ("ANSWER", " ".join(good)) if good else ("ABSTAIN", "Tài liệu hiện có không đủ bằng chứng để trả lời an toàn.")

    @staticmethod
    def clarification_question(requirement: Requirement, question: str = "") -> str:
        if requirement.ambiguity_type == "AMBIGUOUS_ATTRIBUTE":
            entity = requirement.entity or "đối tượng này"
            options = requirement.clarification_options
            return f"Bạn muốn biết {entity} có mấy {', '.join(options[:-1])} hay mấy {options[-1]}?"
        generated = requirement.clarification_question.strip()
        if generated and (not question or normalize_text(question).lower() not in normalize_text(generated).lower()): return generated
        if "entity" in requirement.missing_requirements:
            return f"Bạn đang hỏi {requirement.requested_attribute or 'thông tin này'} của ai hoặc đối tượng nào?"
        if "requested_attribute" in requirement.missing_requirements:
            return f"Bạn muốn biết thuộc tính hoặc thông tin nào về {requirement.entity or 'đối tượng đó'}?"
        return "Bạn có thể làm rõ chính xác thông tin cần hỏi không?"

    def run(self, sample: dict[str, Any]) -> dict[str, Any]:
        state = PonyGuardState(sample.get("sample_id"), sample["question"]); stats = []; timings: dict[str, Any] = {}
        req_json, response = _timed_json(self.llm, "requirement", f"{prompt('requirement_analyzer_v4.txt')}\nQuestion: {sample['question']}", self.stage_tokens["requirement"], timings); stats.append(response)
        requirement = Requirement(**{key: req_json.get(key) for key in Requirement.__dataclass_fields__ if key in req_json})
        requirement = self.apply_clarity_guard(sample["question"], requirement)
        state.requirements = requirement.__dict__
        if requirement.missing_requirements:
            decision: Action = "ASK"; answer = self.clarification_question(requirement, sample["question"])
            reason = self.decision_rationale(requirement, {}, decision)
            state.decision, state.decision_reason, state.final_answer = decision, reason, answer
            state.metrics = {"llm_calls": sum(item.calls for item in stats)}
            return _prediction(sample, "ponyguard", decision, answer, [], stats, state.to_dict(), reason, timings=timings)
        chunks = self.retriever.retrieve(sample["question"], self.top_k); timings["retrieval"] = getattr(self.retriever, "last_timing", {}); state.retrieval = {"chunks": [c.to_dict() for c in chunks]}
        evidence_json, response = _timed_json(self.llm, "evidence", f"{prompt('evidence_extractor_v3.txt')}\nRequirement: {json.dumps(state.requirements, ensure_ascii=False)}\nChunks:\n{context(chunks)}", self.stage_tokens["evidence"], timings); stats.append(response)
        supports, rejected = self.validated_supports(evidence_json, chunks)
        evidence_json["valid_supports"] = supports
        evidence_json["support_rejections"] = rejected
        evidence_json["answerable_from_evidence"] = bool(supports)
        evidence_json["evidence_sufficient"] = bool(supports)
        state.evidence = evidence_json; state.reasoning = {"level": evidence_json.get("inference_level"), "allowed": evidence_json.get("reasoning_allowed")}
        decision = self.decide(requirement, evidence_json) if self.enabled["requirement"] and self.enabled["inference"] else ("ANSWER" if evidence_json.get("evidence_sufficient") else "ABSTAIN")
        reason = self.decision_rationale(requirement, evidence_json, decision)
        state.decision, state.decision_reason = decision, reason
        if decision != "ANSWER":
            answer = self.clarification_question(requirement, sample["question"]) if decision == "ASK" else "Tài liệu hiện có không đủ bằng chứng để trả lời an toàn."
            state.final_answer = answer; state.metrics = {"llm_calls": sum(item.calls for item in stats)}
            return _prediction(sample, "ponyguard", decision, answer, chunks, stats, state.to_dict(), reason, timings=timings)
        support_chunks = [chunk for chunk in chunks if chunk.chunk_id in {item["chunk_id"] for item in supports}]
        draft_json, draft_stats, draft_errors = grounded_generation(self.llm, prompt("basic_rag_v3.txt"), sample["question"], support_chunks, self.stage_tokens["answer"], timings); stats.extend(draft_stats)
        grounding = draft_json.get("grounding") or validate_grounding(draft_json, support_chunks)[0]
        if not grounding["valid"]:
            state.evidence["draft_rejections"] = draft_errors; state.decision, state.final_answer = "ABSTAIN", "Tài liệu hiện có không đủ bằng chứng đã kiểm chứng để trả lời an toàn."
            return _prediction(sample, "ponyguard", "ABSTAIN", state.final_answer, chunks, stats, state.to_dict(), "invalid_grounding", grounding, timings)
        draft_answer = str(draft_json["answer"]); state.draft_answer = draft_answer
        verified, response = _timed_json(self.llm, "verification", f"{prompt('claim_verifier_v2.txt')}\nAnswer: {draft_answer}\nEvidence quote: {grounding['evidence_quote']}\nEvidence:\n{context(support_chunks)}", self.stage_tokens["verification"], timings); stats.append(response)
        claims = verified.get("claims", []); state.claims = claims
        decision, answer = self.final_gate(claims, draft_answer) if self.enabled["verification"] else ("ANSWER", draft_answer)
        reason = self.decision_rationale(requirement, evidence_json, decision)
        state.decision, state.decision_reason, state.final_answer, state.metrics = decision, reason, answer, {"llm_calls": sum(item.calls for item in stats)}
        return _prediction(sample, "ponyguard", decision, answer, chunks, stats, state.to_dict(), reason, grounding, timings)

    @staticmethod
    def validated_supports(evidence: dict[str, Any], chunks: list[Chunk]) -> tuple[list[dict[str, Any]], list[str]]:
        valid, rejected = [], []
        for support in evidence.get("support", []):
            if not isinstance(support, dict): rejected.append("Support không phải object."); continue
            chunk = next((item for item in chunks if item.chunk_id == support.get("chunk_id")), None)
            quote, candidate = str(support.get("evidence_quote", "")), str(support.get("candidate_answer", ""))
            if not chunk: rejected.append("Support tham chiếu chunk không tồn tại.")
            elif not normalized_contains(chunk.text, quote): rejected.append(f"Quote không nằm trong {chunk.chunk_id}.")
            elif not answer_matches_quote(candidate, quote): rejected.append(f"Candidate answer không khớp quote của {chunk.chunk_id}.")
            elif support.get("support_type") not in ("DIRECT", "SIMPLE_INFERENCE"): rejected.append(f"Support type không được phép ở {chunk.chunk_id}.")
            else: valid.append({**support, "chunk_id": chunk.chunk_id})
        numeric_values = {tuple(re.findall(r"\d+(?:[.,]\d+)*", str(item.get("candidate_answer", "")))) for item in valid if item.get("support_type") == "DIRECT"}
        if len(numeric_values) > 1: evidence["conflict_detected"] = True; rejected.append("Các direct supports có giá trị số mâu thuẫn.")
        return valid, rejected
