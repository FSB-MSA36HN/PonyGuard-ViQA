from ponyguard_viqa.core import Chunk, Requirement, add_clarification, resolved_question, stable_hash
from ponyguard_viqa.data import clarification_set, stratified_splits
from ponyguard_viqa.evaluation import metrics
from ponyguard_viqa.pipelines import PonyGuard
from ponyguard_viqa.llm import FallbackLLM, GeminiLLM, LLMResponse, LocalLLM, ProviderQuotaError

def row(number, action):
    return {"sample_id": str(number), "question": f"Question {number} text here", "context": "context", "gold_answers": ["a"], "is_answerable": action == "ANSWER", "expected_action": action, "source": "test"}

def test_splits_are_stratified_and_deterministic():
    rows = [row(i, "ANSWER" if i % 2 else "ABSTAIN") for i in range(6000)]
    first, second = stratified_splits(rows), stratified_splits(rows)
    assert [r["sample_id"] for r in first["test"]] == [r["sample_id"] for r in second["test"]]
    assert len(first["test"]) == 2000
    assert {r["expected_action"] for r in first["test"]} == {"ANSWER", "ABSTAIN"}

def test_clarification_is_separate_ask_data():
    data = clarification_set([row(1, "ANSWER")])
    assert data[0]["expected_action"] == "ASK" and data[0]["missing_requirement"] == "entity"

def test_decision_gate():
    clear = Requirement(entity="x", requested_attribute="y", question_clear=True)
    assert PonyGuard.decide(Requirement(question_clear=False, missing_requirements=["entity"]), {}) == "ASK"
    assert PonyGuard.decide(clear, {"entity_match": True, "attribute_match": True, "evidence_sufficient": False}) == "ABSTAIN"
    assert PonyGuard.decide(clear, {"entity_match": True, "attribute_match": True, "valid_supports": [{"chunk_id": "x"}], "reasoning_allowed": True, "inference_level": "DIRECT"}) == "ANSWER"
    assert PonyGuard.decide(clear, {"entity_match": True, "attribute_match": True, "valid_supports": [{"chunk_id": "x"}], "reasoning_allowed": False, "inference_level": "UNSUPPORTED"}) == "ABSTAIN"

def test_stable_hash_changes_with_ids():
    assert stable_hash(["a"]) != stable_hash(["b"])

def test_clarification_extends_request_without_claiming_evidence():
    merged = add_clarification("Ông ấy sinh năm bao nhiêu?", "Ông ấy là Albert Einstein.")
    assert merged.startswith("Ông ấy sinh năm bao nhiêu?") and "Thông tin làm rõ từ người dùng" in merged

def test_complete_follow_up_question_replaces_an_incomplete_turn_but_short_context_does_not():
    assert resolved_question(add_clarification("Con lợn có?", "Con lợn có mấy chân?")) == "Con lợn có mấy chân?"
    assert "Mỹ" in resolved_question(add_clarification("Quốc khánh là ngày nào?", "Mỹ"))

def test_selected_spelling_replaces_the_matching_unaccented_phrase():
    assert resolved_question(add_clarification("Bào đốm là con gì?", "Báo đốm")) == "Báo đốm là con gì?"

def test_claim_final_gate_removes_unsupported_or_abstains():
    claims = [{"text": "Đúng.", "label": "SUPPORTED"}, {"text": "Sai.", "label": "UNSUPPORTED"}]
    assert PonyGuard.final_gate(claims, "Đúng. Sai.") == ("ANSWER", "Đúng.")
    assert PonyGuard.final_gate([{"text": "Sai.", "label": "CONTRADICTED"}], "Sai.")[0] == "ABSTAIN"
    assert PonyGuard.final_gate([], "Không kiểm chứng được.")[0] == "ABSTAIN"

def test_mock_requirement_analyzer_detects_missing_entity():
    value, _ = LocalLLM("mock", backend="mock").json("question_clear\nQuestion: Ông ấy sinh năm bao nhiêu?")
    assert value["question_clear"] is False and value["missing_requirements"] == ["entity"]

