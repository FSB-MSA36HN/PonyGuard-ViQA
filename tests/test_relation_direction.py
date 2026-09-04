"""S1.2: a support whose source states the relation with swapped roles is rejected.

A reversed actor/patient passes every deterministic check already in place, and
the relation verifier has been measured returning MATCH on it. The direction
comparison below is the part decided in Python.
"""
from ponyguard_viqa.core import Chunk
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import PonyGuard

CHUNK = Chunk("d", "d_1", "Làng Olympic nằm ở Thung lũng Lower Lea do tập đoàn Lend Lease xây dựng.")
SUPPORT = {"chunk_id": "d_1", "support_type": "DIRECT", "evidence_quote": CHUNK.text,
           "candidate_answer": "Thung lũng Lower Lea", "premise_status": "SUPPORTED",
           "relation_match": True, "attribute_match": True}


def triple_llm(question_subject, source_subject, source_object):
    class LLM:
        def json(self, *_):
            return {"question": {"subject": question_subject}, "source": {"subject": source_subject, "object": source_object}}, LLMResponse("{}", 1, 1, 1)
    return LLM()


def test_an_identity_question_is_not_a_role_swap():
    """The Italy case: "what is the capital of X?" puts the queried term on the
    source's object side because the relation is symmetric, and the answer is the
    source's subject. Rejecting that is a false positive."""
    support = {"chunk_id": "d_1", "support_type": "DIRECT",
               "evidence_quote": "Với vai trò là thủ đô của nước Ý, Roma là trụ sở của các tổ chức.",
               "candidate_answer": "Roma", "premise_status": "SUPPORTED",
               "relation_match": True, "attribute_match": True}
    llm = triple_llm("Thủ đô của nước Ý", "Roma", "thủ đô của nước Ý")
    aligned, _ = PonyGuard(None, llm).direction_matches("Thủ đô của nước Ý là gì?", support, {})
    assert aligned is True


def test_a_swapped_role_is_detected():
    llm = triple_llm("Tập đoàn Lend Lease", "Làng Olympic", "tập đoàn Lend Lease")
    aligned, _ = PonyGuard(None, llm).direction_matches("Tập đoàn Lend Lease được xây dựng ở đâu?", SUPPORT, {})
    assert aligned is False


def test_the_same_direction_as_the_source_is_kept():
    llm = triple_llm("Làng Olympic", "Làng Olympic", "Thung lũng Lower Lea")
    aligned, _ = PonyGuard(None, llm).direction_matches("Làng Olympic nằm ở đâu?", SUPPORT, {})
    assert aligned is True


def test_a_tie_or_missing_span_leaves_the_support_alone():
    """Fail-safe: only a strictly better match against the object is evidence."""
    for subject, source_subject, source_object in [("X", "", ""), ("Làng Olympic", "Làng Olympic", "Làng Olympic"), ("", "a", "b")]:
        aligned, _ = PonyGuard(None, triple_llm(subject, source_subject, source_object)).direction_matches("Q?", SUPPORT, {})
        assert aligned is True


def test_a_malformed_direction_contract_cannot_reject_a_support():
    class LLM:
        def json(self, *_): return {"_parse_error": True}, LLMResponse("{}", 1, 1, 1)
    aligned, _ = PonyGuard(None, LLM()).direction_matches("Q?", SUPPORT, {})
    assert aligned is True


def test_a_reversed_support_turns_a_would_be_answer_into_abstain():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return [CHUNK]

    class LLM:
        def __init__(self): self.calls = 0
        def json(self, request, *_):
            self.calls += 1
            if "slot_bindings" in request:
                return {"entity": "Tập đoàn Lend Lease", "requested_attribute": "nơi xây dựng", "answer_type": "LOCATION",
                        "question_complete": True, "missing_requirements": []}, LLMResponse("{}", 1, 1, 1)
            if "verdicts" in request:
                return {"verdicts": [{"chunk_id": "d_1", "verdict": "MATCH"}]}, LLMResponse("{}", 1, 1, 1)
            if "source" in request and "subject" in request:
                return {"question": {"subject": "Tập đoàn Lend Lease"}, "source": {"subject": "Làng Olympic", "object": "tập đoàn Lend Lease"}}, LLMResponse("{}", 1, 1, 1)
            return {"support": [dict(SUPPORT)]}, LLMResponse("{}", 1, 1, 1)
        def generate(self, *_): return LLMResponse("", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM(), intent_first=True).run(
        {"sample_id": "reversed", "question": "Tập đoàn Lend Lease được xây dựng ở đâu?", "gold_answers": [], "expected_action": "ABSTAIN"}
    )
    assert result["prediction"]["decision"] == "ABSTAIN"
    assert any("Hướng quan hệ" in r for r in result["trace"]["evidence"]["support_rejections"])


def test_fallback_skips_an_unavailable_provider_for_the_rest_of_the_question():
    """One timeout per question, not one per stage."""
    from ponyguard_viqa.llm import FallbackLLM, ProviderQuotaError

    class Primary:
        model_name, max_tokens = "remote", 128
        def __init__(self): self.attempts = 0
        def generate(self, *_):
            self.attempts += 1
            raise ProviderQuotaError("Provider temporarily unavailable (429)")

    class Local:
        def generate(self, *_): return LLMResponse("local", 1, 1, 1)

    primary = Primary()
    llm = FallbackLLM(primary, Local())
    for _ in range(4):
        assert llm.generate("x").text == "local"
    assert primary.attempts == 1, "provider should be retried once, not once per stage"
    assert "429" in llm.generate("x").fallback_reason


