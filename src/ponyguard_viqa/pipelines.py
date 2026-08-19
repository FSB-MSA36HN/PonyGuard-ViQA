from __future__ import annotations

import json
import re
from time import perf_counter
from pathlib import Path
from typing import Any, Callable

from .core import ANSWER_TYPE_SATISFIES, Action, Chunk, MISSING_REQUIREMENT_SLOTS, PonyGuardState, Requirement, answer_matches_quote, intent_slot_bindings, normalized_contains, normalize_text, resolved_question, tokenise
from .llm import LocalLLM
from .retrieval import Retriever

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
Progress = Callable[[str, str], None]


def prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{item.chunk_id}] {item.text}" for item in chunks)


def report(progress: Progress | None, stage: str, message: str) -> None:
    if progress:
        progress(stage, message)


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


def validate_grounding(value: dict[str, Any], chunks: list[Chunk], question: str = "") -> tuple[dict[str, Any], list[str]]:
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
    if question and normalized_contains(question, answer):
        return {"valid": False, "citation_chunk_ids": ids, "evidence_quote": quote}, ["Answer chỉ lặp lại một phần của câu hỏi, không bổ sung thông tin."]
    return {"valid": True, "citation_chunk_ids": ids, "evidence_quote": quote}, []


def _timed_json(llm: LocalLLM, label: str, value: str, max_tokens: int, timings: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    started = perf_counter(); parsed, response = llm.json(value, max_tokens); elapsed = (perf_counter()-started)*1000
    timings[label] = {"ms": round(elapsed, 2), "llm_calls": response.calls, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "cold_model_load_ms": round(response.model_load_ms, 2), "provider": response.provider, "model": response.model, "fallback_reason": response.fallback_reason}
    return parsed, response


def _timed_text(llm: LocalLLM, label: str, value: str, max_tokens: int, timings: dict[str, Any]) -> tuple[str, Any]:
    started = perf_counter(); response = llm.generate(value, max_tokens); elapsed = (perf_counter()-started)*1000
    timings[label] = {"ms": round(elapsed, 2), "llm_calls": response.calls, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "cold_model_load_ms": round(response.model_load_ms, 2), "provider": response.provider, "model": response.model, "fallback_reason": response.fallback_reason}
    return normalize_text(response.text).strip("'\"` "), response


def grounded_generation(llm: LocalLLM, instruction: str, question: str, chunks: list[Chunk], max_tokens: int, timings: dict[str, Any], label: str = "answer") -> tuple[dict[str, Any], list[Any], list[str]]:
    """One structured call plus one format-only retry when grounding is invalid."""
    request = f"{instruction}\nQuestion: {question}\nContext:\n{context(chunks)}"
    value, response = _timed_json(llm, label, request, max_tokens, timings)
    grounding, errors = validate_grounding(value, chunks, question)
    if grounding["valid"]:
        return value, [response], []
    repair = (f"{instruction}\nSửa JSON trước để answer, citation_chunk_ids và evidence_quote đều được grounded. "
              f"Chỉ dùng Context sau, không đổi câu hỏi.\nQuestion: {question}\nContext:\n{context(chunks)}\nPrevious JSON: {json.dumps(value, ensure_ascii=False)}")
    value, retry = _timed_json(llm, f"{label}_grounding_retry", repair, max_tokens, timings)
    grounding, errors = validate_grounding(value, chunks, question)
    value["grounding"] = grounding
    return value, [response, retry], errors


class BasicRAG:
    def __init__(self, retriever: Retriever, llm: LocalLLM, top_k: int = 5, stage_tokens: dict[str, int] | None = None): self.retriever, self.llm, self.top_k, self.stage_tokens = retriever, llm, top_k, {"answer": 128, **(stage_tokens or {})}
    def run(self, sample: dict[str, Any], progress: Progress | None = None) -> dict[str, Any]:
        report(progress, "search", "Searching sources")
        timings: dict[str, Any] = {}; chunks = self.retriever.retrieve(sample["question"], self.top_k); timings["retrieval"] = getattr(self.retriever, "last_timing", {})
        report(progress, "answer", "Writing a grounded answer")
        value, stats, errors = grounded_generation(self.llm, prompt("basic_rag_v3.txt"), sample["question"], chunks, self.stage_tokens["answer"], timings)
        grounding = value.get("grounding") or validate_grounding(value, chunks, sample["question"])[0]
        decision: Action = "ANSWER" if grounding["valid"] else "ABSTAIN"
        answer = str(value.get("answer", "")) if decision == "ANSWER" else "Tài liệu hiện có không đủ bằng chứng đã kiểm chứng để trả lời an toàn."
        report(progress, "decision", f"Decision: {decision}")
        return _prediction(sample, "basic_rag", decision, answer, chunks, stats, reason="" if grounding["valid"] else "invalid_grounding", grounding=grounding, timings=timings)


class PromptSafeRAG(BasicRAG):
    def run(self, sample: dict[str, Any], progress: Progress | None = None) -> dict[str, Any]:
        report(progress, "search", "Searching sources")
        timings: dict[str, Any] = {}; chunks = self.retriever.retrieve(sample["question"], self.top_k); timings["retrieval"] = getattr(self.retriever, "last_timing", {})
        report(progress, "answer", "Writing a grounded answer")
        parsed, stats, errors = grounded_generation(self.llm, prompt("prompt_safe_rag_v3.txt"), sample["question"], chunks, self.stage_tokens["answer"], timings)
        decision = parsed.get("decision", "ABSTAIN")
        if decision not in ("ANSWER", "ABSTAIN"): decision = "ABSTAIN"
        grounding = parsed.get("grounding") or validate_grounding(parsed, chunks, sample["question"])[0]
        if decision == "ANSWER" and not grounding["valid"]: decision = "ABSTAIN"
        answer = str(parsed.get("answer", "")) if decision == "ANSWER" else "Tài liệu hiện có không đủ bằng chứng đã kiểm chứng để trả lời an toàn."
        report(progress, "decision", f"Decision: {decision}")
        return _prediction(sample, "prompt_safe_rag", decision, answer, chunks, stats, reason="" if grounding["valid"] else "invalid_grounding", grounding=grounding, timings=timings)


class PonyGuard:
    def __init__(self, retriever: Retriever, llm: LocalLLM, top_k: int = 5, enabled: dict[str, bool] | None = None, stage_tokens: dict[str, int] | None = None, intent_first: bool = False):
        self.retriever, self.llm, self.top_k = retriever, llm, top_k
        self.enabled = {"requirement": True, "inference": True, "verification": True, **(enabled or {})}
        self.stage_tokens = {"requirement": 80, "evidence": 256, "answer": 128, "verification": 128, **(stage_tokens or {})}
        self.intent_first = intent_first

    def analyze_intent(self, question: str, timings: dict[str, Any]) -> tuple[Requirement | None, Any | None]:
        value, response = _timed_json(self.llm, "intent", f"{prompt('intent_analyzer_v2.txt')}\nQuestion: {question}", self.stage_tokens["requirement"], timings)
        if value.get("_parse_error"):
            return None, response
        value["question_clear"] = value.get("question_complete") is True
        requirement = Requirement(**{key: value.get(key) for key in Requirement.__dataclass_fields__ if key in value})
        # Slot resolution is decided from literal question spans, never from the
        # model's global completeness judgement.
        requirement.slot_bindings, span_bound = intent_slot_bindings(question, value.get("slot_bindings"), requirement.answer_type)
        requirement.missing_requirements = list(dict.fromkeys([*requirement.missing_requirements, *span_bound]))
        return self.apply_clarity_guard(question, self.enforce_requirement_contract(value, requirement), span_bound), response

    def extract_facts(self, question: str, requirement: Requirement, chunks: list[Chunk], timings: dict[str, Any], label: str = "semantic_evidence") -> tuple[dict[str, Any], Any]:
        request = f"{prompt('fact_extractor_v1.txt')}\nQuestion: {question}\nExpected entity: {requirement.entity or ''}\nExpected attribute: {requirement.requested_attribute or ''}\nExpected answer type: {requirement.answer_type}\nChunks:\n{context(chunks)}"
        return _timed_json(self.llm, label, request, self.stage_tokens["evidence"], timings)

    def verify_relations(self, question: str, requirement: Requirement, evidence: dict[str, Any], chunks: list[Chunk], timings: dict[str, Any]) -> Any | None:
        raw = self.support_items(evidence)
        if not raw:
            return None
        # A composed relation is by construction absent from every source, so a
        # verdict on it carries no information. Inference is proved arithmetically.
        candidates = [{key: item.get(key, "") for key in ("chunk_id", "evidence_quote", "candidate_answer")} for item in raw if isinstance(item, dict) and not self.is_inference(item)][:2]
        if not candidates:
            return None
        value, response = _timed_json(self.llm, "relation_verification", f"{prompt('relation_verifier_v1.txt')}\nQuestion: {question}\nExpected entity: {requirement.entity or ''}\nExpected attribute: {requirement.requested_attribute or ''}\nCandidates: {json.dumps(candidates, ensure_ascii=False)}\nChunks:\n{context(chunks)}", self.stage_tokens["requirement"], timings)
        verdicts = {str(item.get("chunk_id")): item for item in value.get("verdicts", []) if isinstance(item, dict)}
        for item in raw:
            if isinstance(item, dict) and str(item.get("chunk_id")) in verdicts:
                result = verdicts[str(item.get("chunk_id"))]
                verdict = str(result.get("verdict", "UNSTATED")).upper()
                item.update({"attribute_match": verdict == "MATCH", "relation_match": verdict == "MATCH", "premise_status": "SUPPORTED" if verdict == "MATCH" else verdict, "mismatch_dimension": result.get("mismatch_dimension", "")})
        evidence["support"] = raw
        return response

    @staticmethod
    def is_inference(support: dict[str, Any]) -> bool:
        return str(support.get("support_type", "")).upper() == "SIMPLE_INFERENCE"

    @staticmethod
    def support_items(evidence: dict[str, Any]) -> list[dict[str, Any]]:
        raw = evidence.get("support", [])
        if isinstance(raw, dict): raw = [raw]
        if not raw and all(evidence.get(key) is not None for key in ("chunk_id", "evidence_quote", "candidate_answer")):
            raw = [{key: evidence.get(key) for key in ("chunk_id", "evidence_quote", "candidate_answer", "support_type", "question_entity_quote", "evidence_entity_quote", "question_relation", "evidence_relation", "relation_match", "premise_status", "evidence_time_scope", "evidence_population_scope", "matches_time", "matches_population", "mismatch_reasons")}]
        return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

    @staticmethod
    def decide(requirement: Requirement, evidence: dict[str, Any]) -> Action:
        if requirement.missing_requirements: return "ASK"
        if not all((evidence.get("entity_match"), evidence.get("attribute_match"), evidence.get("valid_supports"))) or evidence.get("conflict_detected"): return "ABSTAIN"
        if not PonyGuard.scope_matches(requirement, evidence.get("valid_supports", [])): return "ABSTAIN"
        if not evidence.get("reasoning_allowed") or evidence.get("inference_level") == "UNSUPPORTED": return "ABSTAIN"
        return "ANSWER"

    @staticmethod
    def scope_matches(requirement: Requirement, supports: list[dict[str, Any]]) -> bool:
        if requirement.time_scope == "UNSPECIFIED" and requirement.population_scope == "UNSPECIFIED": return True
        return any((requirement.time_scope == "UNSPECIFIED" or item.get("matches_time") is True) and (requirement.population_scope == "UNSPECIFIED" or item.get("matches_population") is True) for item in supports)

    @staticmethod
    def apply_clarity_guard(question: str, requirement: Requirement, span_bound: Any = ()) -> Requirement:
        """Accept only schema slots; the model and evidence decide whether one is missing.

        A slot bound to a literal question span is evidence, not allegation, so it
        survives the guards that exist to contain an unbound malformed contract.
        """
        bound = {normalize_text(str(item)).lower() for item in span_bound} & MISSING_REQUIREMENT_SLOTS
        model_missing = [normalize_text(str(item)).lower() for item in requirement.missing_requirements]
        requirement.missing_requirements = list(dict.fromkeys(item for item in model_missing if item in MISSING_REQUIREMENT_SLOTS))
        alleged = [item for item in requirement.missing_requirements if item not in bound]
        # Multiple alleged gaps alongside an extracted entity+attribute are a
        # malformed intent contract. Defer them to the bounded clarity audit.
        if len(alleged) > 2 or (requirement.entity and requirement.requested_attribute and len(alleged) > 1):
            alleged = []
        # A contract cannot both extract a slot and claim that same slot is absent.
        if requirement.entity and normalized_contains(question, requirement.entity):
            alleged = [item for item in alleged if item != "entity"]
        if requirement.requested_attribute:
            alleged = [item for item in alleged if item != "requested_attribute"]
        # A dimension the question already fixes cannot also be a missing input,
        # whether the allegation names that slot or its answer-type sibling.
        resolved = {str(item.get("slot")) for item in requirement.slot_bindings if item.get("status") == "RESOLVED" and item.get("literal")}
        family = ANSWER_TYPE_SATISFIES.get(str(requirement.answer_type).upper(), frozenset())
        covered = resolved | family if resolved & family else resolved
        alleged = [item for item in alleged if item not in covered]
        requirement.missing_requirements = [item for item in requirement.missing_requirements if item in bound or item in alleged]
        requirement.question_clear = not requirement.missing_requirements
        requirement.ambiguity_type = "MISSING_REQUIREMENT" if requirement.missing_requirements else "NONE"
        requirement.clarification_options = PonyGuard.valid_options(requirement.clarification_options) if requirement.missing_requirements else []
        if not requirement.missing_requirements: requirement.clarification_question = ""
        return requirement

    @staticmethod
    def enforce_requirement_contract(value: dict[str, Any], requirement: Requirement) -> Requirement:
        """A model cannot declare a question clear while omitting the slots that define it."""
        entity, attribute = (normalize_text(str(value.get(field) or "")) for field in ("entity", "requested_attribute"))
        missing: list[str] = []
        # Missing contract fields are unresolved. Direct validated evidence can
        # later clear these slots; a partial model response must not imply clear.
        if not entity: missing.append("entity")
        if not attribute: missing.append("requested_attribute")
        requirement.missing_requirements = list(dict.fromkeys([*requirement.missing_requirements, *missing]))
        return requirement

    @staticmethod
    def apply_user_clarification(question: str, requirement: Requirement, completed_slots: Any = ()) -> Requirement:
        """Do not ask again for a requirement the preceding turn already supplied."""
        supplied = {normalize_text(str(slot)).lower() for slot in completed_slots} & MISSING_REQUIREMENT_SLOTS
        _, marker, reply = question.partition("\n\nThông tin làm rõ từ người dùng:")
        reply = normalize_text(reply)
        # Older persisted chats have no slot state.  A reply matching the single offered option is still unambiguous.
        if marker and reply and not supplied and len(requirement.missing_requirements) == 1:
            if any(normalized_contains(reply, option) or normalized_contains(option, reply) for option in requirement.clarification_options):
                supplied = set(requirement.missing_requirements)
        if supplied:
            requirement.missing_requirements = [slot for slot in requirement.missing_requirements if slot not in supplied]
        requirement.question_clear = not requirement.missing_requirements
        requirement.ambiguity_type = "MISSING_REQUIREMENT" if requirement.missing_requirements else "NONE"
        if not requirement.missing_requirements:
            requirement.clarification_question, requirement.clarification_options = "", []
        return requirement

    @staticmethod
    def resolve_missing_with_evidence(requirement: Requirement, evidence: dict[str, Any]) -> Requirement:
        """A direct, unique, validated fact defeats a spurious missing-slot label."""
        if requirement.missing_requirements and evidence.get("valid_supports") and evidence.get("entity_match") and evidence.get("attribute_match") and not evidence.get("conflict_detected"):
            requirement.missing_requirements = []
            requirement.question_clear, requirement.ambiguity_type, requirement.clarification_question = True, "NONE", ""
        return requirement

    @staticmethod
    def make_ask_safe(requirement: Requirement) -> Requirement:
        """A semantic ASK must not degrade to ABSTAIN because an optional slot was malformed."""
        if not requirement.missing_requirements:
            requirement.missing_requirements = ["reference"]
            requirement.question_clear, requirement.ambiguity_type = False, "MISSING_REQUIREMENT"
        if not requirement.clarification_question:
            requirement.clarification_question = "Bạn có thể làm rõ đối tượng hoặc thông tin bạn muốn biết không?"
        return requirement

    def refine_clarification(self, question: str, requirement: Requirement, rationale: str, timings: dict[str, Any]) -> tuple[str, Any | None]:
        """Use plain-text generation so malformed JSON cannot make an ASK vague."""
        if not hasattr(self.llm, "generate"):
            return "", None
        request = (f"{prompt('clarification_writer_v2.txt')}\nOriginal question: {question}\n"
                   f"Missing slots: {', '.join(requirement.missing_requirements) or 'unknown'}\n"
                   f"Current entity: {requirement.entity or 'unknown'}\n"
                   f"Current attribute: {requirement.requested_attribute or 'unknown'}\n"
                   f"Clarification options: {json.dumps(requirement.clarification_options, ensure_ascii=False)}\n"
                   f"Adjudicator rationale: {rationale or 'unknown'}")
        candidate, response = _timed_text(self.llm, "clarification_writer", request, self.stage_tokens["requirement"], timings)
        if not candidate or normalize_text(question).casefold() in candidate.casefold():
            return "", response
        anchors = [value for value in (requirement.entity, requirement.requested_attribute, *requirement.clarification_options) if normalize_text(str(value or ""))]
        if anchors and not any(normalized_contains(candidate, str(anchor)) for anchor in anchors):
            return "", response
        return candidate, response

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
    def text_items(value: Any) -> list[str]:
        """LLMs sometimes return one string where the schema requests a list."""
        values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
        return [normalize_text(str(item)) for item in values if normalize_text(str(item))]

    @staticmethod
    def decision_rationale(requirement: Requirement, evidence: dict[str, Any], decision: Action) -> str:
        if decision == "ASK": return f"Thiếu thông tin bắt buộc: {', '.join(requirement.missing_requirements)}."
        if decision == "ANSWER": return str(evidence.get("decision_rationale") or "Evidence đáp ứng entity, thuộc tính và mức suy luận cho phép.")
        if evidence.get("conflict_detected"): return "Các chunks có evidence mâu thuẫn."
        gaps = PonyGuard.text_items(evidence.get("coverage_gaps"))
        if gaps: return str(gaps[0])
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
        generated = requirement.clarification_question.strip()
        if generated and (not question or normalize_text(question).lower() not in normalize_text(generated).lower()): return generated
        if requirement.clarification_options:
            subject = f" về {requirement.entity}" if requirement.entity else ""
            return f"Bạn muốn làm rõ theo hướng nào{subject}: {' hay '.join(requirement.clarification_options)}?"
        if requirement.ambiguity_type == "AMBIGUOUS_ATTRIBUTE":
            entity = requirement.entity or "đối tượng này"
            return f"Bạn muốn biết số lượng hoặc thuộc tính nào về {entity}?"
        if "entity" in requirement.missing_requirements:
            return f"Bạn đang hỏi {requirement.requested_attribute or 'thông tin này'} của ai hoặc đối tượng nào?"
        if "requested_attribute" in requirement.missing_requirements:
            return f"Bạn muốn biết thuộc tính hoặc thông tin nào về {requirement.entity or 'đối tượng đó'}?"
        if "country" in requirement.missing_requirements:
            return f"Bạn muốn biết {requirement.entity or 'thông tin này'} của quốc gia nào?"
        if "location" in requirement.missing_requirements:
            return f"Bạn muốn biết {requirement.entity or 'thông tin này'} ở địa điểm nào?"
        if "time" in requirement.missing_requirements:
            return f"Bạn muốn biết {requirement.entity or 'thông tin này'} vào thời điểm nào?"
        if "scope" in requirement.missing_requirements:
            return f"Bạn muốn hỏi {requirement.entity or 'thông tin này'} trong phạm vi nào?"
        if "reference" in requirement.missing_requirements or "target" in requirement.missing_requirements:
            return f"Bạn đang nói tới người, vật hoặc đối tượng nào khi hỏi về {requirement.requested_attribute or 'thông tin này'}?"
        return "Bạn có thể làm rõ chính xác thông tin cần hỏi không?"

    @staticmethod
    def coverage_probe_queries(requirement: Requirement, question: str) -> list[str]:
        base = " ".join(part for part in (requirement.entity, requirement.requested_attribute) if part) or question
        return [base] if requirement.time_scope != "UNSPECIFIED" or requirement.population_scope != "UNSPECIFIED" else []

    @staticmethod
    def grounded_refusal(requirement: Requirement, evidence: dict[str, Any]) -> dict[str, Any]:
        supports = evidence.get("valid_supports", [])
        observations = evidence.get("valid_observations", [])
        facts = [{"chunk_id": item["chunk_id"], "text": item["evidence_quote"], "limitation": item.get("limitation", "")} for item in (supports or observations)[:2]]
        gaps = PonyGuard.text_items(evidence.get("coverage_gaps"))
        if evidence.get("_parse_error"):
            gaps.insert(0, "Không thể kiểm chứng semantic evidence vì model trả output không hợp lệ.")
        adjudication = evidence.get("clarification_adjudication", {})
        audit_reason = normalize_text(str(adjudication.get("rationale", ""))) if adjudication.get("decision") == "ASK" else ""
        if audit_reason:
            gaps.insert(0, audit_reason)
        for item in supports:
            for reason in PonyGuard.text_items(item.get("mismatch_reasons")):
                if reason not in gaps: gaps.append(str(reason))
        if requirement.time_scope != "UNSPECIFIED" and not any(item.get("matches_time") is True for item in supports):
            gaps.append("Thời gian trong evidence không khớp thời gian được hỏi.")
        if requirement.population_scope != "UNSPECIFIED" and not any(item.get("matches_population") is True for item in supports):
            gaps.append("Evidence không xác nhận toàn bộ phạm vi/nhóm đối tượng được hỏi.")
        gaps = list(dict.fromkeys(gaps)) or ["Các nguồn đã truy xuất không chứa evidence đã kiểm chứng cho yêu cầu này."]
        partial = supports[0].get("candidate_answer") if supports else ""
        rephrase = f"Nếu bạn muốn phạm vi hẹp hơn mà tài liệu nêu, có thể hỏi về {partial}." if partial else "Bạn có thể nêu phạm vi hoặc mốc thời gian hẹp hơn nếu phù hợp."
        lines = ["Tôi chưa thể trả lời từ các nguồn đã truy xuất."]
        if facts:
            lines.append("Nguồn đã tìm thấy: " + " ".join(f"“{item['text']}” [{item['chunk_id']}]" for item in facts))
            limitations = [str(item["limitation"]) for item in facts if item.get("limitation")]
            if limitations:
                gaps = limitations + gaps
            elif gaps == ["Các nguồn đã truy xuất không chứa evidence đã kiểm chứng cho yêu cầu này."]:
                target = " ".join(part for part in (requirement.requested_attribute, requirement.entity) if part) or "yêu cầu được hỏi"
                gaps = [f"Các đoạn trên không có trích dẫn trực tiếp xác lập {target}."]
        lines.append("Lý do: " + " ".join(gaps))
        lines.append("Điều này cho thấy evidence đã retrieve chưa đủ; không khẳng định toàn bộ corpus không có thông tin.")
        lines.append(rephrase)
        return {"reason_summary": gaps[0], "supported_facts": facts, "coverage_gaps": gaps, "safe_rephrase": rephrase, "text": "\n\n".join(lines)}

    @staticmethod
    def semantic_contract_is_empty(evidence: dict[str, Any]) -> bool:
        """Detect a syntactically valid but decision-incomplete model response."""
        if evidence.get("_parse_error") or evidence.get("support") or evidence.get("missing_requirements"):
            return False
        return not (
            normalize_text(str(evidence.get("entity", "")))
            and normalize_text(str(evidence.get("requested_attribute", "")))
            and isinstance(evidence.get("entity_match"), bool)
            and isinstance(evidence.get("attribute_match"), bool)
            and evidence.get("inference_level") in ("DIRECT", "SIMPLE_INFERENCE", "UNSUPPORTED")
            and isinstance(evidence.get("reasoning_allowed"), bool)
        )

    def recover_direct_evidence(self, question: str, chunks: list[Chunk], timings: dict[str, Any]) -> tuple[dict[str, Any] | None, list[Any], list[str]]:
        value, stats, errors = grounded_generation(self.llm, prompt("evidence_recovery_v1.txt"), question, chunks, self.stage_tokens["answer"], timings, "evidence_recovery")
        grounding = value.get("grounding") or validate_grounding(value, chunks)[0]
        source = next((chunk.text for chunk in chunks if chunk.chunk_id in grounding["citation_chunk_ids"]), "")
        binding = self.entity_binding_is_literal(question, grounding["evidence_quote"], value, source) if grounding["valid"] else False
        if not grounding["valid"] or not binding:
            return None, stats, errors + ([] if binding else ["Evidence recovery không xác minh được entity binding."])
        support = {
            "chunk_id": grounding["citation_chunk_ids"][0], "evidence_quote": grounding["evidence_quote"],
            "candidate_answer": str(value.get("answer", "")), "support_type": "DIRECT",
            "question_entity_quote": value.get("question_entity_quote", ""), "evidence_entity_quote": value.get("evidence_entity_quote", ""),
            "question_relation": value.get("question_relation", ""), "evidence_relation": value.get("evidence_relation", ""),
            "relation_match": value.get("relation_match") is True, "premise_status": value.get("premise_status", "UNSTATED"),
        }
        if not support["relation_match"] or support["premise_status"] != "SUPPORTED":
            return None, stats, errors + ["Evidence recovery không xác minh được quan hệ được hỏi."]
        return {"draft": value, "grounding": grounding, "support": support}, stats, errors

    def run(self, sample: dict[str, Any], progress: Progress | None = None) -> dict[str, Any]:
        question = resolved_question(sample["question"])
        resolved_follow_up = question != sample["question"]
        sample = {**sample, "question": question}
        state = PonyGuardState(sample.get("sample_id"), question); stats = []; timings: dict[str, Any] = {}
        intent_requirement = None
        if self.intent_first:
            report(progress, "understand", "Understanding the question")
            intent_requirement, response = self.analyze_intent(question, timings); stats.append(response)
            if intent_requirement and intent_requirement.missing_requirements:
                state.requirements = intent_requirement.__dict__
                state.decision = "ASK"; state.decision_reason = self.decision_rationale(intent_requirement, {}, "ASK")
                candidate, writer = self.refine_clarification(question, intent_requirement, "", timings)
                if writer is not None: stats.append(writer)
                if candidate: intent_requirement.clarification_question = candidate
                answer = self.clarification_question(intent_requirement, question)
                state.requirements, state.final_answer, state.metrics = intent_requirement.__dict__, answer, {"llm_calls": sum(item.calls for item in stats)}
                return _prediction(sample, "ponyguard", "ASK", answer, [], stats, state.to_dict(), state.decision_reason, timings=timings)
        report(progress, "search", "Searching sources")
        chunks = self.retriever.retrieve(sample["question"], self.top_k); timings["retrieval"] = getattr(self.retriever, "last_timing", {}); state.retrieval = {"chunks": [c.to_dict() for c in chunks]}
        report(progress, "understand", "Understanding the question and evidence")
        if intent_requirement:
            evidence_json, response = self.extract_facts(sample["question"], intent_requirement, chunks, timings)
        else:
            evidence_json, response = _timed_json(self.llm, "semantic_evidence", f"{prompt('semantic_evidence_v5.txt')}\nQuestion: {sample['question']}\nChunks:\n{context(chunks)}", self.stage_tokens["evidence"], timings)
        stats.append(response)
        requirement_json = evidence_json
        semantic_incomplete = self.semantic_contract_is_empty(evidence_json)
        if not intent_requirement and (evidence_json.get("_parse_error") or semantic_incomplete):
            report(progress, "understand", "Recovering question requirements")
            requirement_json, response = _timed_json(self.llm, "requirement_recovery", f"{prompt('requirement_recovery_v1.txt')}\nQuestion: {sample['question']}", self.stage_tokens["requirement"], timings); stats.append(response)
            evidence_json["requirement_recovery"] = {"applied": not requirement_json.get("_parse_error"), "parse_error": bool(requirement_json.get("_parse_error")), "semantic_incomplete": semantic_incomplete}
        recovery_failed = bool(requirement_json.get("_parse_error"))
        requirement = intent_requirement or Requirement(**{key: requirement_json.get(key) for key in Requirement.__dataclass_fields__ if key in requirement_json})
        clarified_slots = sample.get("clarification_for", [])
        if intent_requirement:
            requirement = intent_requirement
        elif recovery_failed:
            requirement = Requirement(question_clear=True)
        else:
            requirement = self.apply_user_clarification(sample["question"], self.apply_clarity_guard(sample["question"], self.enforce_requirement_contract(requirement_json, requirement)), clarified_slots)
        state.requirements = requirement.__dict__
        report(progress, "evidence", "Checking evidence")
        if self.intent_first:
            relation_response = self.verify_relations(sample["question"], requirement, evidence_json, chunks, timings)
            if relation_response is not None: stats.append(relation_response)
        supports, rejected = self.validated_supports(evidence_json, chunks, sample["question"], strict_relation=self.intent_first, expected_entity=requirement.entity)
        evidence_json["valid_supports"] = supports
        evidence_json["support_rejections"] = rejected
        evidence_json["valid_observations"] = self.validated_observations(evidence_json, chunks)
        evidence_json["answerable_from_evidence"] = bool(supports)
        evidence_json["evidence_sufficient"] = bool(supports)
        # A relation-bound DIRECT fact is authoritative. A prose rationale from
        # the same model must not turn verified evidence into false abstention.
        if supports:
            level = "SIMPLE_INFERENCE" if any(item.get("support_type") == "SIMPLE_INFERENCE" for item in supports) else "DIRECT"
            evidence_json.update({"entity_match": True, "attribute_match": True, "inference_level": level, "reasoning_allowed": True})
        if supports and semantic_incomplete:
            evidence_json.update({"entity_match": True, "attribute_match": True, "inference_level": "DIRECT", "reasoning_allowed": True, "answerable_from_evidence": True, "evidence_sufficient": True})
        if self.intent_first and not requirement.missing_requirements and not supports and not resolved_follow_up:
            query = " ".join(part for part in (requirement.entity, requirement.requested_attribute) if part)
            retry_chunks = self.retriever.retrieve(query or sample["question"], self.top_k)
            seen = {chunk.chunk_id for chunk in chunks}
            chunks.extend(chunk for chunk in retry_chunks if chunk.chunk_id not in seen)
            recovered_json, response = self.extract_facts(sample["question"], requirement, chunks, timings, "fact_recovery"); stats.append(response)
            relation_response = self.verify_relations(sample["question"], requirement, recovered_json, chunks, timings)
            if relation_response is not None: stats.append(relation_response)
            recovered_supports, recovery_rejections = self.validated_supports(recovered_json, chunks, sample["question"], strict_relation=True, expected_entity=requirement.entity)
            evidence_json["fact_recovery"] = {"support": recovered_json.get("support"), "rejections": recovery_rejections}
            if recovered_supports:
                supports = recovered_supports
                level = "SIMPLE_INFERENCE" if any(item.get("support_type") == "SIMPLE_INFERENCE" for item in supports) else "DIRECT"
                evidence_json.update({"valid_supports": supports, "entity_match": True, "attribute_match": True, "inference_level": level, "reasoning_allowed": True, "answerable_from_evidence": True, "evidence_sufficient": True})
        if not requirement.missing_requirements and not supports and not resolved_follow_up and (self.intent_first or not evidence_json.get("_parse_error")):
            report(progress, "understand", "Deciding whether clarification is needed")
            audit_prompt = f"{prompt('clarity_auditor_v1.txt')}\nQuestion: {sample['question']}\nExtracted entity: {requirement.entity or ''}\nExtracted attribute: {requirement.requested_attribute or ''}" if self.intent_first else f"{prompt('clarification_adjudicator_v3.txt')}\nQuestion: {sample['question']}\nChunks:\n{context(chunks)}"
            audit_json, response = _timed_json(self.llm, "clarification_adjudication", audit_prompt, self.stage_tokens["requirement"], timings); stats.append(response)
            audit_requirement = self.apply_user_clarification(sample["question"], self.apply_clarity_guard(sample["question"], Requirement(**{key: audit_json.get(key) for key in Requirement.__dataclass_fields__ if key in audit_json})), clarified_slots)
            audit_accepted = audit_json.get("decision") == "ASK" and bool(audit_requirement.missing_requirements)
            if audit_accepted:
                audit_requirement = self.make_ask_safe(audit_requirement)
                requirement = audit_requirement
            evidence_json["clarification_adjudication"] = {"decision": "ASK" if audit_accepted else None, "rationale": audit_json.get("rationale", "") if audit_accepted else "", "missing_requirements": audit_requirement.missing_requirements if audit_accepted else [], "clarification_question": audit_requirement.clarification_question if audit_accepted else "", "clarification_options": audit_requirement.clarification_options if audit_accepted else []}
        if not self.intent_first and chunks and not supports and not requirement.missing_requirements:
            report(progress, "evidence", "Recovering direct evidence")
            recovered, recovery_stats, recovery_errors = self.recover_direct_evidence(sample["question"], chunks, timings); stats.extend(recovery_stats)
            evidence_json["evidence_recovery"] = {"applied": bool(recovered), "errors": recovery_errors}
            if recovered:
                supports = [recovered["support"]]
                evidence_json.update({"entity_match": True, "attribute_match": True, "inference_level": "DIRECT", "reasoning_allowed": True, "valid_supports": supports, "answerable_from_evidence": True, "evidence_sufficient": True, "_recovery_draft": recovered["draft"], "_recovery_grounding": recovered["grounding"]})
        if supports and not self.scope_matches(requirement, supports):
            probes = self.coverage_probe_queries(requirement, sample["question"])
            report(progress, "search", "Checking source coverage")
            probe_chunks = [chunk for query in probes for chunk in self.retriever.retrieve(query, min(2, self.top_k))]
            seen = {chunk.chunk_id for chunk in chunks}
            for chunk in probe_chunks:
                if chunk.chunk_id not in seen:
                    chunks.append(chunk); seen.add(chunk.chunk_id)
            state.coverage = {"probe_queries": probes, "probe_chunk_ids": [chunk.chunk_id for chunk in probe_chunks]}
            state.retrieval = {"chunks": [chunk.to_dict() for chunk in chunks]}
            evidence_json, response = _timed_json(self.llm, "scope_reaudit", f"{prompt('semantic_evidence_v5.txt')}\nQuestion: {sample['question']}\nChunks:\n{context(chunks)}", self.stage_tokens["evidence"], timings); stats.append(response)
            supports, rejected = self.validated_supports(evidence_json, chunks, sample["question"], strict_relation=self.intent_first, expected_entity=requirement.entity)
            evidence_json["valid_supports"], evidence_json["support_rejections"], evidence_json["valid_observations"], evidence_json["answerable_from_evidence"], evidence_json["evidence_sufficient"] = supports, rejected, self.validated_observations(evidence_json, chunks), bool(supports), bool(supports)
        requirement = self.resolve_missing_with_evidence(requirement, evidence_json)
        state.requirements = requirement.__dict__
        state.evidence = evidence_json; state.reasoning = {"level": evidence_json.get("inference_level"), "allowed": evidence_json.get("reasoning_allowed")}
        decision = self.decide(requirement, evidence_json) if self.enabled["requirement"] and self.enabled["inference"] else ("ANSWER" if evidence_json.get("evidence_sufficient") else "ABSTAIN")
        if decision == "ASK":
            report(progress, "understand", "Writing a focused clarification")
            candidate, response = self.refine_clarification(sample["question"], requirement, str(evidence_json.get("clarification_adjudication", {}).get("rationale", "")), timings)
            if response is not None:
                stats.append(response)
                evidence_json["clarification_writer"] = {"applied": bool(candidate), "question": candidate}
            if candidate:
                requirement.clarification_question = candidate
            state.requirements = requirement.__dict__
        reason = self.decision_rationale(requirement, evidence_json, decision)
        state.decision, state.decision_reason = decision, reason
        if decision != "ANSWER":
            refusal = self.grounded_refusal(requirement, evidence_json) if decision == "ABSTAIN" else {}
            state.coverage = {**state.coverage, **refusal}
            answer = self.clarification_question(requirement, sample["question"]) if decision == "ASK" else refusal["text"]
            state.final_answer = answer; state.metrics = {"llm_calls": sum(item.calls for item in stats)}
            report(progress, "decision", f"Decision: {decision}")
            return _prediction(sample, "ponyguard", decision, answer, chunks, stats, state.to_dict(), reason, timings=timings)
        support_chunks = [chunk for chunk in chunks if chunk.chunk_id in {item["chunk_id"] for item in supports}]
        if len(supports) == 1 and supports[0].get("support_type") == "DIRECT":
            canonical = supports[0]
            grounding = {"valid": True, "citation_chunk_ids": [canonical["chunk_id"]], "evidence_quote": str(canonical["evidence_quote"])}
            answer = str(canonical["candidate_answer"])
            state.draft_answer, state.claims, state.final_answer = answer, [{"text": answer, "label": "SUPPORTED", "evidence_chunk_ids": grounding["citation_chunk_ids"]}], answer
            state.metrics = {"llm_calls": sum(item.calls for item in stats)}
            report(progress, "decision", "Decision: ANSWER")
            return _prediction(sample, "ponyguard", "ANSWER", answer, chunks, stats, state.to_dict(), reason, grounding, timings)
        if len(supports) == 1 and supports[0].get("support_type") == "SIMPLE_INFERENCE":
            proof = supports[0]["inference_proof"]
            answer = normalize_text(f"{proof['result']} {proof.get('unit', '')}")
            ids = list(dict.fromkeys(str(item["chunk_id"]) for item in proof["operands"]))
            grounding = {"valid": True, "citation_chunk_ids": ids, "evidence_quote": str(proof["operands"][0]["evidence_quote"]), "inference_proof": proof}
            state.draft_answer, state.claims, state.final_answer = answer, [{"text": answer, "label": "INFERRED_SUPPORTED", "evidence_chunk_ids": ids}], answer
            state.metrics = {"llm_calls": sum(item.calls for item in stats)}
            report(progress, "decision", "Decision: ANSWER")
            return _prediction(sample, "ponyguard", "ANSWER", answer, chunks, stats, state.to_dict(), reason, grounding, timings)
        report(progress, "answer", "Writing from verified evidence")
        if evidence_json.get("_recovery_draft"):
            draft_json, draft_errors, grounding = evidence_json["_recovery_draft"], [], evidence_json["_recovery_grounding"]
        else:
            draft_json, draft_stats, draft_errors = grounded_generation(self.llm, prompt("basic_rag_v3.txt"), sample["question"], support_chunks, self.stage_tokens["answer"], timings); stats.extend(draft_stats)
            grounding = draft_json.get("grounding") or validate_grounding(draft_json, support_chunks, sample["question"])[0]
            # The extractor already produced a relation-bound literal answer.
            # Prefer it over an otherwise unsafe paraphrase from answer generation.
            if not grounding["valid"] and supports:
                canonical = supports[0]
                canonical_quote = str(canonical.get("evidence_quote", ""))
                canonical_answer = str(canonical.get("candidate_answer", ""))
                if answer_matches_quote(canonical_answer, canonical_quote):
                    draft_json = {"answer": canonical_answer}
                    grounding = {"valid": True, "citation_chunk_ids": [canonical["chunk_id"]], "evidence_quote": canonical_quote}
        if not grounding["valid"]:
            state.evidence["draft_rejections"] = draft_errors; state.decision, state.final_answer = "ABSTAIN", "Tài liệu hiện có không đủ bằng chứng đã kiểm chứng để trả lời an toàn."
            return _prediction(sample, "ponyguard", "ABSTAIN", state.final_answer, chunks, stats, state.to_dict(), "invalid_grounding", grounding, timings)
        draft_answer = str(draft_json["answer"]); state.draft_answer = draft_answer
        report(progress, "verify", "Verifying the answer")
        verified, response = _timed_json(self.llm, "verification", f"{prompt('claim_verifier_v2.txt')}\nAnswer: {draft_answer}\nEvidence quote: {grounding['evidence_quote']}\nEvidence:\n{context(support_chunks)}", self.stage_tokens["verification"], timings); stats.append(response)
        claims = verified.get("claims", []); state.claims = claims
        decision, answer = self.final_gate(claims, draft_answer) if self.enabled["verification"] else ("ANSWER", draft_answer)
        if decision == "ABSTAIN":
            refusal = self.grounded_refusal(requirement, evidence_json)
            state.coverage = {**state.coverage, **refusal}
            answer = refusal["text"]
        reason = self.decision_rationale(requirement, evidence_json, decision)
        state.decision, state.decision_reason, state.final_answer, state.metrics = decision, reason, answer, {"llm_calls": sum(item.calls for item in stats)}
        report(progress, "decision", f"Decision: {decision}")
        return _prediction(sample, "ponyguard", decision, answer, chunks, stats, state.to_dict(), reason, grounding, timings)

    @staticmethod
    def validated_supports(evidence: dict[str, Any], chunks: list[Chunk], question: str = "", strict_relation: bool = False, expected_entity: str = "") -> tuple[list[dict[str, Any]], list[str]]:
        valid, rejected = [], []
        raw_supports = PonyGuard.support_items(evidence)
        for support in raw_supports:
            if not isinstance(support, dict): rejected.append("Support không phải object."); continue
            chunk = next((item for item in chunks if item.chunk_id == support.get("chunk_id")), None)
            quote, candidate = str(support.get("evidence_quote", "")), str(support.get("candidate_answer", ""))
            status = str(support.get("premise_status") or "SUPPORTED").upper()
            relation_match = support.get("relation_match") if isinstance(support.get("relation_match"), bool) else True
            if chunk and strict_relation and status == "SUPPORTED" and relation_match is True and not normalized_contains(chunk.text, quote) and normalized_contains(chunk.text, candidate):
                quote = PonyGuard.source_excerpt_around(chunk.text, candidate)
                support["evidence_quote"] = quote
            # A derived relation is stated by no source, so the relation verdict is
            # uninformative for it. Its proof is validated arithmetically instead.
            inference = PonyGuard.is_inference(support)
            if not chunk: rejected.append("Support tham chiếu chunk không tồn tại.")
            elif not normalized_contains(chunk.text, quote): rejected.append(f"Quote không nằm trong {chunk.chunk_id}.")
            elif not inference and strict_relation and ("relation_match" not in support or "attribute_match" not in support or "premise_status" not in support): rejected.append(f"Support trong {chunk.chunk_id} thiếu xác minh quan hệ.")
            elif not inference and status != "SUPPORTED": rejected.append(f"Premise của câu hỏi {status.lower()} trong {chunk.chunk_id}.")
            elif not inference and strict_relation and support.get("attribute_match") is not True: rejected.append(f"Thuộc tính trong {chunk.chunk_id} không khớp yêu cầu được hỏi.")
            elif not inference and relation_match is not True: rejected.append(f"Quan hệ trong {chunk.chunk_id} không khớp yêu cầu được hỏi.")
            elif inference and not PonyGuard.inference_proof_is_valid(support, chunks, question): rejected.append(f"Inference proof không hợp lệ ở {chunk.chunk_id}.")
            elif not inference and not answer_matches_quote(candidate, quote): rejected.append(f"Candidate answer không khớp quote của {chunk.chunk_id}.")
            elif not inference and question and not PonyGuard.entity_binding_is_literal(question, quote, support, chunk.text, expected_entity): rejected.append(f"Entity trong {chunk.chunk_id} không khớp thực thể được hỏi.")
            elif str(support.get("support_type", "")).upper() not in ("DIRECT", "SIMPLE_INFERENCE"): rejected.append(f"Support type không được phép ở {chunk.chunk_id}.")
            else: valid.append({**support, "chunk_id": chunk.chunk_id, "support_type": str(support["support_type"]).upper()})
        numeric_values = {tuple(re.findall(r"\d+(?:[.,]\d+)*", str(item.get("candidate_answer", "")))) for item in valid if item.get("support_type") == "DIRECT"}
        if len(numeric_values) > 1: evidence["conflict_detected"] = True; rejected.append("Các direct supports có giá trị số mâu thuẫn.")
        return valid, rejected

    @staticmethod
    def inference_proof_is_valid(support: dict[str, Any], chunks: list[Chunk], question: str = "") -> bool:
        """Prove a derived answer from stated operands instead of trusting a relation verdict.

        Every operand must quote a real chunk literally, state its own value, and
        be about something the question names; the result is then recomputed here.
        An unsupported join fails on the operands, not on a model's opinion.
        """
        proof = support.get("inference_proof")
        if not isinstance(proof, dict) or proof.get("operation") not in {"sum", "difference", "ratio"}:
            return False
        operands = proof.get("operands")
        if not isinstance(operands, list) or len(operands) != 2:
            return False
        values: list[float] = []
        for operand in operands:
            if not isinstance(operand, dict): return False
            chunk = next((item for item in chunks if item.chunk_id == operand.get("chunk_id")), None)
            quote, value = str(operand.get("evidence_quote", "")), str(operand.get("value", ""))
            if not chunk or not normalized_contains(chunk.text, quote) or not answer_matches_quote(value, quote): return False
            if question and not PonyGuard.entity_binding_is_literal(question, quote, support, chunk.text): return False
            parsed = PonyGuard.numeric_value(value)
            if parsed is None: return False
            values.append(parsed)
        expected = values[0] + values[1] if proof["operation"] == "sum" else values[0] - values[1] if proof["operation"] == "difference" else values[0] / values[1] if values[1] else None
        actual = PonyGuard.numeric_value(str(proof.get("result", support.get("candidate_answer", ""))))
        return expected is not None and actual is not None and abs(expected - actual) <= max(.001, abs(expected) * .001)

    @staticmethod
    def numeric_value(value: str) -> float | None:
        match = re.search(r"\d+(?:[.,]\d+)*", normalize_text(value))
        if not match: return None
        number = match.group()
        if "," in number: number = number.replace(".", "").replace(",", ".")
        elif number.count(".") == 1 and len(number.rsplit(".", 1)[1]) == 3: number = number.replace(".", "")
        else: number = number.replace(",", "")
        try: return float(number)
        except ValueError: return None

    @staticmethod
    def entity_binding_is_literal(question: str, evidence_quote: str, support: dict[str, Any], source_text: str = "", expected_entity: str = "") -> bool:
        question_entity = normalize_text(str(support.get("question_entity_quote", "")))
        evidence_entity = normalize_text(str(support.get("evidence_entity_quote", "")))
        expected_entity = normalize_text(str(expected_entity or ""))
        if expected_entity:
            exact = normalized_contains(question, expected_entity) and normalized_contains(source_text or evidence_quote, expected_entity)
            literal_alias = evidence_entity and normalized_contains(question, evidence_entity) and normalized_contains(source_text or evidence_quote, evidence_entity) and normalized_contains(expected_entity, evidence_entity)
            if not (exact or literal_alias):
                return False
        if question_entity and evidence_entity and normalized_contains(question, question_entity) and normalized_contains(evidence_quote, evidence_entity) and question_entity.casefold() == evidence_entity.casefold():
            return True
        if question_entity and evidence_entity:
            shorter, longer = sorted((question_entity, evidence_entity), key=len)
            if "Thông tin làm rõ từ người dùng:" in question and len(tokenise(shorter)) >= 2 and normalized_contains(longer, shorter):
                return True
        # Relation strictness is checked separately.  A verifier can still emit
        # unusable entity spans, so bind the literal question and quote to source.
        question_terms = {term for term in tokenise(question) if len(term) > 2}
        source_terms = set(tokenise(source_text or evidence_quote))
        quote_terms = set(tokenise(evidence_quote))
        return len(question_terms & source_terms) >= 2 and bool(question_terms & quote_terms)

    @staticmethod
    def validated_observations(evidence: dict[str, Any], chunks: list[Chunk]) -> list[dict[str, str]]:
        """Keep only literal source excerpts for a transparent refusal."""
        valid: list[dict[str, str]] = []
        raw_supports = PonyGuard.support_items(evidence)
        for support in raw_supports:
            if not isinstance(support, dict):
                continue
            chunk = next((item for item in chunks if item.chunk_id == support.get("chunk_id")), None)
            candidate = normalize_text(str(support.get("candidate_answer", "")))
            if not chunk or not candidate or not normalized_contains(chunk.text, candidate):
                continue
            numbers = re.findall(r"\d+(?:[.,]\d+)*", chunk.text)
            limitation = "Đoạn này có nhiều số liệu riêng nhưng không nêu một tổng số duy nhất." if len(set(numbers)) > 1 else "Đoạn này nêu một số liệu liên quan nhưng chưa xác lập đầy đủ yêu cầu."
            valid.append({"chunk_id": chunk.chunk_id, "evidence_quote": PonyGuard.source_excerpt_around(chunk.text, candidate), "limitation": limitation})
            if len(valid) == 2:
                return valid
        for observation in evidence.get("retrieved_observations", []):
            if not isinstance(observation, dict):
                continue
            chunk = next((item for item in chunks if item.chunk_id == observation.get("chunk_id")), None)
            quote = normalize_text(str(observation.get("evidence_quote", "")))
            if chunk and quote and normalized_contains(chunk.text, quote):
                valid.append({"chunk_id": chunk.chunk_id, "evidence_quote": quote, "limitation": normalize_text(str(observation.get("limitation", "")))})
            if len(valid) == 2:
                break
        return valid

    @staticmethod
    def source_excerpt(text: str, limit: int = 280) -> str:
        """A literal, bounded fallback excerpt when the model omits observations."""
        text = normalize_text(text)
        if len(text) <= limit:
            return text
        boundary = max(text.rfind(mark, 0, limit) for mark in ".!?;")
        return text[:boundary + 1] if boundary > limit // 2 else text[:limit].rsplit(" ", 1)[0]

    @staticmethod
    def source_excerpt_around(text: str, needle: str, limit: int = 280) -> str:
        text, needle = normalize_text(text), normalize_text(needle)
        index = text.casefold().find(needle.casefold())
        if index < 0:
            return PonyGuard.source_excerpt(text, limit)
        start, end = max(0, index - limit // 2), min(len(text), index + len(needle) + limit // 2)
        while start and not text[start - 1].isspace(): start -= 1
        while end < len(text) and not text[end].isspace(): end += 1
        return text[start:end]
