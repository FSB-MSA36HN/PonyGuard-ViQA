from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from ponyguard_viqa.core import add_clarification, load_config
from ponyguard_viqa.llm import build_llm, list_gemini_models
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard
from ponyguard_viqa.retrieval import Embedder, Retriever


st.set_page_config(page_title="PonyGuard", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stBottom"], [data-testid="stHeader"] { background:#101114!important; color:#f5f5f7; }
[data-testid="stAppViewContainer"] > .main { background:#101114!important; }
[data-testid="stSidebar"] { background:#17181d; border-right:1px solid #292b33; }
[data-testid="stSidebar"] > div:first-child { padding:1rem .75rem; }
.brand { font-size:1.1rem; font-weight:700; letter-spacing:-.035em; margin:.2rem 0 1rem; }
.brand span { color:#a78bfa; }.subtle { color:#a4a7b1; font-size:.8rem; }
.badge { display:inline-block; padding:.2rem .5rem; border-radius:99px; background:#22232a; color:#c8cad3; font-size:.7rem; font-weight:600; }
.decision { font-size:.71rem; font-weight:750; letter-spacing:.06em; padding:.26rem .55rem; border-radius:99px; display:inline-block; }
.answer { background:#203b33; color:#8cf1c9; }.ask { background:#3c3420; color:#ffd777; }.abstain { background:#3b2529; color:#ff9ea7; }
[data-testid="stMainBlockContainer"] { max-width:860px; padding-top:1.4rem; }
.assistant-meta { color:#a4a7b1; font-size:.72rem; margin:.2rem 0 .55rem; }
.starter button { border:1px solid #30313a!important; background:#191a20!important; border-radius:11px!important; color:#e5e5e8!important; font-size:.8rem!important; }
[data-testid="stChatMessage"] { background:transparent; padding:.45rem 0; animation:rise .25s ease-out; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p { line-height:1.6; }
[data-testid="stChatInput"] { border-radius:14px; border:1px solid #353740; background:#191a20; }
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea { background:#191a20!important; color:#f5f5f7!important; }
[data-testid="stChatInput"] textarea::placeholder { color:#9295a1!important; }
.stButton button { border-radius:10px; border-color:#353740!important; }
.st-key-composer { max-width:860px; margin:0 auto; }
.st-key-composer [data-testid="stTextArea"] textarea { background:#191a20!important; color:#f5f5f7!important; }
[data-testid="stSidebar"] .stButton button { justify-content:flex-start; text-align:left; }
@keyframes rise { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:translateY(0); } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(ttl=300)
def available_gemini_models() -> list[str]:
    return list_gemini_models()


@st.cache_resource
def shared_resources(config_version: int):
    config = load_config("configs/base.yaml")
    retrieval, model = config["retrieval"], config["model"]
    return (
        Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(retrieval["embedding_model"])),
        retrieval,
        model,
    )


@st.cache_resource
def selected_llm(selected_model: str):
    return build_llm(load_config("configs/base.yaml")["model"], selected_model=selected_model)


def pipeline(system: str, selected_model: str):
    retriever, retrieval, model = shared_resources(Path("configs/base.yaml").stat().st_mtime_ns)
    llm = selected_llm(selected_model)
    return BasicRAG(retriever, llm, retrieval["top_k"], stage_tokens=model.get("stage_max_tokens")) if system == "Basic RAG" else PonyGuard(retriever, llm, retrieval["top_k"], stage_tokens=model.get("stage_max_tokens"), intent_first=True)


def ask(system: str, selected_model: str, question: str, clarification_for: list[str] | None = None, progress=None) -> dict:
    result = pipeline(system, selected_model).run({"sample_id": f"demo_{uuid4().hex}", "question": question, "clarification_for": clarification_for or [], "gold_answers": [], "expected_action": "ANSWER"}, progress=progress)
    Path("runs").mkdir(exist_ok=True)
    with Path("runs/ui_timing.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "request_id": result["sample_id"], "system": system, "selected_model": selected_model, "prediction": result["prediction"], "trace": result.get("trace", {}), "performance": result["performance"]}, ensure_ascii=False) + "\n")
    return result


def empty_chat() -> dict:
    return {"id": uuid4().hex, "title": "New chat", "messages": [], "pending_question": None, "pending_requirements": []}


def saved_pending_requirements(chat: dict) -> list[str]:
    if "pending_requirements" in chat:
        return chat["pending_requirements"]
    for message in reversed(chat.get("messages", [])):
        if message.get("role") == "assistant" and message.get("result", {}).get("prediction", {}).get("decision") == "ASK":
            return message["result"].get("trace", {}).get("requirements", {}).get("missing_requirements", [])
    return []


def active_chat() -> dict:
    return next(chat for chat in st.session_state.chats if chat["id"] == st.session_state.active_chat_id)


def save_active_chat() -> None:
    chat = active_chat()
    chat["messages"] = st.session_state.messages
    chat["pending_question"] = st.session_state.pending_question
    chat["pending_requirements"] = st.session_state.pending_requirements


def new_chat() -> None:
    save_active_chat()
    chat = empty_chat()
    st.session_state.chats.append(chat)
    st.session_state.active_chat_id = chat["id"]
    st.session_state.messages = []
    st.session_state.pending_question = None
    st.session_state.pending_requirements = []
    st.rerun()


def open_chat(chat_id: str) -> None:
    save_active_chat()
    st.session_state.active_chat_id = chat_id
    chat = active_chat()
    st.session_state.messages = chat["messages"]
    st.session_state.pending_question = chat["pending_question"]
    st.session_state.pending_requirements = saved_pending_requirements(chat)
    st.rerun()


def delete_chat(chat_id: str) -> None:
    was_active = chat_id == st.session_state.active_chat_id
    st.session_state.chats = [chat for chat in st.session_state.chats if chat["id"] != chat_id]
    if not st.session_state.chats:
        st.session_state.chats = [empty_chat()]
    if was_active:
        chat = st.session_state.chats[-1]
        st.session_state.active_chat_id = chat["id"]
        st.session_state.messages = chat["messages"]
        st.session_state.pending_question = chat["pending_question"]
        st.session_state.pending_requirements = saved_pending_requirements(chat)
    st.rerun()


def copy_details_button(details: dict, request_id: str) -> None:
    """Copy a locally rendered diagnostic trace without interpolating model output into HTML."""
    payload = base64.b64encode(json.dumps(details, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")
    button_id = f"copy-details-{request_id.replace('_', '-')}"
    st.html(
        f"""
        <button id="{button_id}" type="button" aria-label="Copy diagnostic details"
          style="border:1px solid #353740;border-radius:8px;background:#191a20;color:#f5f5f7;padding:6px 10px;cursor:pointer;font:inherit">
          Copy details
        </button>
        <script>
        (() => {{
          const button = document.getElementById({json.dumps(button_id)});
          const text = new TextDecoder().decode(Uint8Array.from(atob({json.dumps(payload)}), c => c.charCodeAt(0)));
          button.onclick = async () => {{
            try {{ await navigator.clipboard.writeText(text); button.textContent = 'Copied'; }}
            catch (_) {{ button.textContent = 'Copy failed'; }}
            setTimeout(() => button.textContent = 'Copy details', 1400);
          }};
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


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
            with st.expander("Sources", expanded=False):
                st.markdown(f"> {evidence}")
                st.caption("Chunks: " + ", ".join(grounding.get("citation_chunk_ids", [])))
        coverage = result.get("trace", {}).get("coverage", {})
        if decision == "ABSTAIN" and coverage:
            with st.expander("Why not", expanded=False):
                st.write(coverage.get("reason_summary", "The evidence does not cover the request."))
                for fact in coverage.get("supported_facts", []):
                    st.markdown(f"> {fact['text']}\n\n`{fact['chunk_id']}`")
                    if fact.get("limitation"):
                        st.caption(fact["limitation"])
                gaps = coverage.get("coverage_gaps", [])
                for gap in [gaps] if isinstance(gaps, str) else gaps:
                    st.caption("• " + gap)
                if coverage.get("safe_rephrase"):
                    st.info(coverage["safe_rephrase"])
        st.markdown(f"<div class='assistant-meta'>{performance['latency_ms']:.0f} ms · {performance['llm_calls']} calls</div>", unsafe_allow_html=True)
        with st.expander("Details", expanded=False):
            details = {"timing": performance.get("stages", {}), "trace": result.get("trace", {})}
            copy_details_button(details, result["sample_id"])
            st.code(json.dumps(details, ensure_ascii=False, indent=2), language="json", wrap_lines=True)


if "chats" not in st.session_state:
    first_chat = empty_chat()
    st.session_state.chats = [first_chat]
    st.session_state.active_chat_id = first_chat["id"]
if "messages" not in st.session_state:
    chat = active_chat()
    st.session_state.messages = chat["messages"]
    st.session_state.pending_question = chat["pending_question"]
    st.session_state.pending_requirements = saved_pending_requirements(chat)
st.session_state.setdefault("pending_question", None)
if "pending_requirements" not in st.session_state:
    st.session_state.pending_requirements = saved_pending_requirements(active_chat())
st.session_state.setdefault("composer_nonce", 0)

with st.sidebar:
    st.markdown("<div class='brand'><span>✦</span> PonyGuard</div>", unsafe_allow_html=True)
    if st.button(":material/edit_square:  New chat", width="stretch"):
        new_chat()
    st.divider()
    st.caption("Chats")
    for chat in reversed(st.session_state.chats):
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            if st.button(
                f":material/chat_bubble_outline:  {chat['title']}",
                key=f"chat_{chat['id']}",
                type="primary" if chat["id"] == st.session_state.active_chat_id else "secondary",
                width="stretch",
            ):
                open_chat(chat["id"])
            if st.button("Delete", icon=":material/delete:", key=f"delete_{chat['id']}"):
                delete_chat(chat["id"])

if not st.session_state.messages:
    st.title("How can I help?")

for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])
    else:
        render_result(message)

pending = st.session_state.pending_question
placeholder = "Add a clarification…" if pending else "Message PonyGuard…"
local_model = load_config("configs/base.yaml")["model"]["name"]
model_options = available_gemini_models() + ["local"]
preferred_model = load_config("configs/base.yaml")["model"].get("gemini_model", "")
default_model_index = model_options.index(preferred_model) if preferred_model in model_options else 0
with st.bottom:
    with st.form("composer", border=True, clear_on_submit=False):
        typed_prompt = st.text_area(
            "Message",
            placeholder=placeholder,
            height=68,
            key=f"composer_text_{st.session_state.composer_nonce}",
            label_visibility="collapsed",
        )
        with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
            system = st.segmented_control(
                "Choose a model",
                ["PonyGuard", "Basic RAG"],
                default="PonyGuard",
                required=True,
                key="system_picker",
                label_visibility="collapsed",
                width="content",
                persist_state="session",
            )
            selected_model = st.selectbox(
                "Model",
                model_options,
                index=default_model_index,
                format_func=lambda value: f"Local · {local_model}" if value == "local" else f"Gemini · {value}",
                key="model_picker",
                label_visibility="collapsed",
                width=260,
                persist_state="session",
            )
            submitted = st.form_submit_button("Send", type="primary", icon=":material/arrow_upward:")
prompt = typed_prompt.strip() if submitted and typed_prompt else st.session_state.pop("queued_prompt", None)

if prompt:
    clarification_for = list(st.session_state.pending_requirements) if pending else []
    displayed = prompt if not pending else f"Clarification: {prompt}"
    st.session_state.messages.append({"role": "user", "content": displayed})
    chat = active_chat()
    if chat["title"] == "New chat":
        chat["title"] = prompt.strip().replace("\n", " ")[:42] or "New chat"
    question = add_clarification(pending, prompt) if pending else prompt
    st.session_state.pending_question = None
    st.session_state.pending_requirements = []
    with st.chat_message("assistant", avatar="🤖" if system == "Basic RAG" else "🛡️"):
        with st.status("Starting…", expanded=True) as status:
            def show_progress(stage: str, label: str) -> None:
                icons = {"understand": "psychology", "search": "travel_explore", "evidence": "fact_check", "answer": "edit_note", "verify": "verified", "decision": "account_tree"}
                st.write(f":material/{icons.get(stage, 'progress_activity')}: {label}")
                status.update(label=label, state="running", expanded=True)

            result = ask(system, selected_model, question, clarification_for, show_progress)
            status.update(label="Done", state="complete", expanded=False)
    assistant_message = {"role": "assistant", "system": system, "result": result}
    st.session_state.messages.append(assistant_message)
    if result["prediction"]["decision"] == "ASK":
        st.session_state.pending_question = question
        st.session_state.pending_requirements = result.get("trace", {}).get("requirements", {}).get("missing_requirements", [])
    st.session_state.composer_nonce += 1
    save_active_chat()
    st.rerun()
