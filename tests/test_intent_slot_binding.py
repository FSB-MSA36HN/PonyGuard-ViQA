"""Change A: intent resolves slots from literal question spans, not a global judgement.

Fixtures use concrete wording only as data; every rule under test is schema-driven.
"""
from ponyguard_viqa.core import Requirement, intent_slot_bindings
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import PonyGuard


def binding(slot, span, status):
    return {"slot": slot, "span": span, "status": status}


def test_referential_span_marks_its_slot_unresolved():
    question = "Ông ấy sinh năm bao nhiêu?"
    bindings, unresolved = intent_slot_bindings(question, [
        binding("entity", "Ông ấy", "REFERENTIAL"),
        binding("requested_attribute", "sinh năm bao nhiêu", "RESOLVED"),
    ])
    assert unresolved == ["entity"]
    assert bindings[0]["literal"] is True


def test_absent_optional_dimension_never_becomes_a_missing_slot():
    """Acceptance criterion 5: optional country/location/time/scope cannot force ASK."""
    _, unresolved = intent_slot_bindings("Bức tranh Mona Lisa được trưng bày ở đâu?", [
        binding("entity", "Bức tranh Mona Lisa", "RESOLVED"),
        binding("requested_attribute", "được trưng bày ở đâu", "RESOLVED"),
        binding("time", "", "ABSENT"),
        binding("country", "", "ABSENT"),
        binding("scope", "", "ABSENT"),
    ])
    assert unresolved == []


def test_absent_required_slot_is_unresolved_like_an_empty_slot_string():
    _, unresolved = intent_slot_bindings("Con hươu cao cổ có mấy?", [
        binding("entity", "Con hươu cao cổ", "RESOLVED"),
        binding("requested_attribute", "", "ABSENT"),
    ])
    assert unresolved == ["requested_attribute"]


def test_a_span_absent_from_the_question_cannot_manufacture_a_clarification():
    _, unresolved = intent_slot_bindings("A fully specified question?", [
        binding("entity", "a span the question never contains", "REFERENTIAL"),
    ])
    assert unresolved == []


def test_unknown_slots_and_statuses_are_ignored_rather_than_trusted():
    bindings, unresolved = intent_slot_bindings("A question?", [
        binding("not_a_schema_slot", "A question", "REFERENTIAL"),
        binding("entity", "A question", "NOT_AN_ENUM_VALUE"),
        "not an object",
    ])
    assert bindings == [] and unresolved == []


def test_the_dimension_an_interrogative_asks_for_is_never_a_missing_input():
    """A question asking for a time states the requested value; it does not reference one."""
    bindings, unresolved = intent_slot_bindings("Khi nào Việt Cách bắt đầu tiến vào Việt Nam?", [
        binding("entity", "Việt Cách", "RESOLVED"),
        binding("requested_attribute", "bắt đầu tiến vào Việt Nam", "RESOLVED"),
        binding("time", "Khi nào", "REFERENTIAL"),
    ], answer_type="TIME")
    assert unresolved == []
    assert bindings[-1]["interrogative"] is True


def test_a_referenced_dimension_the_question_does_not_ask_for_stays_unresolved():
    """The same slot, when it is an input rather than the requested value, still asks."""
    _, unresolved = intent_slot_bindings("Dân số Hà Nội khi đó là bao nhiêu?", [
        binding("entity", "Hà Nội", "RESOLVED"),
        binding("requested_attribute", "Dân số", "RESOLVED"),
        binding("time", "khi đó", "REFERENTIAL"),
    ], answer_type="COUNT")
    assert unresolved == ["time"]


def test_a_location_question_does_not_ask_for_its_own_answer_dimension():
    _, unresolved = intent_slot_bindings("Bức tranh Mona Lisa được trưng bày ở đâu?", [
        binding("entity", "Bức tranh Mona Lisa", "RESOLVED"),
        binding("location", "ở đâu", "REFERENTIAL"),
    ], answer_type="LOCATION")
    assert unresolved == []


def test_span_bound_slot_survives_the_extracted_slot_guard():
    """The pronoun case: the entity is literally in the question, yet unresolved."""
    question = "Ông ấy sinh năm bao nhiêu?"
    requirement = PonyGuard.apply_clarity_guard(
        question,
        Requirement(entity="ông ấy", requested_attribute="năm sinh", missing_requirements=["entity"]),
        ["entity"],
    )
    assert requirement.missing_requirements == ["entity"] and not requirement.question_clear


