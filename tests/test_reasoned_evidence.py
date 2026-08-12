from ponyguard_viqa.core import Requirement, question_scope
from ponyguard_viqa.core import Chunk
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import PonyGuard


HANOI_SUPPORT = {
    "chunk_id": "doc_004269_chunk_000001",
    "evidence_quote": "Năm 2009, Hà Nội có 677 trường tiểu học, 581 trường trung học cơ sở và 186 trường trung học phổ thông với 27.552 lớp học, 982.579 học sinh.",
    "candidate_answer": "982.579 học sinh",
    "support_type": "DIRECT",
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


def test_scope_detector_marks_current_and_all_without_making_question_ambiguous():
    assert question_scope("Hiện tại Hà Nội có bao nhiêu học sinh ở tất cả các trường?") == ("CURRENT", "ALL", ["CURRENT", "all requested categories"])


def test_string_coverage_gap_is_rendered_as_one_reason_not_characters():
    requirement = Requirement(entity="Hà Nội", requested_attribute="số học sinh", time_scope="CURRENT", population_scope="ALL")
    evidence = {"valid_supports": [{**HANOI_SUPPORT, "mismatch_reasons": "Evidence chỉ nêu phổ thông."}], "coverage_gaps": "Đoạn văn chỉ nêu số liệu Hà Nội năm 2009, không phải hiện tại."}
    refusal = PonyGuard.grounded_refusal(requirement, evidence)
    assert refusal["reason_summary"].startswith("Đoạn văn")
    assert refusal["coverage_gaps"][0].startswith("Đoạn văn")
    assert all(len(gap) > 1 for gap in refusal["coverage_gaps"])


def test_pipeline_runs_bounded_coverage_probes_then_returns_grounded_refusal():
    chunk = Chunk("doc_004269", "doc_004269_chunk_000001", HANOI_SUPPORT["evidence_quote"])
    class Retriever:
        last_timing = {}
        def __init__(self): self.queries = []
        def retrieve(self, query, *_): self.queries.append(query); return [chunk]
    class LLM:
        def __init__(self): self.values = iter([
            {"entity": "Hà Nội", "requested_attribute": "số học sinh"},
            {"entity_match": True, "attribute_match": True, "conflict_detected": False, "reasoning_allowed": True, "inference_level": "DIRECT", "support": [HANOI_SUPPORT]},
            {"entity_match": True, "attribute_match": True, "conflict_detected": False, "reasoning_allowed": True, "inference_level": "DIRECT", "support": [HANOI_SUPPORT]},
        ])
        def json(self, *_): return next(self.values), LLMResponse("{}", 1, 1, 1)
    retriever = Retriever()
    result = PonyGuard(retriever, LLM()).run({"sample_id": "hn", "question": "Hiện tại Hà Nội có bao nhiêu học sinh ở tất cả các trường học?", "gold_answers": [], "expected_action": "ABSTAIN"})
    assert result["prediction"]["decision"] == "ABSTAIN"
    assert "982.579" in result["prediction"]["answer"]
    assert len(retriever.queries) == 3
    assert result["trace"]["coverage"]["probe_queries"]
