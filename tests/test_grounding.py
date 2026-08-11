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
            {"entity": "Việt Nam", "requested_attribute": "số cấp học", "question_clear": True},
            {"entity_match": True, "attribute_match": True, "conflict_detected": False, "inference_level": "DIRECT", "reasoning_allowed": True, "evidence_sufficient": False, "decision_rationale": "Không đủ.", "support": [{"chunk_id": CHUNK.chunk_id, "evidence_quote": "Ở Việt Nam có 5 cấp học", "candidate_answer": "5 cấp học", "support_type": "DIRECT"}]},
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
