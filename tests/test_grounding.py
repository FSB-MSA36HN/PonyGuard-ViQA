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


def test_grounding_validator_rejects_an_answer_that_only_echoes_the_question():
    chunk = Chunk("grammar", "grammar_1", "Động từ là từ dùng để chỉ hoạt động, trạng thái của sự vật.")
    value = {"answer": "Động từ", "citation_chunk_ids": [chunk.chunk_id], "evidence_quote": "Động từ là từ dùng để chỉ hoạt động"}
    assert not validate_grounding(value, [chunk], "Động từ là gì?")[0]["valid"]


def test_basic_rag_repairs_an_echo_into_a_self_contained_grounded_answer():
    chunk = Chunk("grammar", "grammar_1", "Động từ là từ dùng để chỉ hoạt động, trạng thái của sự vật.")
    class Retriever:
        def retrieve(self, *_): return [chunk]
    class LLM:
        def __init__(self): self.values = iter([
            {"answer": "Động từ", "citation_chunk_ids": [chunk.chunk_id], "evidence_quote": "Động từ là từ dùng để chỉ hoạt động"},
            {"answer": "Động từ là từ dùng để chỉ hoạt động.", "citation_chunk_ids": [chunk.chunk_id], "evidence_quote": "Động từ là từ dùng để chỉ hoạt động"},
        ])
        def json(self, *_): return next(self.values), LLMResponse("{}", 1, 1, 1)
    result = BasicRAG(Retriever(), LLM()).run({"sample_id": "definition", "question": "Động từ là gì?", "gold_answers": [], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert result["prediction"]["answer"] == "Động từ là từ dùng để chỉ hoạt động."


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


def test_relation_contradiction_is_rejected_even_when_the_quote_is_literal():
    evidence = {"support": [{
        "chunk_id": CHUNK.chunk_id, "evidence_quote": "Ở Việt Nam có 5 cấp học", "candidate_answer": "5 cấp học",
        "support_type": "DIRECT", "premise_status": "CONTRADICTED", "relation_match": False,
    }]}
    supports, rejected = PonyGuard.validated_supports(evidence, [CHUNK], "Ở Việt Nam có 4 cấp học?")
    assert not supports and any("Premise" in reason or "Quan hệ" in reason for reason in rejected)


def test_strict_relation_rejects_a_nearby_but_different_attribute():
    source = Chunk("subject", "subject_1", "Subject stores food as starch.")
    evidence = {"support": [{
        "chunk_id": source.chunk_id, "evidence_quote": source.text, "candidate_answer": "starch",
        "support_type": "DIRECT", "attribute_match": False, "relation_match": True, "premise_status": "SUPPORTED",
    }]}
    supports, rejected = PonyGuard.validated_supports(evidence, [source], "What is Subject's embryo storage form?", strict_relation=True, expected_entity="Subject")
    assert not supports and any("Thuộc tính" in reason for reason in rejected)


def test_contradiction_first_verdict_cannot_be_overridden_by_candidate_labels():
    source = Chunk("transfer", "transfer_1", "Protein transfers material from A to B.")
    evidence = {"support": [{"chunk_id": source.chunk_id, "evidence_quote": source.text, "candidate_answer": "B", "support_type": "DIRECT", "attribute_match": True, "relation_match": True, "premise_status": "SUPPORTED"}]}
    class LLM:
        def json(self, *_): return {"verdicts": [{"chunk_id": source.chunk_id, "verdict": "CONTRADICTED", "mismatch_dimension": "direction"}]}, LLMResponse("{}", 1, 1, 1)
    guard = PonyGuard(None, LLM())
    guard.verify_relations("Where is material transferred from B?", Requirement(entity="Protein", requested_attribute="transfer from B"), evidence, [source], {})
    supports, rejected = guard.validated_supports(evidence, [source], "Where is material transferred from B?", strict_relation=True, expected_entity="Protein")
    assert not supports and any("contradicted" in reason for reason in rejected)


def test_source_level_binding_recovers_direct_support_when_model_entity_spans_are_malformed():
    source = Chunk("country", "country_1", "Country A has 12 plant species in total.")
    evidence = {"support": [{
        "chunk_id": source.chunk_id, "evidence_quote": "12 plant species in total", "candidate_answer": "12",
        "support_type": "DIRECT", "question_entity_quote": "How many plant species does Country A have?", "evidence_entity_quote": "12 plant species in total",
    }]}
    supports, rejected = PonyGuard.validated_supports(evidence, [source], "How many plant species does Country A have?")
    assert len(supports) == 1 and not rejected


def test_vietnam_plants_support_is_not_rejected_when_the_entity_is_outside_the_short_quote():
    source = Chunk("doc_003879", "doc_003879_chunk_000001", "Việt Nam có mức đa dạng sinh học cao. 15.986 loài thực vật đã được tìm thấy trong cả nước, trong đó 10% là loài đặc hữu.")
    evidence = {"support": [{
        "chunk_id": source.chunk_id, "evidence_quote": "15.986 loài thực vật đã được tìm thấy trong cả nước", "candidate_answer": "15.986",
        "support_type": "DIRECT", "question_entity_quote": "Việt Nam có bao nhiêu loài thực vật theo như trong tài liệu nói?", "evidence_entity_quote": "15.986 loài thực vật đã được tìm thấy trong cả nước",
    }]}
    supports, rejected = PonyGuard.validated_supports(evidence, [source], "Việt Nam có bao nhiêu loài thực vật theo như trong tài liệu nói?")
    assert len(supports) == 1 and not rejected


def test_relation_verified_direct_support_uses_source_binding_when_entity_spans_are_malformed():
    source = Chunk("country", "country_1", "Country A banned discriminatory statements in the press from 1881.")
    evidence = {"support": [{
        "chunk_id": source.chunk_id, "evidence_quote": source.text, "candidate_answer": "1881",
        "support_type": "DIRECT", "question_entity_quote": "When did Country A ban discriminatory statements in the press?",
        "evidence_entity_quote": source.text, "attribute_match": True, "relation_match": True, "premise_status": "SUPPORTED",
    }]}
    supports, rejected = PonyGuard.validated_supports(evidence, [source], "When did Country A ban discriminatory statements in the press?", strict_relation=True)
    assert len(supports) == 1 and not rejected


def test_relation_verified_support_repairs_a_nonliteral_quote_from_the_literal_answer():
    source = Chunk("work", "work_1", "The painting is displayed inside the National Museum.")
    evidence = {"support": [{
        "chunk_id": source.chunk_id, "evidence_quote": "The painting is displayed in the National Museum",
        "candidate_answer": "National Museum", "support_type": "DIRECT", "question_entity_quote": "The painting",
        "evidence_entity_quote": "The painting", "attribute_match": True, "relation_match": True, "premise_status": "SUPPORTED",
    }]}
    supports, rejected = PonyGuard.validated_supports(evidence, [source], "Where is the painting displayed?", strict_relation=True, expected_entity="the painting")
    assert len(supports) == 1 and not rejected
    assert supports[0]["evidence_quote"] == source.text


def test_expected_entity_must_bind_to_the_source_even_when_the_verifier_accepts():
    source = Chunk("person", "person_1", "Taylor Example was born in 1958.")
    evidence = {"support": [{
        "chunk_id": source.chunk_id, "evidence_quote": source.text, "candidate_answer": "1958",
        "support_type": "DIRECT", "attribute_match": True, "relation_match": True, "premise_status": "SUPPORTED",
    }]}
    supports, rejected = PonyGuard.validated_supports(evidence, [source], "When was he born?", strict_relation=True, expected_entity="he")
    assert not supports and any("khớp thực thể" in reason for reason in rejected)


def test_single_valid_direct_support_is_immutable_without_writer_or_claim_calls():
    source = Chunk("source", "source", "Subject has a verified value of 5.")
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return [source]
    class LLM:
        def __init__(self): self.values = iter([
            {"entity": "Subject", "requested_attribute": "verified value", "question_complete": True, "missing_requirements": []},
            {"support": [{"chunk_id": source.chunk_id, "evidence_quote": source.text, "candidate_answer": "5", "support_type": "DIRECT"}]},
            {"verdicts": [{"chunk_id": source.chunk_id, "verdict": "MATCH"}]},
        ])
        def json(self, *_): return next(self.values), LLMResponse("{}", 1, 1, 1)
    result = PonyGuard(Retriever(), LLM(), intent_first=True).run({"sample_id": "canonical", "question": "What is Subject's verified value?", "gold_answers": ["5"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert result["prediction"]["answer"] == "5"
    assert "answer" not in result["performance"]["stages"] and "verification" not in result["performance"]["stages"]


def test_empty_semantic_contract_recovers_a_direct_grounded_answer():
    source = Chunk("us", "us_1", "Ngày 4 tháng 7 được chào mừng như là ngày quốc khánh của Mỹ.")
    class Retriever:
        def retrieve(self, *_): return [source]
    class LLM:
        def __init__(self): self.values = iter([
                {},
                {"entity": "Mỹ", "requested_attribute": "ngày Quốc khánh", "question_clear": True, "missing_requirements": []},
                {"decision": "ABSTAIN", "missing_requirements": []},
                {"answer": "4 tháng 7", "citation_chunk_ids": ["us_1"], "evidence_quote": source.text, "question_entity_quote": "Mỹ", "evidence_entity_quote": "Mỹ", "question_relation": "Ngày Quốc khánh", "evidence_relation": "ngày quốc khánh", "relation_match": True, "premise_status": "SUPPORTED"},
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