def test_ask_question_is_specific_to_the_missing_requirement():
    requirement = Requirement(requested_attribute="năm sinh", question_clear=False, missing_requirements=["entity"])
    assert PonyGuard.clarification_question(requirement) == "Bạn đang hỏi năm sinh của ai hoặc đối tượng nào?"
    generated = Requirement(question_clear=False, clarification_question="Bạn đang hỏi năm sinh của ai?")
    assert PonyGuard.clarification_question(generated) == "Bạn đang hỏi năm sinh của ai?"

def test_requirement_contract_rejects_unknown_slots():
    requirement = PonyGuard.apply_clarity_guard("Any question", Requirement(missing_requirements=["unknown", "country"]))
    assert requirement.missing_requirements == ["country"]

def test_clear_question_overrides_bad_llm_clarity_and_answers_with_direct_evidence():
    question = "Việt Nam có bao nhiêu loài thực vật?"
    bad_llm_requirement = Requirement(question_clear=False, missing_requirements=["entity"], clarification_question='Có phải bạn đang muốn hỏi "Việt Nam có bao nhiêu loài thực vật?"?')
    requirement = PonyGuard.apply_clarity_guard(question, bad_llm_requirement)
    evidence = {"entity_match": True, "attribute_match": True, "valid_supports": [{"chunk_id": "doc_003879_chunk_000001"}], "conflict_detected": False, "inference_level": "DIRECT", "reasoning_allowed": True, "decision_rationale": "Chunk nêu trực tiếp 15.986 loài thực vật."}
    requirement = PonyGuard.resolve_missing_with_evidence(requirement, evidence)
    assert requirement.question_clear and not requirement.missing_requirements
    assert PonyGuard.decide(requirement, evidence) == "ANSWER"
    assert "15.986" in PonyGuard.decision_rationale(requirement, evidence, "ANSWER")

def test_clear_question_without_evidence_abstains_not_asks():
    requirement = PonyGuard.apply_clarity_guard("Việt Nam có bao nhiêu loài thực vật?", Requirement())
    evidence = {"entity_match": False, "attribute_match": False, "evidence_sufficient": False, "conflict_detected": False, "inference_level": "UNSUPPORTED", "reasoning_allowed": False, "missing_evidence": ["số loài thực vật ở Việt Nam"]}
    assert PonyGuard.decide(requirement, evidence) == "ABSTAIN"

def test_conflicting_evidence_abstains():
    requirement = Requirement(entity="Việt Nam", requested_attribute="số loài thực vật")
    evidence = {"entity_match": True, "attribute_match": True, "evidence_sufficient": True, "conflict_detected": True, "inference_level": "DIRECT", "reasoning_allowed": True}
    assert PonyGuard.decide(requirement, evidence) == "ABSTAIN"

def test_repeated_clarification_is_replaced_with_specific_fallback():
    requirement = Requirement(requested_attribute="năm sinh", missing_requirements=["entity"], clarification_question='Có phải bạn đang hỏi "Ông ấy sinh năm bao nhiêu?"?')
    assert PonyGuard.clarification_question(requirement, "Ông ấy sinh năm bao nhiêu?") == "Bạn đang hỏi năm sinh của ai hoặc đối tượng nào?"

def test_ask_metrics_separate_false_and_meaningful_asks():
    rows = [
        {"gold": {"expected_action": "ANSWER", "answers": []}, "prediction": {"decision": "ASK", "answer": ""}, "performance": {"latency_ms": 1, "input_tokens": 1, "output_tokens": 1, "llm_calls": 1}},
        {"gold": {"expected_action": "ASK", "answers": []}, "prediction": {"decision": "ASK", "answer": ""}, "performance": {"latency_ms": 1, "input_tokens": 1, "output_tokens": 1, "llm_calls": 1}},
    ]
    result = metrics(rows)
    assert result["false_ask_rate"] == 1 and result["meaningful_ask_rate"] == .5 and result["ask_recall"] == 1

