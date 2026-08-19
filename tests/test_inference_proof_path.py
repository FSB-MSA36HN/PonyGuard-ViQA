"""Change B: a derived answer is proved arithmetically, not by a relation verdict.

No source states a composed relation, so the verifier's verdict on one carries no
information. These tests pin what replaces it: literal operands, question binding
and recomputed arithmetic — and that DIRECT safety is untouched.
"""
from ponyguard_viqa.core import Chunk
from ponyguard_viqa.llm import LLMResponse
from ponyguard_viqa.pipelines import PonyGuard

CHUNK = Chunk("doc", "doc_1", "Theo điều tra năm 2009, 97,3% dân số biết tiếng Pháp, trong khi 1,1% không có kiến thức về tiếng Pháp.")
QUESTION = "Chênh lệch giữa tỷ lệ biết tiếng Pháp và không có kiến thức tiếng Pháp là bao nhiêu điểm phần trăm?"


def proof(result="96,2", operation="difference", values=("97,3%", "1,1%")):
    return {
        "operation": operation, "result": result, "unit": "%",
        "operands": [
            {"value": values[0], "chunk_id": "doc_1", "evidence_quote": "97,3% dân số biết tiếng Pháp"},
            {"value": values[1], "chunk_id": "doc_1", "evidence_quote": "1,1% không có kiến thức về tiếng Pháp"},
        ],
    }


def support(**overrides):
    return {
        "chunk_id": "doc_1", "support_type": "SIMPLE_INFERENCE",
        "evidence_quote": "97,3% dân số biết tiếng Pháp", "candidate_answer": "96,2%",
        "inference_proof": proof(), **overrides,
    }


def test_a_valid_proof_survives_a_contradicted_verdict_on_the_composed_relation():
    """The regression this change exists for: the composed relation is unstateable."""
    rejected_by_verifier = support(premise_status="CONTRADICTED", relation_match=False, attribute_match=False)
    valid, rejections = PonyGuard.validated_supports(
        {"support": [rejected_by_verifier]}, [CHUNK], QUESTION, strict_relation=True, expected_entity="tỷ lệ biết tiếng Pháp",
    )
    assert len(valid) == 1 and not rejections


def test_arithmetic_that_does_not_recompute_is_rejected():
    valid, rejections = PonyGuard.validated_supports(
        {"support": [support(inference_proof=proof(result="42"))]}, [CHUNK], QUESTION, strict_relation=True,
    )
    assert not valid and "Inference proof" in rejections[0]


def test_an_operand_quote_absent_from_its_chunk_is_rejected():
    fabricated = proof()
    fabricated["operands"][1]["evidence_quote"] = "một con số không có trong nguồn"
    valid, rejections = PonyGuard.validated_supports(
        {"support": [support(inference_proof=fabricated)]}, [CHUNK], QUESTION, strict_relation=True,
    )
    assert not valid and "Inference proof" in rejections[0]


def test_an_operand_value_absent_from_its_own_quote_is_rejected():
    mismatched = proof(values=("55,5%", "1,1%"))
    valid, rejections = PonyGuard.validated_supports(
        {"support": [support(inference_proof=mismatched)]}, [CHUNK], QUESTION, strict_relation=True,
    )
    assert not valid and "Inference proof" in rejections[0]


def test_an_unsupported_join_of_unrelated_numbers_is_rejected():
    """Two real numbers from a real chunk are not a proof if the question is not about them."""
    unrelated = Chunk("other", "doc_2", "Đội bóng ghi 7 bàn thắng và nhận 3 thẻ vàng trong mùa giải.")
    join = {
        "operation": "difference", "result": "4", "unit": "",
        "operands": [
            {"value": "7", "chunk_id": "doc_2", "evidence_quote": "7 bàn thắng"},
            {"value": "3", "chunk_id": "doc_2", "evidence_quote": "3 thẻ vàng"},
        ],
    }
    valid, rejections = PonyGuard.validated_supports(
        {"support": [support(chunk_id="doc_2", evidence_quote="7 bàn thắng", inference_proof=join)]},
        [unrelated], QUESTION, strict_relation=True,
    )
    assert not valid and "Inference proof" in rejections[0]


def test_a_missing_or_malformed_proof_is_rejected():
    for broken in ({}, {"operation": "exponent", "operands": [], "result": "1"}, {"operation": "sum", "operands": [{}], "result": "1"}):
        valid, _ = PonyGuard.validated_supports(
            {"support": [support(inference_proof=broken)]}, [CHUNK], QUESTION, strict_relation=True,
        )
        assert not valid


def test_direct_support_still_requires_a_matching_relation_verdict():
    """Change B must not open the DIRECT path it does not touch."""
    reversed_actor = {
        "chunk_id": "doc_1", "support_type": "DIRECT",
        "evidence_quote": "97,3% dân số biết tiếng Pháp", "candidate_answer": "97,3%",
        "premise_status": "CONTRADICTED", "relation_match": False, "attribute_match": False,
    }
    valid, rejections = PonyGuard.validated_supports(
        {"support": [reversed_actor]}, [CHUNK], QUESTION, strict_relation=True,
    )
    assert not valid and "contradicted" in rejections[0].lower()


def test_inference_candidates_are_not_sent_to_the_relation_verifier():
    """The useless call on a composed relation is removed, not merely ignored."""
    class LLM:
        def json(self, *_):
            raise AssertionError("a composed relation must not be sent for a verdict")

    assert PonyGuard(None, LLM()).verify_relations(QUESTION, None, {"support": [support()]}, [CHUNK], {}) is None


def test_direct_candidates_are_still_verified():
    seen = {}

    class LLM:
        def json(self, request, *_):
            seen["request"] = request
            return {"verdicts": [{"chunk_id": "doc_1", "verdict": "MATCH"}]}, LLMResponse("{}", 1, 1, 1)

    from ponyguard_viqa.core import Requirement
    evidence = {"support": [{"chunk_id": "doc_1", "support_type": "DIRECT", "evidence_quote": "97,3% dân số biết tiếng Pháp", "candidate_answer": "97,3%"}]}
    assert PonyGuard(None, LLM()).verify_relations(QUESTION, Requirement(), evidence, [CHUNK], {}) is not None
    assert evidence["support"][0]["premise_status"] == "SUPPORTED"
