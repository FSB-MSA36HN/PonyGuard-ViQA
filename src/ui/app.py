from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from ponyguard_viqa.core import add_clarification, load_config
from ponyguard_viqa.llm import LocalLLM
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard
from ponyguard_viqa.retrieval import Embedder, Retriever

@st.cache_resource
def pipeline(system):
    config = load_config("configs/base.yaml"); r, m = config["retrieval"], config["model"]
    retriever = Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(r["embedding_model"]))
    llm = LocalLLM(m["name"], m["backend"], m["max_tokens"])
    return (BasicRAG if system == "Basic RAG" else PonyGuard)(retriever, llm, r["top_k"])

st.set_page_config(page_title="PonyGuard-ViQA", layout="wide")
def ask(system, question):
    return pipeline(system).run({"sample_id": "demo", "question": question, "gold_answers": [], "expected_action": "ANSWER"})


st.title("PonyGuard-ViQA")
system = st.sidebar.radio("System", ["Basic RAG", "PonyGuard"])
if st.sidebar.button("Xóa cuộc hội thoại"):
    st.session_state.pop("demo_result", None)
    st.session_state.pop("demo_question", None)
    st.rerun()

question = st.text_area("Câu hỏi", placeholder="Nhập câu hỏi tiếng Việt...")
if st.button("Hỏi", type="primary") and question.strip():
    st.session_state.demo_question = question
    st.session_state.demo_result = ask(system, question)

result = st.session_state.get("demo_result")
if result:
    left, center, right = st.columns([1, 1, 2])
    with left: st.subheader("Decision"); st.metric("Action", result["prediction"]["decision"])
    with center: st.subheader("Final answer"); st.write(result["prediction"]["answer"])
    if result["prediction"].get("reason"):
        st.caption("Lý do quyết định: " + result["prediction"]["reason"])
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
