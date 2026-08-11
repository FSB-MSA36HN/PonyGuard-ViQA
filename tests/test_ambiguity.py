from ponyguard_viqa.core import Requirement, add_clarification, missing_requirements_from_question, question_ambiguity
from ponyguard_viqa.pipelines import PonyGuard


def test_quantity_ellipsis_is_contextual_ask_not_an_answerable_attribute():
    question = "Hiện tại Việt Nam có mấy?"
    requirement = PonyGuard.apply_clarity_guard(question, Requirement())
    assert missing_requirements_from_question(question) == ["requested_attribute"]
    assert requirement.ambiguity_type == "AMBIGUOUS_ATTRIBUTE"
    assert requirement.entity == "Việt Nam"
    question = PonyGuard.clarification_question(requirement, question)
    assert "Việt Nam" in question and "người" in question and "tỉnh/thành" in question and "cấp học" in question
    assert PonyGuard.decide(requirement, {}) == "ASK"


def test_explicit_quantity_attribute_is_not_ambiguous():
    for question in ("Việt Nam có bao nhiêu cấp học?", "Việt Nam có bao nhiêu loài thực vật?", "Hà Nội có mấy quận?"):
        assert question_ambiguity(question) == ([], "NONE")


def test_followup_clears_ambiguity_without_becoming_evidence():
    merged = add_clarification("Hiện tại Việt Nam có mấy?", "Tôi hỏi mấy cấp học.")
    requirement = PonyGuard.apply_clarity_guard(merged, Requirement())
    assert requirement.ambiguity_type == "NONE" and not requirement.missing_requirements


def test_model_options_are_short_suggestions_not_facts():
    requirement = PonyGuard.apply_clarity_guard("Việt Nam có mấy?", Requirement(entity="Việt Nam", clarification_options=["người", "tỉnh/thành", "cấp học", "15.986 loài"]))
    assert requirement.clarification_options == ["người", "tỉnh/thành", "cấp học"]


def test_ambiguous_question_asks_before_retrieval_or_evidence_call():
    class Retriever:
        def retrieve(self, *_): raise AssertionError("ASK must not retrieve")
    class LLM:
        def json(self, *_):
            from ponyguard_viqa.llm import LLMResponse
            return {"entity": "Việt Nam", "requested_attribute": None}, LLMResponse("{}", 1, 1, 1)
    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "ask", "question": "Hiện tại Việt Nam có mấy?", "gold_answers": [], "expected_action": "ASK"})
    assert result["prediction"]["decision"] == "ASK"
    assert result["performance"]["llm_calls"] == 1
