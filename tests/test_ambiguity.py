from ponyguard_viqa.core import Requirement, add_clarification
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import PonyGuard


def test_quantity_ellipsis_is_contextual_ask_not_an_answerable_attribute():
    question = "Hiện tại Việt Nam có mấy?"
    requirement = PonyGuard.apply_clarity_guard(question, Requirement(entity="Việt Nam", missing_requirements=["requested_attribute"]))
    assert requirement.ambiguity_type == "MISSING_REQUIREMENT"
    assert requirement.entity == "Việt Nam"
    question = PonyGuard.clarification_question(requirement, question)
    assert question == "Bạn muốn biết thuộc tính hoặc thông tin nào về Việt Nam?"
    assert PonyGuard.decide(requirement, {}) == "ASK"


def test_explicit_quantity_attribute_is_not_ambiguous():
    for question in ("Việt Nam có bao nhiêu cấp học?", "Việt Nam có bao nhiêu loài thực vật?", "Hà Nội có mấy quận?"):
        assert PonyGuard.apply_clarity_guard(question, Requirement()).missing_requirements == []


def test_extracted_slots_cannot_also_be_used_to_ask_the_same_question_again():
    requirement = PonyGuard.apply_clarity_guard("con người có mấy cái đầu?", Requirement(entity="con người", requested_attribute="số lượng đầu", missing_requirements=["entity", "requested_attribute"]))
    assert requirement.question_clear and not requirement.missing_requirements


def test_optional_context_slot_flood_cannot_turn_a_clear_relation_into_ask():
    requirement = PonyGuard.apply_clarity_guard(
        "What is the difference between the two stated rates?",
        Requirement(entity="the two stated rates", requested_attribute="difference", missing_requirements=["country", "location", "time", "scope"]),
    )
    assert requirement.question_clear and not requirement.missing_requirements


def test_clear_requirement_contract_with_an_omitted_slot_becomes_an_ask():
    requirement = PonyGuard.enforce_requirement_contract(
        {"question_clear": True, "entity": "an entity", "requested_attribute": None},
        Requirement(entity="an entity", question_clear=True),
    )
    requirement = PonyGuard.apply_clarity_guard("A complete-looking question", requirement)
    assert requirement.missing_requirements == ["requested_attribute"]


def test_partial_requirement_contract_with_only_an_entity_becomes_an_ask():
    requirement = PonyGuard.enforce_requirement_contract(
        {"entity": "an entity"},
        Requirement(entity="an entity"),
    )
    requirement = PonyGuard.apply_clarity_guard("A question", requirement)
    assert requirement.missing_requirements == ["requested_attribute"]


def test_partial_semantic_output_cannot_turn_an_incomplete_request_into_abstain():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return []

    class LLM:
        def json(self, *_): return {"entity": "an entity"}, LLMResponse("{}", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "partial-contract", "question": "An incomplete quantity request", "gold_answers": [], "expected_action": "ASK"})
    assert result["prediction"]["decision"] == "ASK"
    assert result["trace"]["requirements"]["missing_requirements"] == ["requested_attribute"]


def test_malformed_semantic_output_recovers_requirements_before_deciding():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return []

    class LLM:
        def __init__(self): self.outputs = iter([
            {"_parse_error": True},
            {"entity": "an entity", "requested_attribute": None, "question_clear": False, "missing_requirements": ["requested_attribute"]},
        ])
        def json(self, *_): return next(self.outputs), LLMResponse("{}", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "recovered-requirement", "question": "An incomplete request", "gold_answers": [], "expected_action": "ASK"})
    assert result["prediction"]["decision"] == "ASK"
    assert result["trace"]["evidence"]["requirement_recovery"]["applied"] is True


def test_followup_clears_ambiguity_without_becoming_evidence():
    merged = add_clarification("Hiện tại Việt Nam có mấy?", "Tôi hỏi mấy cấp học.")
    requirement = PonyGuard.apply_clarity_guard(merged, Requirement())
    assert requirement.ambiguity_type == "NONE" and not requirement.missing_requirements


