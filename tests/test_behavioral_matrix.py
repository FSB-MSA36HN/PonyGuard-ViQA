"""Deterministic behavioural contract matrix; no network, model download, or frozen benchmark writes."""
from __future__ import annotations

import pytest

from ponyguard_viqa.core import Chunk, Requirement, add_clarification
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard, PromptSafeRAG


DIRECT = {"entity_match": True, "attribute_match": True, "valid_supports": [{"chunk_id": "source"}], "conflict_detected": False, "reasoning_allowed": True, "inference_level": "DIRECT"}


@pytest.mark.parametrize(
    ("case", "requirement", "evidence", "expected"),
    [
        ("direct evidence", Requirement(entity="subject", requested_attribute="fact"), DIRECT, "ANSWER"),
        ("simple inference", Requirement(entity="subject", requested_attribute="fact"), {**DIRECT, "inference_level": "SIMPLE_INFERENCE"}, "ANSWER"),
        ("missing entity", Requirement(requested_attribute="fact", missing_requirements=["entity"]), {}, "ASK"),
        ("missing requested attribute", Requirement(entity="subject", missing_requirements=["requested_attribute"]), {}, "ASK"),
        ("missing country", Requirement(entity="subject", requested_attribute="date", missing_requirements=["country"]), {}, "ASK"),
        ("missing location", Requirement(entity="subject", requested_attribute="fact", missing_requirements=["location"]), {}, "ASK"),
        ("missing time", Requirement(entity="subject", requested_attribute="fact", missing_requirements=["time"]), {}, "ASK"),
        ("missing scope", Requirement(entity="subject", requested_attribute="count", missing_requirements=["scope"]), {}, "ASK"),
        ("missing referent", Requirement(requested_attribute="fact", missing_requirements=["reference"]), {}, "ASK"),
        ("missing target", Requirement(requested_attribute="fact", missing_requirements=["target"]), {}, "ASK"),
        ("no evidence", Requirement(entity="subject", requested_attribute="fact"), {"entity_match": True, "attribute_match": True, "valid_supports": [], "reasoning_allowed": True, "inference_level": "DIRECT"}, "ABSTAIN"),
        ("entity mismatch", Requirement(entity="subject", requested_attribute="fact"), {**DIRECT, "entity_match": False}, "ABSTAIN"),
        ("conflicting facts", Requirement(entity="subject", requested_attribute="fact"), {**DIRECT, "conflict_detected": True}, "ABSTAIN"),
        ("unsupported inference", Requirement(entity="subject", requested_attribute="fact"), {**DIRECT, "reasoning_allowed": False, "inference_level": "UNSUPPORTED"}, "ABSTAIN"),
        ("unmatched time scope", Requirement(entity="subject", requested_attribute="fact", time_scope="CURRENT"), {**DIRECT, "valid_supports": [{"chunk_id": "source", "matches_time": False, "matches_population": True}]}, "ABSTAIN"),
    ],
)
def test_decision_policy_matrix(case, requirement, evidence, expected):
    assert PonyGuard.decide(requirement, evidence) == expected


@pytest.mark.parametrize("slot", ["entity", "requested_attribute", "country", "location", "time", "scope", "reference", "target"])
def test_every_ask_slot_has_a_nonempty_question_and_can_be_resolved(slot):
    requirement = Requirement(entity="subject", requested_attribute="fact", missing_requirements=[slot])
    if slot == "entity":
        requirement.entity = None
    if slot == "requested_attribute":
        requirement.requested_attribute = None
    question = PonyGuard.clarification_question(requirement, "A terse user question")
    assert question.strip()
    resolved = PonyGuard.apply_user_clarification(add_clarification("A terse user question", "A relevant clarification"), requirement, [slot])
    assert not resolved.missing_requirements


class Retriever:
    last_timing = {}
    def __init__(self, chunks): self.chunks = chunks; self.queries = []
    def retrieve(self, question, *_): self.queries.append(question); return self.chunks


class ScriptedLLM:
    def __init__(self, outputs): self.outputs = iter(outputs)
    def json(self, *_): return next(self.outputs), LLMResponse("{}", 1, 1, 1)


