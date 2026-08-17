from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    calls: int = 1
    model_load_ms: float = 0.0
    provider: str = "local"
    model: str = ""
    fallback_reason: str = ""


class ProviderQuotaError(RuntimeError):
    """A provider is temporarily unavailable, so automatic fallback is allowed."""


def gemini_api_key() -> str:
    """Read a local .env key without requiring another dependency or exposing it."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "GEMINI_API_KEY":
            return value.strip().strip("'\"")
    return ""


def list_gemini_models(api_key: str | None = None) -> list[str]:
    """Return only models this API key says can generate text."""
    api_key = api_key or gemini_api_key()
    if not api_key:
        return []
    url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"
    request = Request(url, headers={"x-goog-api-key": api_key})
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []
    return sorted(
        model["name"].removeprefix("models/")
        for model in payload.get("models", [])
        if "generateContent" in model.get("supportedGenerationMethods", [])
    )


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
                try:
                    rendered = self._tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                except TypeError:
                    rendered = self._tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                text = generate(self._model, self._tokenizer, prompt=rendered, max_tokens=max_tokens or self.max_tokens, verbose=False)
            except ImportError as error:
                raise RuntimeError("mlx-lm is unavailable. Use backend: mock for tests or run bootstrap on Apple Silicon.") from error
        return LLMResponse(text.strip(), len(prompt.split()), len(text.split()), (perf_counter()-started)*1000, model_load_ms=model_load_ms, provider="local", model=self.model_name)

    def json(self, prompt: str, max_tokens: int | None = None) -> tuple[dict[str, Any], LLMResponse]:
        response = self.generate(prompt + "\nReturn ONLY a JSON object.") if max_tokens is None else self.generate(prompt + "\nReturn ONLY a JSON object.", max_tokens)
        try:
            return self._extract_json(response.text), response
        except ValueError:
            repair_prompt = "Trả về MỘT JSON object hợp lệ cho yêu cầu gốc sau. Không thêm giải thích, markdown hoặc text khác.\n\nYêu cầu gốc:\n" + prompt + "\n\nOutput không hợp lệ cần thay thế:\n" + response.text
            repair_tokens = max(max_tokens or self.max_tokens, 256)
            repaired = self.generate(repair_prompt, repair_tokens)
            try:
                value = self._extract_json(repaired.text)
            except ValueError:
                # ponytail: fail closed; add a constrained decoder only if malformed JSON remains frequent after profiling.
                return {"_parse_error": True}, LLMResponse(repaired.text, response.input_tokens + repaired.input_tokens, response.output_tokens + repaired.output_tokens, response.latency_ms + repaired.latency_ms, response.calls + repaired.calls, response.model_load_ms + repaired.model_load_ms, repaired.provider, repaired.model, repaired.fallback_reason)
            return value, LLMResponse(repaired.text, response.input_tokens + repaired.input_tokens, response.output_tokens + repaired.output_tokens, response.latency_ms + repaired.latency_ms, response.calls + repaired.calls, response.model_load_ms + repaired.model_load_ms, repaired.provider, repaired.model, repaired.fallback_reason)

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


class GeminiLLM(LocalLLM):
    """Gemini REST adapter using the models exposed to the configured API key."""
    def __init__(self, model: str, api_key: str, max_tokens: int = 256):
        super().__init__(model, "gemini", max_tokens)
        self.api_key = api_key

    def generate(self, prompt: str, max_tokens: int | None = None) -> LLMResponse:
        started = perf_counter()
        model = self.model_name.removeprefix("models/")
        generation_config = {"temperature": 0, "maxOutputTokens": max_tokens or self.max_tokens}
        if "JSON object" in prompt:
            generation_config["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": "Bạn là trợ lý tiếng Việt. Luôn trả lời bằng tiếng Việt có dấu; chỉ giữ JSON keys và nhãn kỹ thuật khi được yêu cầu."}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='-_.')}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code in {429, 500, 502, 503, 504} or "RESOURCE_EXHAUSTED" in detail:
                raise ProviderQuotaError(f"Gemini temporarily unavailable ({error.code})") from error
            raise RuntimeError(f"Gemini request failed ({error.code}): {detail[:300]}") from error
        except (URLError, TimeoutError) as error:
            raise ProviderQuotaError(f"Gemini network unavailable: {error}") from error
        candidate = (payload.get("candidates") or [{}])[0]
        parts = candidate.get("content", {}).get("parts", []) if isinstance(candidate, dict) else []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
        if not text and isinstance(candidate, dict) and candidate.get("finishReason") == "MAX_TOKENS":
            # Let LocalLLM.json repair this with its larger structured-output retry instead of crashing the UI.
            return LLMResponse("", len(prompt.split()), 0, (perf_counter()-started)*1000, provider="gemini", model=model)
        if not text:
            raise RuntimeError(f"Gemini returned no text: {json.dumps(payload)[:300]}")
        return LLMResponse(text, len(prompt.split()), len(text.split()), (perf_counter()-started)*1000, provider="gemini", model=model)


class FallbackLLM(LocalLLM):
    """Use local MLX when Gemini has temporary capacity or network trouble."""
    def __init__(self, primary: GeminiLLM, fallback: LocalLLM):
        self.primary, self.fallback = primary, fallback
        self.model_name, self.backend, self.max_tokens = primary.model_name, "gemini_auto", primary.max_tokens

    def generate(self, prompt: str, max_tokens: int | None = None) -> LLMResponse:
        try:
            return self.primary.generate(prompt, max_tokens)
        except ProviderQuotaError as error:
            response = self.fallback.generate(prompt, max_tokens)
            response.fallback_reason = str(error)
            return response


def build_llm(model_config: dict[str, Any], *, mock: bool = False, selected_model: str | None = None) -> LocalLLM:
    """Construct the configured Gemini-first provider, with a local quota fallback."""
    local = LocalLLM(model_config["name"], "mock" if mock else "mlx", model_config["max_tokens"])
    if mock or selected_model == "local" or model_config.get("backend") != "gemini_auto":
        return local
    key = gemini_api_key()
    model = selected_model or model_config.get("gemini_model", "")
    return FallbackLLM(GeminiLLM(model, key, model_config["max_tokens"]), local) if key and model else local