def test_supplied_clarification_resolves_the_slot_asked_on_the_previous_turn():
    question = add_clarification("toán học có mấy phép toán?", "trong lĩnh vực đại số tuyến tính nhé")
    requirement = PonyGuard.apply_user_clarification(
        question,
        PonyGuard.apply_clarity_guard(question, Requirement(entity="toán học", requested_attribute="phép toán", missing_requirements=["scope"])),
        ["scope"],
    )
    assert requirement.question_clear and not requirement.missing_requirements


def test_legacy_chat_reply_matching_the_only_offered_option_also_resolves_it():
    question = add_clarification("toán học có mấy phép toán?", "trong lĩnh vực đại số tuyến tính nhé")
    requirement = PonyGuard.apply_user_clarification(
        question,
        PonyGuard.apply_clarity_guard(question, Requirement(missing_requirements=["scope"], clarification_options=["trong lĩnh vực đại số tuyến tính"])),
    )
    assert requirement.question_clear and not requirement.missing_requirements


def test_intent_first_does_not_ask_again_after_a_user_selects_a_spelling():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return []

    class LLM:
        def __init__(self): self.calls, self.requests = 0, []
        def json(self, request, *_):
            self.calls += 1; self.requests.append(request)
            if self.calls == 1:
                return {"entity": "báo đốm", "requested_attribute": "loài", "missing_requirements": ["entity"]}, LLMResponse("{}", 1, 1, 1)
            return {"support": [], "decision": None}, LLMResponse("{}", 1, 1, 1)

    llm = LLM()
    result = PonyGuard(Retriever(), llm, intent_first=True).run({
        "sample_id": "selected-spelling", "question": add_clarification("Bào đốm là con gì?", "Báo đốm"),
        "clarification_for": ["entity"], "gold_answers": [], "expected_action": "ABSTAIN",
    })
    assert result["prediction"]["decision"] != "ASK" and llm.calls > 1
    assert "Question: Báo đốm là con gì?" in llm.requests[0]


def test_adjudicator_cannot_reopen_a_slot_completed_by_the_user():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return []

    class LLM:
        def __init__(self):
            self.outputs = iter([
                {"entity": "toán học", "requested_attribute": "phép toán", "missing_requirements": ["scope"], "clarification_options": ["trong lĩnh vực đại số tuyến tính"], "entity_match": False, "attribute_match": False, "conflict_detected": False, "inference_level": "UNSUPPORTED", "reasoning_allowed": False, "support": []},
                {"decision": "ASK", "entity": "toán học", "requested_attribute": "phép toán", "missing_requirements": ["scope"], "clarification_question": "Bạn muốn hỏi trong phạm vi nào?"},
            ])
        def json(self, *_): return next(self.outputs), LLMResponse("{}", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM()).run({
        "sample_id": "completed-slot",
        "question": add_clarification("toán học có mấy phép toán?", "trong lĩnh vực đại số tuyến tính nhé"),
        "clarification_for": ["scope"], "gold_answers": [], "expected_action": "ABSTAIN",
    })
    assert result["prediction"]["decision"] == "ABSTAIN"
    assert result["trace"]["evidence"]["clarification_adjudication"]["missing_requirements"] == []


def test_model_options_are_short_suggestions_not_facts_or_fallbacks():
    requirement = PonyGuard.apply_clarity_guard("Việt Nam có mấy?", Requirement(entity="Việt Nam", missing_requirements=["requested_attribute"], clarification_options=["người", "tỉnh/thành", "cấp học", "15.986 loài"]))
    assert requirement.clarification_options == ["người", "tỉnh/thành", "cấp học"]


def test_country_dependent_date_keeps_a_vetted_semantic_missing_slot():
    question = "Quốc khánh là ngày mấy?"
    requirement = PonyGuard.apply_clarity_guard(
        question,
        Requirement(entity="Quốc khánh", requested_attribute="ngày diễn ra", answer_type="DATE", question_clear=False, missing_requirements=["country"]),
    )
    assert not requirement.question_clear and requirement.missing_requirements == ["country"]
    assert requirement.requested_attribute == "ngày diễn ra" and requirement.answer_type == "DATE"
    assert PonyGuard.clarification_question(requirement, question) == "Bạn muốn biết Quốc khánh của quốc gia nào?"


