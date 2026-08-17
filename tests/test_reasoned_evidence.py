from ponyguard_viqa.core import Requirement
from ponyguard_viqa.core import Chunk
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import PonyGuard


HANOI_SUPPORT = {
    "chunk_id": "doc_004269_chunk_000001",
    "evidence_quote": "Năm 2009, Hà Nội có 677 trường tiểu học, 581 trường trung học cơ sở và 186 trường trung học phổ thông với 27.552 lớp học, 982.579 học sinh.",
    "candidate_answer": "982.579 học sinh",
    "support_type": "DIRECT",
    "question_entity_quote": "Hà Nội",
    "evidence_entity_quote": "Hà Nội",
    "matches_time": False,
    "matches_population": False,
    "mismatch_reasons": ["Evidence nêu năm 2009, không phải hiện tại.", "Evidence chỉ nêu tiểu học, THCS và THPT; không xác nhận tất cả loại trường."],
}


def test_broad_current_hanoi_question_abstains_with_grounded_scope_explanation():
    requirement = Requirement(entity="Hà Nội", requested_attribute="số học sinh", time_scope="CURRENT", population_scope="ALL")
    evidence = {"entity_match": True, "attribute_match": True, "valid_supports": [HANOI_SUPPORT], "reasoning_allowed": True, "inference_level": "DIRECT"}
    assert PonyGuard.decide(requirement, evidence) == "ABSTAIN"
    refusal = PonyGuard.grounded_refusal(requirement, evidence)
    assert "982.579" in refusal["text"]
    assert "2009" in refusal["text"]
    assert "tất cả" in refusal["text"]
    assert refusal["supported_facts"][0]["chunk_id"] == "doc_004269_chunk_000001"


def test_narrow_2009_school_question_can_answer_when_scope_matches():
    requirement = Requirement(entity="Hà Nội", requested_attribute="số học sinh phổ thông", time_scope="năm 2009")
    evidence = {"entity_match": True, "attribute_match": True, "valid_supports": [{**HANOI_SUPPORT, "matches_time": True, "matches_population": True}], "reasoning_allowed": True, "inference_level": "DIRECT"}
    assert PonyGuard.decide(requirement, evidence) == "ANSWER"


def test_scope_is_evaluated_from_semantic_contract_values():
    requirement = Requirement(time_scope="CURRENT", population_scope="ALL")
    assert not PonyGuard.scope_matches(requirement, [{"matches_time": False, "matches_population": True}])


def test_string_coverage_gap_is_rendered_as_one_reason_not_characters():
    requirement = Requirement(entity="Hà Nội", requested_attribute="số học sinh", time_scope="CURRENT", population_scope="ALL")
    evidence = {"valid_supports": [{**HANOI_SUPPORT, "mismatch_reasons": "Evidence chỉ nêu phổ thông."}], "coverage_gaps": "Đoạn văn chỉ nêu số liệu Hà Nội năm 2009, không phải hiện tại."}
    refusal = PonyGuard.grounded_refusal(requirement, evidence)
    assert refusal["reason_summary"].startswith("Đoạn văn")
    assert refusal["coverage_gaps"][0].startswith("Đoạn văn")
    assert all(len(gap) > 1 for gap in refusal["coverage_gaps"])


def test_refusal_uses_the_dynamic_adjudicator_reason_and_does_not_claim_corpus_absence():
    requirement = Requirement()
    evidence = {"valid_supports": [], "clarification_adjudication": {"decision": "ASK", "rationale": "The retrieved sources discuss unrelated topics and do not establish the requested concept."}}
    refusal = PonyGuard.grounded_refusal(requirement, evidence)
    assert refusal["coverage_gaps"][0].startswith("The retrieved sources")
    assert "không khẳng định toàn bộ corpus" in refusal["text"]


def test_refusal_ignores_an_ask_rationale_when_the_adjudicator_has_no_missing_slot():
    refusal = PonyGuard.grounded_refusal(Requirement(), {"valid_supports": [], "clarification_adjudication": {"decision": None, "rationale": "A false ambiguity."}})
    assert "false ambiguity" not in refusal["text"].lower()


def test_rejected_numeric_support_is_shown_as_a_component_not_a_total():
    chunk = Chunk("counts", "counts_1", "Country A has 3 groups, 12 birds, and 8 mammals.")
    evidence = {"chunk_id": chunk.chunk_id, "evidence_quote": "Country A has 8 mammals", "candidate_answer": "8", "valid_supports": []}
    observations = PonyGuard.validated_observations(evidence, [chunk])
    refusal = PonyGuard.grounded_refusal(Requirement(), {"valid_supports": [], "valid_observations": observations})
    assert "8 mammals" in refusal["text"]
    assert "nhiều số liệu riêng" in refusal["text"]


def test_refusal_shows_literal_retrieved_observations_when_no_answer_support_exists():
    chunk = Chunk("holiday", "holiday_1", "Ngày 4 tháng 7 là Quốc khánh Hoa Kỳ.")
    evidence = {"valid_supports": [], "valid_observations": PonyGuard.validated_observations({"retrieved_observations": [{"chunk_id": "holiday_1", "evidence_quote": "Ngày 4 tháng 7 là Quốc khánh Hoa Kỳ.", "limitation": "Đoạn này chỉ nêu ngày của một quốc gia, không định nghĩa khái niệm được hỏi."}]}, [chunk])}
    refusal = PonyGuard.grounded_refusal(Requirement(entity="Quốc khánh", requested_attribute="khái niệm"), evidence)
    assert "Ngày 4 tháng 7" in refusal["text"]
    assert "không định nghĩa" in refusal["text"]


def test_pipeline_runs_bounded_coverage_probes_then_returns_grounded_refusal():
    chunk = Chunk("doc_004269", "doc_004269_chunk_000001", HANOI_SUPPORT["evidence_quote"])
    class Retriever:
        last_timing = {}
        def __init__(self): self.queries = []
        def retrieve(self, query, *_): self.queries.append(query); return [chunk]
    class LLM:
        def __init__(self): self.values = iter([
            {"entity": "Hà Nội", "requested_attribute": "số học sinh", "time_scope": "CURRENT", "population_scope": "ALL", "entity_match": True, "attribute_match": True, "conflict_detected": False, "reasoning_allowed": True, "inference_level": "DIRECT", "support": [HANOI_SUPPORT]},
            {"entity_match": True, "attribute_match": True, "conflict_detected": False, "reasoning_allowed": True, "inference_level": "DIRECT", "support": [HANOI_SUPPORT]},
        ])
        def json(self, *_): return next(self.values), LLMResponse("{}", 1, 1, 1)
    retriever = Retriever()
    result = PonyGuard(retriever, LLM()).run({"sample_id": "hn", "question": "Hiện tại Hà Nội có bao nhiêu học sinh ở tất cả các trường học?", "gold_answers": [], "expected_action": "ABSTAIN"})
    assert result["prediction"]["decision"] == "ABSTAIN"
    assert "982.579" in result["prediction"]["answer"]
    assert len(retriever.queries) == 2
    assert result["trace"]["coverage"]["probe_queries"]
