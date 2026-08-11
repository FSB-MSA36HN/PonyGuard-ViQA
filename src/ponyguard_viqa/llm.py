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


class LocalLLM:
    """Small direct MLX adapter; mock mode keeps tests and smoke runs offline."""
    def __init__(self, model: str, backend: str = "mlx", max_tokens: int = 256):
        self.model_name, self.backend, self.max_tokens = model, backend, max_tokens
        self._model = self._tokenizer = None

    def generate(self, prompt: str) -> LLMResponse:
        started = perf_counter()
        if self.backend == "mock":
            text = self._mock(prompt)
        else:
            try:
                from mlx_lm import generate, load
                if self._model is None: self._model, self._tokenizer = load(self.model_name)
                messages = [
                    {"role": "system", "content": "Bạn là trợ lý tiếng Việt. Luôn trả lời bằng tiếng Việt có dấu. Không dùng tiếng Trung hoặc tiếng Anh trong phần nội dung tự nhiên; chỉ giữ nguyên JSON keys và nhãn kỹ thuật khi được yêu cầu."},
                    {"role": "user", "content": prompt},
                ]
                rendered = self._tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                text = generate(self._model, self._tokenizer, prompt=rendered, max_tokens=self.max_tokens, verbose=False)
            except ImportError as error:
                raise RuntimeError("mlx-lm is unavailable. Use backend: mock for tests or run bootstrap on Apple Silicon.") from error
        return LLMResponse(text.strip(), len(prompt.split()), len(text.split()), (perf_counter()-started)*1000)

    def json(self, prompt: str) -> tuple[dict[str, Any], LLMResponse]:
        response = self.generate(prompt + "\nReturn ONLY a JSON object.")
        try:
            return self._extract_json(response.text), response
        except ValueError:
            repaired = self.generate("Sửa nội dung sau thành MỘT JSON object hợp lệ. Không thêm giải thích, markdown hoặc text khác.\n\n" + response.text)
            try:
                value = self._extract_json(repaired.text)
            except ValueError as error:
                raise ValueError(f"Model returned invalid JSON after one repair attempt: {repaired.text[:200]}") from error
            return value, LLMResponse(repaired.text, response.input_tokens + repaired.input_tokens, response.output_tokens + repaired.output_tokens, response.latency_ms + repaired.latency_ms)

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
        if "question_clear" in prompt:
            unclear = bool(re.search(r"(?:Ông ấy|Bà ấy|Người này|nó)\b", prompt, re.I))
            return json.dumps({"entity": None if unclear else "question entity", "requested_attribute": "requested fact", "answer_type": "text", "question_clear": not unclear, "missing_requirements": ["entity"] if unclear else [], "clarification_question": "Bạn đang hỏi năm sinh của ai?" if unclear else ""})
        if "decision là ANSWER" in prompt:
            return json.dumps({"decision": "ABSTAIN", "answer": "Tài liệu không đủ bằng chứng."})
        if "evidence_sufficient" in prompt:
            return json.dumps({"entity_match": True, "attribute_match": True, "evidence_found": True, "evidence_sufficient": True, "conflict_detected": False, "supporting_chunk_ids": ["chunk_000001"], "missing_evidence": [], "inference_level": "DIRECT", "reasoning_allowed": True})
        if "claims" in prompt:
            return json.dumps({"claims": [{"claim_id": "c1", "text": "Mock answer.", "label": "SUPPORTED", "evidence_chunk_ids": ["chunk_000001"]}]})
        return "Mock answer."
