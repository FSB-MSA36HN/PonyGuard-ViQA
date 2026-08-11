from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    calls: int = 1
    model_load_ms: float = 0.0


class LocalLLM:
    """Small direct MLX adapter; mock mode keeps tests and smoke runs offline."""
    def __init__(self, model: str, backend: str = "mlx", max_tokens: int = 256):
        self.model_name, self.backend, self.max_tokens = model, backend, max_tokens
        self._model = self._tokenizer = None

    def generate(self, prompt: str, max_tokens: int | None = None) -> LLMResponse:
        started = perf_counter()
        model_load_ms = 0.0
        if self.backend == "mock":
            text = self._mock(prompt)
        else:
            try:
                from mlx_lm import generate, load
                if self._model is None:
                    loaded = perf_counter(); self._model, self._tokenizer = load(self.model_name); model_load_ms = (perf_counter()-loaded)*1000
                messages = [
                    {"role": "system", "content": "Bạn là trợ lý tiếng Việt. Luôn trả lời bằng tiếng Việt có dấu. Không dùng tiếng Trung hoặc tiếng Anh trong phần nội dung tự nhiên; chỉ giữ nguyên JSON keys và nhãn kỹ thuật khi được yêu cầu."},
                    {"role": "user", "content": prompt},
                ]
                rendered = self._tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                text = generate(self._model, self._tokenizer, prompt=rendered, max_tokens=max_tokens or self.max_tokens, verbose=False)
            except ImportError as error:
                raise RuntimeError("mlx-lm is unavailable. Use backend: mock for tests or run bootstrap on Apple Silicon.") from error
        return LLMResponse(text.strip(), len(prompt.split()), len(text.split()), (perf_counter()-started)*1000, model_load_ms=model_load_ms)

    def json(self, prompt: str, max_tokens: int | None = None) -> tuple[dict[str, Any], LLMResponse]:
        response = self.generate(prompt + "\nReturn ONLY a JSON object.") if max_tokens is None else self.generate(prompt + "\nReturn ONLY a JSON object.", max_tokens)
        try:
            return self._extract_json(response.text), response
        except ValueError:
            repair_prompt = "Sửa nội dung sau thành MỘT JSON object hợp lệ. Không thêm giải thích, markdown hoặc text khác.\n\n" + response.text
            repair_tokens = max(max_tokens or self.max_tokens, 256)
            repaired = self.generate(repair_prompt, repair_tokens)
            try:
                value = self._extract_json(repaired.text)
            except ValueError:
                # ponytail: fail closed; add a constrained decoder only if malformed JSON remains frequent after profiling.
                return {"_parse_error": True}, LLMResponse(repaired.text, response.input_tokens + repaired.input_tokens, response.output_tokens + repaired.output_tokens, response.latency_ms + repaired.latency_ms, response.calls + repaired.calls, response.model_load_ms + repaired.model_load_ms)
            return value, LLMResponse(repaired.text, response.input_tokens + repaired.input_tokens, response.output_tokens + repaired.output_tokens, response.latency_ms + repaired.latency_ms, response.calls + repaired.calls, response.model_load_ms + repaired.model_load_ms)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Parse the first complete JSON object without regex greediness."""
        decoder = json.JSONDecoder()
        for offset, character in enumerate(text):
            if character != "{": continue
            try:
                value, _ = decoder.raw_decode(text[offset:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict): return value
        raise ValueError("Model did not return a complete JSON object")

    @staticmethod
    def _mock(prompt: str) -> str:
        """Deterministic minimal test backend, deliberately not benchmark-capable."""
        if prompt.lstrip().startswith("Phân tích câu hỏi") or prompt.lstrip().startswith("question_clear"):
            unclear = bool(re.search(r"(?:Ông ấy|Bà ấy|Người này|nó)\b", prompt, re.I))
            return json.dumps({"entity": None if unclear else "question entity", "requested_attribute": "requested fact", "answer_type": "text", "question_clear": not unclear, "missing_requirements": ["entity"] if unclear else [], "clarification_question": "Bạn đang hỏi năm sinh của ai?" if unclear else ""})
        match = re.search(r"\[([A-Za-z0-9_]+)\]\s+(.+)", prompt, re.S)
        if "support là mảng" in prompt:
            if not match: return json.dumps({"entity_match": False, "attribute_match": False, "conflict_detected": False, "inference_level": "UNSUPPORTED", "reasoning_allowed": False, "support": []})
            chunk_id, quote = match.group(1), match.group(2).split("\nReturn ONLY", 1)[0].strip().split("\n\n", 1)[0]
            return json.dumps({"entity_match": True, "attribute_match": True, "conflict_detected": False, "inference_level": "DIRECT", "reasoning_allowed": True, "support": [{"chunk_id": chunk_id, "evidence_quote": quote, "candidate_answer": quote, "support_type": "DIRECT"}]})
        if "claims" in prompt:
            return json.dumps({"claims": [{"claim_id": "c1", "text": "Mock answer.", "label": "SUPPORTED", "evidence_chunk_ids": ["chunk_000001"]}]})
        if "citation_chunk_ids" in prompt and match:
            chunk_id, quote = match.group(1), match.group(2).split("\nReturn ONLY", 1)[0].strip().split("\n\n", 1)[0]
            decision = "ANSWER" if '"decision":"ANSWER|ABSTAIN"' in prompt else None
            value = {"answer": quote, "citation_chunk_ids": [chunk_id], "evidence_quote": quote}
            if decision: value["decision"] = decision
            return json.dumps(value)
        return "Mock answer."
