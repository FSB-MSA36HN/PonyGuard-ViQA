"""HTTP backend for the React UI: pipeline stages streamed as NDJSON.

ponytail: stdlib ThreadingHTTPServer, no FastAPI/uvicorn dependency. The whole
surface is three endpoints; move to FastAPI only if auth, validation schemas or
websockets show up.
"""
from __future__ import annotations

import json
import queue
import sys
import threading
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ponyguard_viqa.core import add_clarification, load_config  # noqa: E402
from ponyguard_viqa.llm import build_llm, list_gemini_models  # noqa: E402
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard  # noqa: E402
from ponyguard_viqa.retrieval import Embedder, Retriever  # noqa: E402

WEB_DIST = ROOT / "web" / "dist"


@lru_cache(maxsize=1)
def config() -> dict:
    return load_config(ROOT / "configs" / "base.yaml")


@lru_cache(maxsize=1)
def retriever() -> Retriever:
    embedding = config()["retrieval"]["embedding_model"]
    return Retriever(ROOT / "artifacts/index/faiss.index", ROOT / "artifacts/index/documents.jsonl", Embedder(embedding))


@lru_cache(maxsize=4)
def llm(selected_model: str):
    return build_llm(config()["model"], selected_model=selected_model)


@lru_cache(maxsize=8)
def pipeline(system: str, selected_model: str):
    retrieval, model = config()["retrieval"], config()["model"]
    stage_tokens = model.get("stage_max_tokens")
    if system == "Basic RAG":
        return BasicRAG(retriever(), llm(selected_model), retrieval["top_k"], stage_tokens=stage_tokens)
    return PonyGuard(retriever(), llm(selected_model), retrieval["top_k"], stage_tokens=stage_tokens, intent_first=True)


@lru_cache(maxsize=1)
def gemini_models() -> tuple[str, ...]:
    return tuple(list_gemini_models())


def log_run(system: str, selected_model: str, result: dict) -> None:
    path = ROOT / "runs" / "ui_timing.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(), "request_id": result["sample_id"],
            "system": system, "selected_model": selected_model, "prediction": result["prediction"],
            "trace": result.get("trace", {}), "performance": result["performance"],
        }, ensure_ascii=False) + "\n")


def run_stream(body: dict):
    """Yield {stage} events while the blocking pipeline runs, then {result}."""
    system = body.get("system", "PonyGuard")
    selected_model = body.get("model", "local")
    pending = body.get("pending_question") or ""
    typed = (body.get("question") or "").strip()
    question = add_clarification(pending, typed) if pending else typed
    sample = {
        "sample_id": f"demo_{uuid4().hex}", "question": question,
        "clarification_for": body.get("clarification_for") or [],
        "gold_answers": [], "expected_action": "ANSWER",
    }
    events: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            result = pipeline(system, selected_model).run(sample, progress=lambda stage, label: events.put({"type": "stage", "stage": stage, "label": label}))
            log_run(system, selected_model, result)
            events.put({"type": "result", "system": system, "resolved_question": question, "result": result})
        except Exception as error:  # surfaced in the UI instead of a dead stream
            events.put({"type": "error", "message": f"{type(error).__name__}: {error}"})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()
    while (event := events.get()) is not None:
        yield event


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # keep the console readable
        pass

    def _send(self, status: int, payload: bytes, content_type: str, stream: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if stream:
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def _chunk(self, event: dict) -> None:
        data = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()

    def do_OPTIONS(self) -> None:
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:
        if self.path.startswith("/api/models"):
            model = config()["model"]
            self._send(200, json.dumps({
                "systems": ["PonyGuard", "Basic RAG"],
                "models": [*gemini_models(), "local"],
                "default_model": model.get("gemini_model", "local"),
                "local_model": model["name"],
            }).encode(), "application/json")
            return
        self._serve_static()

    def do_POST(self) -> None:
        if not self.path.startswith("/api/ask"):
            self._send(404, b"{}", "application/json")
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        self._send(200, b"", "application/x-ndjson", stream=True)
        for event in run_stream(body):
            self._chunk(event)
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def _serve_static(self) -> None:
        relative = self.path.split("?")[0].lstrip("/") or "index.html"
        target = (WEB_DIST / relative).resolve()
        if not target.is_file() or WEB_DIST not in target.parents:
            target = WEB_DIST / "index.html"
        if not target.is_file():
            self._send(404, b"Run `npm run build` in web/, or use the Vite dev server.", "text/plain")
            return
        types = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".json": "application/json"}
        self._send(200, target.read_bytes(), types.get(target.suffix, "application/octet-stream"))


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"PonyGuard API on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