def test_simple_inference_pipeline_answers_only_after_grounding_and_claim_verification():
    source = Chunk("source", "source", "The ledger identifies subject with values 5 and 0; their difference is 5.")
    llm = ScriptedLLM([
        {"entity": "subject", "requested_attribute": "verified total", "question_clear": True, "entity_match": True, "attribute_match": True, "conflict_detected": False, "reasoning_allowed": True, "inference_level": "SIMPLE_INFERENCE", "support": [{"chunk_id": "source", "evidence_quote": "The ledger identifies subject with values 5 and 0; their difference is 5.", "candidate_answer": "5", "support_type": "SIMPLE_INFERENCE", "question_entity_quote": "subject", "evidence_entity_quote": "subject", "inference_proof": {"operation": "difference", "operands": [{"value": "5", "chunk_id": "source", "evidence_quote": "The ledger identifies subject with values 5 and 0; their difference is 5."}, {"value": "0", "chunk_id": "source", "evidence_quote": "The ledger identifies subject with values 5 and 0; their difference is 5."}], "result": "5"}}]},
        {"answer": "5", "citation_chunk_ids": ["source"], "evidence_quote": "The ledger identifies subject with values 5 and 0; their difference is 5."},
        {"claims": [{"text": "5", "label": "INFERRED_SUPPORTED", "evidence_chunk_ids": ["source"]}]},
    ])
    retriever = Retriever([source])
    result = PonyGuard(retriever, llm).run({"sample_id": "simple-inference", "question": "What is subject's verified total?", "gold_answers": ["5"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert result["prediction"]["grounding"]["valid"]
    assert retriever.queries == ["What is subject's verified total?"]


@pytest.mark.parametrize("pipeline_type", [BasicRAG, PromptSafeRAG])
def test_baselines_share_the_same_grounded_answer_contract(pipeline_type):
    source = Chunk("source", "source", "A source states the requested value is 5.")
    answer = {"answer": "5", "citation_chunk_ids": ["source"], "evidence_quote": "A source states the requested value is 5."}
    if pipeline_type is PromptSafeRAG:
        answer["decision"] = "ANSWER"
    result = pipeline_type(Retriever([source]), ScriptedLLM([answer])).run({"sample_id": "baseline", "question": "What is the requested value?", "gold_answers": ["5"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert result["prediction"]["grounding"]["citation_chunk_ids"] == ["source"]


def test_component_counts_produce_a_grounded_abstain_explanation_not_a_fake_total():
    source = Chunk("counts", "counts", "Subject has 3 groups, 12 birds, and 8 mammals.")
    evidence = {"chunk_id": "counts", "evidence_quote": "Subject has 8 mammals", "candidate_answer": "8", "valid_supports": []}
    observations = PonyGuard.validated_observations(evidence, [source])
    refusal = PonyGuard.grounded_refusal(Requirement(entity="subject", requested_attribute="total count"), {"valid_supports": [], "valid_observations": observations})
    assert "nhiều số liệu riêng" in refusal["text"]
    assert "8 mammals" in refusal["text"]


def test_intent_first_production_path_skips_recovery_for_clear_direct_evidence():
    source = Chunk("source", "source", "Subject has a verified value of 5.")
    llm = ScriptedLLM([
        {"entity": "Subject", "requested_attribute": "verified value", "question_complete": True, "missing_requirements": []},
        {"entity_match": True, "attribute_match": True, "reasoning_allowed": True, "inference_level": "DIRECT", "support": [{"chunk_id": "source", "evidence_quote": source.text, "candidate_answer": "5", "support_type": "DIRECT", "question_entity_quote": "Subject", "evidence_entity_quote": "Subject", "question_relation": "verified value", "evidence_relation": "verified value", "relation_match": True, "premise_status": "SUPPORTED"}]},
        {"verdicts": [{"chunk_id": "source", "verdict": "MATCH"}]},
        {"answer": "5", "citation_chunk_ids": ["source"], "evidence_quote": source.text},
        {"claims": [{"text": "5", "label": "SUPPORTED", "evidence_chunk_ids": ["source"]}]},
    ])
    result = PonyGuard(Retriever([source]), llm, intent_first=True).run({"sample_id": "fast-path", "question": "What is Subject's verified value?", "gold_answers": ["5"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert "evidence_recovery" not in result["performance"]["stages"]
    assert "clarification_adjudication" not in result["performance"]["stages"]


def test_intent_first_recovers_one_fact_after_initial_extraction_failure():
    source = Chunk("source", "source", "Subject has a verified value of 5.")
    llm = ScriptedLLM([
        {"entity": "Subject", "requested_attribute": "verified value", "question_complete": True, "missing_requirements": []},
        {"_parse_error": True},
        {"support": [{"chunk_id": "source", "evidence_quote": source.text, "candidate_answer": "5", "support_type": "DIRECT"}]},
        {"verdicts": [{"chunk_id": "source", "verdict": "MATCH"}]},
        {"question": {"subject": "Subject"}, "source": {"subject": "Subject", "object": "verified value of 5"}},
    ])
    result = PonyGuard(Retriever([source]), llm, intent_first=True).run({"sample_id": "recovery", "question": "What is Subject's verified value?", "gold_answers": ["5"], "expected_action": "ANSWER"})
    assert result["prediction"]["decision"] == "ANSWER"
    assert result["prediction"]["grounding"]["valid"]
    assert "fact_recovery" in result["performance"]["stages"]
