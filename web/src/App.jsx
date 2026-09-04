import { useEffect, useRef, useState } from "react";
import { fetchOptions, streamAsk } from "./api.js";
import { useChats } from "./useChats.js";
import Sidebar from "./components/Sidebar.jsx";
import Composer from "./components/Composer.jsx";
import AssistantMessage from "./components/AssistantMessage.jsx";
import StageTimeline from "./components/StageTimeline.jsx";

const STARTERS = [
  "Dân số Việt Nam theo tài liệu là bao nhiêu?",
  "Ông ấy sinh năm nào?",
  "Thủ đô của Việt Nam là gì?",
];

export default function App() {
  const { chats, active, activeId, setActiveId, patchActive, create, remove } = useChats();
  const [options, setOptions] = useState({ systems: ["PonyGuard", "Basic RAG"], models: ["local"] });
  const [system, setSystem] = useState("PonyGuard");
  const [model, setModel] = useState("local");
  const [draft, setDraft] = useState("");
  const [stages, setStages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottom = useRef(null);

  useEffect(() => {
    fetchOptions()
      .then((value) => {
        setOptions(value);
        setModel(value.models?.includes(value.default_model) ? value.default_model : value.models?.[0] || "local");
      })
      .catch((issue) => setError(issue.message));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [active.messages.length, stages.length, busy]);

  async function send(text) {
    const question = text.trim();
    if (!question || busy) return;
    const pending = active.pending;
    setDraft("");
    setError("");
    setStages([]);
    setBusy(true);
    patchActive((chat) => ({
      title: chat.title === "Cuộc trò chuyện mới" ? question.slice(0, 42) : chat.title,
      messages: [...chat.messages, { role: "user", content: pending ? `Làm rõ: ${question}` : question }],
      pending: null,
    }));
    try {
      await streamAsk(
        {
          question,
          system,
          model,
          pending_question: pending?.question || "",
          clarification_for: pending?.requirements || [],
        },
        (event) => {
          if (event.type === "stage") setStages((all) => [...all, event]);
          if (event.type === "error") setError(event.message);
          if (event.type === "result") {
            const ask = event.result.prediction.decision === "ASK";
            patchActive((chat) => ({
              messages: [...chat.messages, { role: "assistant", system: event.system, result: event.result }],
              pending: ask
                ? { question: event.resolved_question, requirements: event.result.trace?.requirements?.missing_requirements || [] }
                : null,
            }));
          }
        }
      );
    } catch (issue) {
      setError(issue.message);
    } finally {
      setBusy(false);
      setStages([]);
    }
  }

  return (
    <div className="app">
      <Sidebar chats={chats} activeId={activeId} onSelect={setActiveId} onCreate={create} onDelete={remove} />
      <main className="main">
        <div className="thread">
          {!active.messages.length ? (
            <div className="hero">
              <h1>Tôi có thể giúp gì?</h1>
              <p>Hỏi bằng tiếng Việt. PonyGuard chỉ trả lời khi bằng chứng trong tài liệu được kiểm chứng, hỏi lại khi câu hỏi thiếu thông tin, và từ chối có căn cứ khi không đủ dữ kiện.</p>
              <div className="chips">
                {STARTERS.map((starter) => (
                  <button key={starter} type="button" className="chip" onClick={() => send(starter)}>
                    {starter}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {active.messages.map((message, index) =>
            message.role === "user" ? (
              <article key={index} className="message user">
                <div className="bubble">{message.content}</div>
              </article>
            ) : (
              <AssistantMessage key={index} message={message} onPickOption={(option) => send(option)} />
            )
          )}

          {busy ? (
            <article className="message assistant">
              <div className="avatar pulsing" aria-hidden="true" />
              <div className="message-body">
                <StageTimeline stages={stages} running />
                {!stages.length ? <div className="caption">Đang khởi động pipeline…</div> : null}
              </div>
            </article>
          ) : null}

          {error ? <div className="error">{error}</div> : null}
          <div ref={bottom} />
        </div>

        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={() => send(draft)}
          busy={busy}
          pending={active.pending?.question || ""}
          system={system}
          onSystem={setSystem}
          model={model}
          onModel={setModel}
          options={options}
        />
      </main>
    </div>
  );
}