def test_vietnam_plants_regression_answers_despite_bad_requirement_label():
    class RetrieverStub:
        def retrieve(self, *_): return [Chunk("doc_003879", "doc_003879_chunk_000001", "Việt Nam có 15.986 loài thực vật.")]
    class LLMStub:
        def __init__(self): self.outputs = iter([
                {"entity": None, "requested_attribute": "số loài thực vật", "question_clear": False, "missing_requirements": ["entity"], "clarification_question": 'Có phải bạn đang muốn hỏi "Việt Nam có bao nhiêu loài thực vật?"?', "entity_match": True, "attribute_match": True, "conflict_detected": False, "inference_level": "DIRECT", "reasoning_allowed": True, "decision_rationale": "Chunk nêu trực tiếp 15.986 loài thực vật.", "support": [{"chunk_id": "doc_003879_chunk_000001", "evidence_quote": "Việt Nam có 15.986 loài thực vật.", "candidate_answer": "15.986 loài thực vật", "support_type": "DIRECT", "question_entity_quote": "Việt Nam", "evidence_entity_quote": "Việt Nam"}]},
            {"answer": "15.986 loài thực vật", "citation_chunk_ids": ["doc_003879_chunk_000001"], "evidence_quote": "Việt Nam có 15.986 loài thực vật."},
            {"claims": [{"claim_id": "c1", "text": "Việt Nam có 15.986 loài thực vật.", "label": "SUPPORTED", "evidence_chunk_ids": ["doc_003879_chunk_000001"]}]},
        ])
        def json(self, *_): return next(self.outputs), LLMResponse("{}", 1, 1, 1)
        def generate(self, *_): return LLMResponse("Việt Nam có 15.986 loài thực vật.", 1, 1, 1)
    result = PonyGuard(RetrieverStub(), LLMStub()).run({"sample_id": "plants", "question": "Việt Nam có bao nhiêu loài thực vật?", "gold_answers": ["15.986 loài thực vật"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert "15.986" in result["prediction"]["answer"]

def test_json_parser_handles_fenced_json_and_repairs_malformed_output():
    assert LocalLLM._extract_json("```json\n{\"ok\": true}\n```") == {"ok": True}
    llm = LocalLLM("mock", backend="mock")
    outputs = iter(["{\"broken\": true", "{\"repaired\": true}"])
    llm.generate = lambda *_: LLMResponse(next(outputs), 1, 1, 1)  # type: ignore[method-assign]
    value, response = llm.json("anything")
    assert value == {"repaired": True} and response.calls == 2

def test_json_parser_fails_closed_after_two_malformed_outputs():
    llm = LocalLLM("mock", backend="mock")
    llm.generate = lambda *_: LLMResponse("{broken", 1, 1, 1)  # type: ignore[method-assign]
    value, response = llm.json("anything", 80)
    assert value == {"_parse_error": True} and response.calls == 2


def test_temporary_provider_error_falls_back_to_local_but_other_errors_do_not():
    class Primary:
        model_name = "gemini-test"
        max_tokens = 8
        def generate(self, *_): raise ProviderQuotaError("Gemini temporarily unavailable (503)")
    class Fallback:
        def generate(self, *_): return LLMResponse("local", 1, 1, 1, provider="local", model="local-test")
    response = FallbackLLM(Primary(), Fallback()).generate("test")
    assert response.text == "local" and response.fallback_reason == "Gemini temporarily unavailable (503)"


def test_gemini_uses_json_mime_type_for_structured_requests(monkeypatch):
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"candidates":[{"content":{"parts":[{"text":"{}"}]}}]}'
    def request(*args, **kwargs):
        captured["body"] = __import__("json").loads(args[0].data)
        return Response()
    monkeypatch.setattr("ponyguard_viqa.llm.urlopen", request)
    GeminiLLM("gemini-test", "key").generate("Return ONLY a JSON object.")
    assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_max_tokens_without_text_is_repaired_by_the_json_layer(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"candidates":[{"finishReason":"MAX_TOKENS"}]}'
    monkeypatch.setattr("ponyguard_viqa.llm.urlopen", lambda *_args, **_kwargs: Response())
    response = GeminiLLM("gemini-test", "key").generate("Return ONLY a JSON object.")
    assert response.text == ""
