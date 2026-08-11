from __future__ import annotations
import sys
import json
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from ponyguard_viqa.core import add_clarification, load_config
from ponyguard_viqa.llm import LocalLLM
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard
from ponyguard_viqa.retrieval import Embedder, Retriever

@st.cache_resource
def resources():
    config = load_config("configs/base.yaml"); r, m = config["retrieval"], config["model"]
    return (Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(r["embedding_model"])), LocalLLM(m["name"], m["backend"], m["max_tokens"]), r, m)


def pipeline(system):
    retriever, llm, retrieval, model = resources()
    cls = BasicRAG if system == "Basic RAG" else PonyGuard
    return cls(retriever, llm, retrieval["top_k"], stage_tokens=model.get("stage_max_tokens"))

st.set_page_config(page_title="PonyGuard-ViQA", layout="wide")
def ask(system, question):
    result = pipeline(system).run({"sample_id": f"demo_{uuid4().hex}", "question": question, "gold_answers": [], "expected_action": "ANSWER"})
    Path("runs/ui_timing.jsonl").parent.mkdir(exist_ok=True)
    with Path("runs/ui_timing.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "request_id": result["sample_id"], "system": system, "performance": result["performance"]}, ensure_ascii=False) + "\n")
    return result


st.title("PonyGuard-ViQA")
system = st.sidebar.radio("System", ["Basic RAG", "PonyGuard"])
if st.sidebar.button("Xóa cuộc hội thoại"):
    st.session_state.pop("demo_result", None)
    st.session_state.pop("demo_question", None)
    st.rerun()

question = st.text_area("Câu hỏi", placeholder="Nhập câu hỏi tiếng Việt...")
if st.button("Hỏi", type="primary") and question.strip():
    st.session_state.demo_question = question
    with st.status("Đang tìm evidence…", expanded=True) as status:
        st.write("Đang chạy model local và kiểm chứng grounding.")
        st.session_state.demo_result = ask(system, question)
        status.update(label="Hoàn tất", state="complete", expanded=False)

result = st.session_state.get("demo_result")
if result:
    left, center, right = st.columns([1, 1, 2])
    with left: st.subheader("Decision"); st.metric("Action", result["prediction"]["decision"])
    with center: st.subheader("Final answer"); st.write(result["prediction"]["answer"])
    grounding = result["prediction"].get("grounding", {})
    st.caption("Grounding: " + ("đã kiểm chứng" if grounding.get("valid") else "không hợp lệ") + (f" · chunks: {', '.join(grounding.get('citation_chunk_ids', []))}" if grounding.get("citation_chunk_ids") else ""))
    if grounding.get("evidence_quote"):
        st.info("Evidence quote: " + grounding["evidence_quote"])
    if result["prediction"].get("reason"):
        st.caption("Lý do quyết định: " + result["prediction"]["reason"])
    perf = result["performance"]
    st.caption(f"Thời gian LLM: {perf['latency_ms']:.0f} ms · {perf['llm_calls']} lượt gọi · tokens vào/ra: {perf['input_tokens']}/{perf['output_tokens']}")
    with st.expander("Timing theo stage"):
        st.json(perf.get("stages", {}))
    with right:
        st.subheader("Trace")
        st.json(result.get("trace", {"retrieval": result["retrieval"]}))
    if result["prediction"]["decision"] == "ASK":
        st.info("PonyGuard cần làm rõ yêu cầu. Thông tin bạn nhập chỉ dùng để xác định câu hỏi; hệ thống vẫn phải tìm evidence từ corpus.")
        clarification = st.text_input("Bổ sung entity hoặc thuộc tính cần hỏi", placeholder="Ví dụ: Tôi đang hỏi số loài hoa ở Vườn quốc gia Cúc Phương.")
        if st.button("Gửi thông tin làm rõ") and clarification.strip():
            st.session_state.demo_question = add_clarification(st.session_state.demo_question, clarification)
            st.session_state.demo_result = ask(system, st.session_state.demo_question)
            st.rerun()