def test_malformed_missing_slot_flood_is_deferred_instead_of_forcing_ask():
    requirement = PonyGuard.apply_clarity_guard(
        "Define the quoted expression.",
        Requirement(requested_attribute="definition", missing_requirements=["entity", "location", "time", "scope"]),
    )
    assert requirement.question_clear and not requirement.missing_requirements


def test_semantic_asks_cover_common_missing_slots_without_accepting_bad_entity_labels():
    cases = [
        ("Hội nghị được tổ chức ở đâu?", "location", "Bạn muốn biết Hội nghị ở địa điểm nào?"),
        ("Cuộc bầu cử diễn ra khi nào?", "time", "Bạn muốn biết Cuộc bầu cử vào thời điểm nào?"),
        ("Số liệu này áp dụng cho ai?", "target", "Bạn đang nói tới người, vật hoặc đối tượng nào khi hỏi về thông tin này?"),
    ]
    for question, slot, expected in cases:
        entity = "Hội nghị" if slot == "location" else "Cuộc bầu cử" if slot == "time" else None
        requirement = PonyGuard.apply_clarity_guard(question, Requirement(entity=entity, missing_requirements=[slot]))
        assert requirement.missing_requirements == [slot]
        assert PonyGuard.clarification_question(requirement, question) == expected
    clear = PonyGuard.apply_clarity_guard("Việt Nam có bao nhiêu loài thực vật?", Requirement())
    assert not clear.missing_requirements
    person = PonyGuard.apply_clarity_guard("Người này là ai?", Requirement(missing_requirements=["target"]))
    assert person.missing_requirements == ["target"]


def test_model_generated_clarification_is_used_instead_of_fixed_choices():
    requirement = Requirement(entity="Việt Nam", missing_requirements=["requested_attribute"], ambiguity_type="AMBIGUOUS_ATTRIBUTE", clarification_question="Bạn muốn biết chỉ số nào của Việt Nam?")
    assert PonyGuard.clarification_question(requirement, "Việt Nam có mấy?") == "Bạn muốn biết chỉ số nào của Việt Nam?"


def test_dynamic_ambiguity_options_are_rendered_as_one_selection_question():
    requirement = Requirement(entity="a term", missing_requirements=["country", "requested_attribute"], clarification_options=["khái niệm", "quốc gia cụ thể", "một khía cạnh cụ thể"])
    question = PonyGuard.clarification_question(requirement, "A term is?")
    assert "khái niệm" in question and "quốc gia cụ thể" in question and "một khía cạnh cụ thể" in question


def test_ambiguous_question_is_decided_by_the_semantic_evidence_contract():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return []
    class LLM:
        def json(self, *_):
            from ponyguard_viqa.llm import LLMResponse
            return {"entity": "Việt Nam", "missing_requirements": ["requested_attribute"]}, LLMResponse("{}", 1, 1, 1)
    stages = []
    result = PonyGuard(Retriever(), LLM()).run(
        {"sample_id": "ask", "question": "Hiện tại Việt Nam có mấy?", "gold_answers": [], "expected_action": "ASK"},
        progress=lambda stage, _: stages.append(stage),
    )
    assert result["prediction"]["decision"] == "ASK"
    assert result["performance"]["llm_calls"] == 1
    assert stages == ["search", "understand", "evidence", "understand", "decision"]


def test_country_dependent_question_asks_after_evidence_shows_multiple_countries():
    from ponyguard_viqa.core import Chunk
    from ponyguard_viqa.llm import LLMResponse

    class Retriever:
        last_timing = {}
        def retrieve(self, *_):
            return [
                Chunk("us", "us_1", "Ngày 4 tháng 7 là Quốc khánh Hoa Kỳ."),
                Chunk("fr", "fr_1", "Ngày 14 tháng 7 là Quốc khánh Pháp."),
            ]

    class LLM:
        def __init__(self):
            self.outputs = iter([
                {"entity": "Quốc khánh", "requested_attribute": "ngày diễn ra", "answer_type": "DATE", "question_clear": True, "missing_requirements": [], "entity_match": False, "attribute_match": True, "conflict_detected": False, "inference_level": "UNSUPPORTED", "reasoning_allowed": False, "support": []},
                {"decision": "ASK", "entity": "Quốc khánh", "requested_attribute": "ngày diễn ra", "missing_requirements": ["country"], "clarification_question": "Bạn muốn biết Quốc khánh của quốc gia nào?"},
            ])
        def json(self, *_): return next(self.outputs), LLMResponse("{}", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "national-day", "question": "Quốc khánh là ngày mấy?", "gold_answers": [], "expected_action": "ASK"})
    assert result["prediction"]["decision"] == "ASK"
    assert result["prediction"]["answer"] == "Bạn muốn biết Quốc khánh của quốc gia nào?"
    assert result["trace"]["evidence"]["clarification_adjudication"]["decision"] == "ASK"


