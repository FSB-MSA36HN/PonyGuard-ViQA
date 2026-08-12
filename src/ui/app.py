from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from ponyguard_viqa.core import add_clarification, load_config
from ponyguard_viqa.llm import LocalLLM
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard
from ponyguard_viqa.retrieval import Embedder, Retriever


st.set_page_config(page_title="PonyGuard", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
:root { --ink:#f5f5f7; --muted:#a4a7b1; --panel:#17181e; --line:#292b35; --accent:#a78bfa; --mint:#70e0bb; }
.stApp { background: radial-gradient(circle at 72% -10%, #30214a 0, transparent 30%), #0e0f13; color:var(--ink); }
[data-testid="stSidebar"] { background:#121319; border-right:1px solid var(--line); }
[data-testid="stSidebar"] > div:first-child { padding:1.2rem .9rem; }
.brand { font-size:1.26rem; font-weight:750; letter-spacing:-.045em; margin:.15rem 0 .15rem; }
.brand span { color:var(--accent); }.subtle { color:var(--muted); font-size:.83rem; }
.mode-card { border:1px solid var(--line); background:linear-gradient(145deg,#1b1d25,#14151a); border-radius:15px; padding:12px; margin:8px 0 18px; }
.mode-card b { font-size:.91rem; }.mode-card p { color:var(--muted); font-size:.75rem; margin:4px 0 0; }
.hero { max-width:820px; margin:4.6rem auto 1.3rem; text-align:center; animation:rise .45s ease-out; }
.hero h1 { font-size:clamp(2.1rem,5vw,3.5rem); letter-spacing:-.065em; margin:0; }
.hero p { color:var(--muted); font-size:1.04rem; margin:.65rem 0 1.25rem; }
.eyebrow,.badge { display:inline-block; padding:.24rem .56rem; border-radius:99px; background:#222033; color:#cabdff; font-size:.72rem; font-weight:650; }
.decision { font-size:.71rem; font-weight:750; letter-spacing:.06em; padding:.26rem .55rem; border-radius:99px; display:inline-block; }
.answer { background:#203b33; color:#8cf1c9; }.ask { background:#3c3420; color:#ffd777; }.abstain { background:#3b2529; color:#ff9ea7; }
.assistant-meta { color:var(--muted); font-size:.76rem; margin:.3rem 0 .7rem; }
.starter button { border:1px solid var(--line)!important; background:#181a22!important; border-radius:14px!important; min-height:76px; color:var(--ink)!important; text-align:left!important; transition:.2s!important; }
.starter button:hover { border-color:var(--accent)!important; transform:translateY(-2px); background:#211d30!important; }
[data-testid="stChatMessage"] { background:transparent; padding:.45rem 0; animation:rise .25s ease-out; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p { line-height:1.65; }
[data-testid="stChatInput"] { border-radius:17px; border:1px solid #3b3e4b; background:#181a22; box-shadow:0 12px 38px rgba(0,0,0,.22); }
.stButton button { border-radius:10px; }
@keyframes rise { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:translateY(0); } }
@media (max-width: 700px) { .hero { margin:2.5rem auto 1rem; } [data-testid="stSidebar"] { min-width:260px; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def resources():
    config = load_config("configs/base.yaml")
    retrieval, model = config["retrieval"], config["model"]
    return (
        Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(retrieval["embedding_model"])),
        LocalLLM(model["name"], model["backend"], model["max_tokens"]),
        retrieval,
        model,
    )


def pipeline(system: str):
    retriever, llm, retrieval, model = resources()
    return (BasicRAG if system == "Basic RAG" else PonyGuard)(retriever, llm, retrieval["top_k"], stage_tokens=model.get("stage_max_tokens"))


def ask(system: str, question: str) -> dict:
    result = pipeline(system).run({"sample_id": f"demo_{uuid4().hex}", "question": question, "gold_answers": [], "expected_action": "ANSWER"})
    Path("runs").mkdir(exist_ok=True)
    with Path("runs/ui_timing.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "request_id": result["sample_id"], "system": system, "performance": result["performance"]}, ensure_ascii=False) + "\n")
    return result


def new_chat() -> None:
    st.session_state.messages = []
    st.session_state.pending_question = None
    st.rerun()


def render_result(message: dict) -> None:
    result, system = message["result"], message["system"]
    prediction, performance = result["prediction"], result["performance"]
    decision = prediction["decision"]
    style = {"ANSWER": "answer", "ASK": "ask", "ABSTAIN": "abstain"}[decision]
    with st.chat_message("assistant", avatar="🤖" if system == "Basic RAG" else "🛡️"):
        st.markdown(f"<span class='badge'>{system}</span> <span class='decision {style}'>{decision}</span>", unsafe_allow_html=True)
        st.markdown(prediction["answer"])
        if prediction.get("reason"):
            st.caption(prediction["reason"])
        grounding = prediction.get("grounding", {})
        evidence = grounding.get("evidence_quote")
        if evidence:
            with st.expander("Evidence đã dùng", expanded=False):
                st.markdown(f"> {evidence}")
                st.caption("Chunks: " + ", ".join(grounding.get("citation_chunk_ids", [])))
        coverage = result.get("trace", {}).get("coverage", {})
        if decision == "ABSTAIN" and coverage:
            with st.expander("Vì sao chưa thể xác nhận", expanded=True):
                st.write(coverage.get("reason_summary", "Evidence chưa bao phủ đầy đủ yêu cầu."))
                for fact in coverage.get("supported_facts", []):
                    st.markdown(f"> {fact['text']}\n\n`{fact['chunk_id']}`")
                gaps = coverage.get("coverage_gaps", [])
                for gap in [gaps] if isinstance(gaps, str) else gaps:
                    st.caption("• " + gap)
                if coverage.get("safe_rephrase"):
                    st.info(coverage["safe_rephrase"])
        st.markdown(f"<div class='assistant-meta'>Local inference · {performance['latency_ms']:.0f} ms · {performance['llm_calls']} lượt model</div>", unsafe_allow_html=True)
        with st.expander("Trace & timing", expanded=False):
            st.json({"timing": performance.get("stages", {}), "trace": result.get("trace", {})})


if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

with st.sidebar:
    st.markdown("<div class='brand'><span>✦</span> PonyGuard</div><div class='subtle'>Vietnamese evidence workspace</div>", unsafe_allow_html=True)
    st.divider()
    system = st.radio("AI mode", ["PonyGuard", "Basic RAG"], label_visibility="collapsed")
    descriptions = {
        "PonyGuard": ("🛡️  PonyGuard", "Evidence-first · ANSWER / ASK / ABSTAIN"),
        "Basic RAG": ("✦  Basic RAG", "Grounded baseline · direct response"),
    }
    title, description = descriptions[system]
    st.markdown(f"<div class='mode-card'><b>{title}</b><p>{description}</p></div>", unsafe_allow_html=True)
    st.button("＋ New chat", use_container_width=True, on_click=new_chat)
    st.divider()
    st.markdown("<div class='subtle'>Local · Qwen 2.5 7B Q4<br>FAISS evidence index · 5 chunks</div>", unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown("<div class='hero'><span class='eyebrow'>LOCAL · GROUNDED · VIETNAMESE</span><h1>Hỏi từ evidence, không đoán mò.</h1><p>Chọn AI mode ở sidebar, sau đó bắt đầu một cuộc hội thoại.</p></div>", unsafe_allow_html=True)
    examples = ["Việt Nam có bao nhiêu cấp học?", "Việt Nam có bao nhiêu loài thực vật?", "Hiện tại Việt Nam có mấy?"]
    cols = st.columns(3)
    for column, example in zip(cols, examples):
        with column:
            if st.button(example, use_container_width=True, key=example):
                st.session_state.queued_prompt = example

for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])
    else:
        render_result(message)

pending = st.session_state.pending_question
placeholder = "Bổ sung thông tin để PonyGuard làm rõ…" if pending else "Nhắn câu hỏi của bạn…"
submitted = st.chat_input(placeholder, key="chat_input")
prompt = submitted or st.session_state.pop("queued_prompt", None)

if prompt:
    displayed = prompt if not pending else f"Làm rõ: {prompt}"
    st.session_state.messages.append({"role": "user", "content": displayed})
    question = add_clarification(pending, prompt) if pending else prompt
    st.session_state.pending_question = None
    with st.chat_message("assistant", avatar="🤖" if system == "Basic RAG" else "🛡️"):
        label = "PonyGuard đang phân tích yêu cầu và evidence…" if system == "PonyGuard" else "Basic RAG đang tìm evidence và tạo câu trả lời…"
        with st.status(label, expanded=True) as status:
            st.write("Đang chạy local model. Bạn có thể xem timing chi tiết sau khi hoàn tất.")
            result = ask(system, question)
            status.update(label="Hoàn tất", state="complete", expanded=False)
    assistant_message = {"role": "assistant", "system": system, "result": result}
    st.session_state.messages.append(assistant_message)
    if result["prediction"]["decision"] == "ASK":
        st.session_state.pending_question = question
    st.rerun()