def test_span_bound_slot_survives_the_malformed_flood_guard():
    question = "Dân số Hà Nội khi đó là bao nhiêu?"
    requirement = PonyGuard.apply_clarity_guard(
        question,
        Requirement(entity="Hà Nội", requested_attribute="dân số", missing_requirements=["time", "country", "location", "scope"]),
        ["time"],
    )
    assert requirement.missing_requirements == ["time"]


def test_unbound_slot_flood_is_still_suppressed():
    requirement = PonyGuard.apply_clarity_guard(
        "What is the difference between the two stated rates?",
        Requirement(entity="the two stated rates", requested_attribute="difference", missing_requirements=["country", "location", "time", "scope"]),
    )
    assert requirement.question_clear and not requirement.missing_requirements


def test_intent_asks_before_retrieval_when_a_span_is_referential():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_):
            raise AssertionError("a validated ASK must not reach retrieval")

    class LLM:
        def json(self, *_):
            return {
                "entity": "Hà Nội", "requested_attribute": "dân số", "answer_type": "COUNT",
                "question_complete": True, "missing_requirements": [],
                "slot_bindings": [
                    binding("entity", "Hà Nội", "RESOLVED"),
                    binding("requested_attribute", "Dân số", "RESOLVED"),
                    binding("time", "khi đó", "REFERENTIAL"),
                ],
            }, LLMResponse("{}", 1, 1, 1)
        def generate(self, *_):
            return LLMResponse("Bạn muốn biết dân số Hà Nội vào thời điểm nào?", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM(), intent_first=True).run(
        {"sample_id": "referential-time", "question": "Dân số Hà Nội khi đó là bao nhiêu?", "gold_answers": [], "expected_action": "ASK"}
    )
    assert result["prediction"]["decision"] == "ASK"
    assert result["trace"]["requirements"]["missing_requirements"] == ["time"]


def test_intent_stays_clear_when_every_optional_dimension_is_absent():
    from ponyguard_viqa.core import Chunk

    class Retriever:
        last_timing = {}
        def retrieve(self, *_):
            return [Chunk("d", "d_1", "Bức tranh Mona Lisa được trưng bày tại bảo tàng Louvre.")]

    class LLM:
        def json(self, *_):
            return {
                "entity": "Mona Lisa", "requested_attribute": "nơi trưng bày", "answer_type": "LOCATION",
                "question_complete": True, "missing_requirements": [],
                "slot_bindings": [
                    binding("entity", "Mona Lisa", "RESOLVED"),
                    binding("requested_attribute", "được trưng bày ở đâu", "RESOLVED"),
                    binding("time", "", "ABSENT"),
                    binding("country", "", "ABSENT"),
                ],
                "support": [],
            }, LLMResponse("{}", 1, 1, 1)
        def generate(self, *_):
            return LLMResponse("", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM(), intent_first=True).run(
        {"sample_id": "absent-optional", "question": "Bức tranh Mona Lisa được trưng bày ở đâu?", "gold_answers": [], "expected_action": "ANSWER"}
    )
    assert result["prediction"]["decision"] != "ASK"
    assert result["trace"]["requirements"]["missing_requirements"] == []


def test_a_resolved_dimension_cannot_also_be_alleged_missing():
    """A question that fixes its place does not need a clarification about that place."""
    requirement = PonyGuard.apply_clarity_guard(
        "Những bệnh viện lớn nào ở Hà Nội đang quá tải?",
        Requirement(
            entity="bệnh viện", requested_attribute="tên", answer_type="LOCATION",
            missing_requirements=["country"],
            slot_bindings=[{"slot": "location", "span": "ở Hà Nội", "status": "RESOLVED", "literal": True}],
        ),
    )
    assert requirement.question_clear and not requirement.missing_requirements


def test_an_unresolved_dimension_is_still_alleged_when_nothing_binds_it():
    requirement = PonyGuard.apply_clarity_guard(
        "Quốc khánh là ngày nào?",
        Requirement(entity="Quốc khánh", requested_attribute="ngày", answer_type="DATE", missing_requirements=["country"]),
    )
    assert requirement.missing_requirements == ["country"]


def test_a_resolved_sibling_of_a_different_answer_type_does_not_cover_the_allegation():
    requirement = PonyGuard.apply_clarity_guard(
        "Dân số là bao nhiêu ở đó?",
        Requirement(
            entity="Dân số", requested_attribute="số dân", answer_type="COUNT",
            missing_requirements=["location"],
            slot_bindings=[{"slot": "time", "span": "", "status": "ABSENT", "literal": False}],
        ),
    )
    assert requirement.missing_requirements == ["location"]