def test_adjudication_can_ask_for_a_missing_requested_attribute_without_support():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return []

    class LLM:
        def __init__(self):
            self.outputs = iter([
                {"entity": "a subject", "missing_requirements": [], "entity_match": False, "attribute_match": False, "conflict_detected": False, "inference_level": "UNSUPPORTED", "reasoning_allowed": False, "support": []},
                {"decision": "ASK", "entity": "a subject", "missing_requirements": ["requested_attribute"], "clarification_question": "Bạn muốn biết thông tin nào về đối tượng này?"},
            ])
        def json(self, *_): return next(self.outputs), LLMResponse("{}", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "incomplete", "question": "A subject is?", "gold_answers": [], "expected_action": "ASK"})
    assert result["prediction"]["decision"] == "ASK"


def test_invalid_semantic_output_fails_closed_to_abstain_not_an_unverified_ask():
    class Retriever:
        last_timing = {}
        def retrieve(self, *_): return []

    class LLM:
        def __init__(self):
            self.outputs = iter([
                {"_parse_error": True, "support": []},
                {"_parse_error": True},
            ])
        def json(self, *_): return next(self.outputs), LLMResponse("{}", 1, 1, 1)

    result = PonyGuard(Retriever(), LLM()).run({"sample_id": "malformed", "question": "An incomplete request", "gold_answers": [], "expected_action": "ASK"})
    assert result["prediction"]["decision"] == "ABSTAIN"
    assert "output không hợp lệ" in result["prediction"]["answer"]


def test_clarification_writer_replaces_a_generic_fallback_with_a_specific_question():
    class LLM:
        def generate(self, *_):
            return LLMResponse("Bạn muốn biết ngày này của quốc gia nào?", 1, 1, 1)

    requirement = Requirement(missing_requirements=["reference"], clarification_question="Bạn có thể làm rõ đối tượng hoặc thông tin bạn muốn biết không?")
    question, response = PonyGuard(None, LLM()).refine_clarification("Một ngày lễ là gì?", requirement, "Thiếu ngữ cảnh.", {})
    assert response is not None
    assert question == "Bạn muốn biết ngày này của quốc gia nào?"


def test_clarification_writer_rejects_an_incomplete_unanchored_question():
    class LLM:
        def generate(self, *_): return LLMResponse("Bạn muốn biết", 1, 1, 1)

    requirement = Requirement(entity="an entity", missing_requirements=["requested_attribute"])
    question, response = PonyGuard(None, LLM()).refine_clarification("An entity has how many?", requirement, "", {})
    assert response is not None and question == ""


def test_option_already_stated_in_the_question_cancels_the_allegation():
    """A contract offering a choice the question already made is contradicting itself."""
    requirement = Requirement(missing_requirements=["entity"], clarification_options=["Weil der Stadt", "Berlin"], clarification_question="Thành phố nào?")
    guarded = PonyGuard.apply_clarity_guard("Dân số thành phố Weil der Stadt là bao nhiêu?", requirement)
    assert guarded.missing_requirements == []
    assert guarded.question_clear is True


def test_option_absent_from_the_question_keeps_the_allegation():
    requirement = Requirement(missing_requirements=["entity"], clarification_options=["Kepler", "Newton"], clarification_question="Bạn hỏi về ai?")
    guarded = PonyGuard.apply_clarity_guard("Ông ấy sinh năm nào?", requirement)
    assert guarded.missing_requirements == ["entity"]
