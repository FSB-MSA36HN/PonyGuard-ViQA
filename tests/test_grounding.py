from ponyguard_viqa.core import Chunk, Requirement
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard, validate_grounding


CHUNK = Chunk("doc_003896", "doc_003896_chunk_000001", "Ở Việt Nam có 5 cấp học: tiểu học, trung học cơ sở, trung học phổ thông, đại học và sau đại học.")


def test_grounding_validator_accepts_literal_quote_and_rejects_wrong_quote_id_or_number():
    good = {"answer": "5 cấp học", "citation_chunk_ids": [CHUNK.chunk_id], "evidence_quote": "Ở Việt Nam có 5 cấp học"}
    assert validate_grounding(good, [CHUNK])[0]["valid"]
    assert not validate_grounding({**good, "evidence_quote": "Việt Nam có 4 cấp học"}, [CHUNK])[0]["valid"]
    assert not validate_grounding({**good, "citation_chunk_ids": ["missing"]}, [CHUNK])[0]["valid"]
    assert not validate_grounding({**good, "answer": "4 cấp học"}, [CHUNK])[0]["valid"]


def test_basic_rag_with_wrong_numeric_answer_never_emits_it():
    class Retriever: 
        def retrieve(self, *_): return [CHUNK]
    class LLM:
        def __init__(self): self.values = iter([{"answer": "4 cấp học", "citation_chunk_ids": [CHUNK.chunk_id], "evidence_quote": "Ở Việt Nam có 5 cấp học"}] * 2)
        def json(self, *_): return next(self.values), LLMResponse("{}", 1, 1, 1)
    result = BasicRAG(Retriever(), LLM()).run({"sample_id": "levels", "question": "Việt Nam có bao nhiêu cấp học?", "gold_answers": ["5 cấp học"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ABSTAIN" and "4 cấp" not in result["prediction"]["answer"]
    assert result["performance"]["stages"]["answer"]["llm_calls"] == 1


def test_ponyguard_direct_valid_quote_answers_despite_bad_prose_verdict():
    class Retriever:
        def retrieve(self, *_): return [CHUNK]
    class LLM:
        def __init__(self): self.values = iter([
            {"entity": "Việt Nam", "requested_attribute": "số cấp học", "question_clear": True, "entity_match": True, "attribute_match": True, "conflict_detected": False, "inference_level": "DIRECT", "reasoning_allowed": True, "evidence_sufficient": False, "decision_rationale": "Không đủ.", "support": [{"chunk_id": CHUNK.chunk_id, "evidence_quote": "Ở Việt Nam có 5 cấp học", "candidate_answer": "5 cấp học", "support_type": "DIRECT", "question_entity_quote": "Việt Nam", "evidence_entity_quote": "Việt Nam"}]},
            {"answer": "5 cấp học", "citation_chunk_ids": [CHUNK.chunk_id], "evidence_quote": "Ở Việt Nam có 5 cấp học"},
            {"claims": [{"text": "5 cấp học", "label": "SUPPORTED", "evidence_chunk_ids": [CHUNK.chunk_id]}]},
        ])
        def json(self, *_): return next(self.values), LLMResponse("{}", 1, 1, 1)
    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "levels", "question": "Việt Nam có bao nhiêu cấp học?", "gold_answers": ["5 cấp học"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER" and result["prediction"]["answer"] == "5 cấp học"


def test_ponyguard_rejects_missing_support_and_asks_only_for_referent():
    evidence = {"entity_match": True, "attribute_match": True, "valid_supports": [], "reasoning_allowed": True, "inference_level": "DIRECT"}
    assert PonyGuard.decide(Requirement(entity="Việt Nam", requested_attribute="dân số"), evidence) == "ABSTAIN"
    assert PonyGuard.decide(Requirement(missing_requirements=["entity"]), evidence) == "ASK"


def test_support_conflict_is_rejected():
    other = Chunk("d", "other", "Ở Việt Nam có 4 cấp học.")
    evidence = {"support": [
        {"chunk_id": CHUNK.chunk_id, "evidence_quote": "Ở Việt Nam có 5 cấp học", "candidate_answer": "5 cấp học", "support_type": "DIRECT"},
        {"chunk_id": other.chunk_id, "evidence_quote": "Ở Việt Nam có 4 cấp học", "candidate_answer": "4 cấp học", "support_type": "DIRECT"},
    ]}
    _, rejected = PonyGuard.validated_supports(evidence, [CHUNK, other])
    assert evidence["conflict_detected"] and rejected


def test_support_for_a_different_entity_is_rejected_even_when_the_quote_is_valid():
    other = Chunk("doc_2", "other_1", "Khánh Hòa là một tỉnh ven biển của Việt Nam.")
    evidence = {"support": [{"chunk_id": other.chunk_id, "evidence_quote": other.text, "candidate_answer": "Khánh Hòa", "support_type": "DIRECT", "question_entity_quote": "Quốc Khánh", "evidence_entity_quote": "Khánh Hòa"}]}
    supports, rejected = PonyGuard.validated_supports(evidence, [other], "Quốc Khánh là gì?")
    assert not supports and any("khớp thực thể" in reason for reason in rejected)


def test_empty_semantic_contract_recovers_a_direct_grounded_answer():
    source = Chunk("us", "us_1", "Ngày 4 tháng 7 được chào mừng như là ngày quốc khánh của Hợp chúng quốc châu Mỹ.")
    class Retriever:
        def retrieve(self, *_): return [source]
    class LLM:
        def __init__(self): self.values = iter([
            {},
            {"answer": "4 tháng 7", "citation_chunk_ids": ["us_1"], "evidence_quote": source.text, "question_entity_quote": "Mỹ", "evidence_entity_quote": "Mỹ"},
            {"claims": [{"text": "4 tháng 7", "label": "SUPPORTED", "evidence_chunk_ids": ["us_1"]}]},
        ])
        def json(self, *_): return next(self.values), LLMResponse("{}", 1, 1, 1)
    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "recovery", "question": "Ngày Quốc khánh của Mỹ?", "gold_answers": [], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert result["prediction"]["answer"] == "4 tháng 7"
    assert result["trace"]["evidence"]["evidence_recovery"]["applied"]


def test_partial_semantic_contract_still_recovers_direct_evidence():
    assert PonyGuard.semantic_contract_is_empty({"entity": "a country", "requested_attribute": "", "support": []})


def test_follow_up_accepts_an_expanded_literal_entity_label_and_single_support_object():
    chunk = Chunk("us", "us_1", "Ngày 4 tháng 7 được chào mừng như là ngày quốc khánh.")
    evidence = {"chunk_id": "us_1", "evidence_quote": chunk.text, "candidate_answer": "4 tháng 7", "support_type": "direct", "question_entity_quote": "Quốc Khánh", "evidence_entity_quote": "ngày quốc khánh"}
    supports, rejected = PonyGuard.validated_supports(evidence, [chunk], "Quốc Khánh là gì?\n\nThông tin làm rõ từ người dùng: Mỹ")
    assert len(supports) == 1 and not rejected and supports[0]["support_type"] == "DIRECT"
