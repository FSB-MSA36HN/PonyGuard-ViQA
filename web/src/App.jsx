import { useCallback, useEffect, useRef, useState } from "react";
import { fetchOptions, streamAsk } from "./api.js";
import { useChats } from "./useChats.js";
import Sidebar from "./components/Sidebar.jsx";
import Composer from "./components/Composer.jsx";
import AssistantMessage from "./components/AssistantMessage.jsx";
import UserMessage from "./components/UserMessage.jsx";
import StageTimeline from "./components/StageTimeline.jsx";
import Icon from "./components/Icon.jsx";

const STARTERS = [
  "Thủ đô của Việt Nam là gì?",
  "Kepler sinh năm nào?",
  "Ông ấy sinh năm nào?",
];

function initialTheme() {
  const saved = localStorage.getItem("ponyguard.theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const { chats, active, activeId, setActiveId, patchActive, create, remove } = useChats();
  const [options, setOptions] = useState({ systems: ["PonyGuard", "Basic RAG"], models: ["local"] });
  const [system, setSystem] = useState("PonyGuard");
  const [model, setModel] = useState("auto");
  const [draft, setDraft] = useState("");
  const [stages, setStages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [theme, setTheme] = useState(initialTheme);
  const [narrow, setNarrow] = useState(() => window.matchMedia("(max-width: 880px)").matches);
  const [sidebar, setSidebar] = useState(() => !window.matchMedia("(max-width: 880px)").matches);
  const [atBottom, setAtBottom] = useState(true);
  const [scrolled, setScrolled] = useState(false);

  const thread = useRef(null);
  const composer = useRef(null);
  const abort = useRef(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("ponyguard.theme", theme);
  }, [theme]);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 880px)");
    const onChange = (event) => {
      setNarrow(event.matches);
      setSidebar(!event.matches);
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    fetchOptions()
      .then((value) => {
        setOptions(value);
        setModel(value.models?.includes(value.default_model) ? value.default_model : value.models?.[0] || "local");
      })
      .catch(() => setError("Không kết nối được backend. Chạy ./run.sh rồi tải lại trang."));
  }, []);

  const scrollToBottom = useCallback((behavior = "smooth") => {
    const node = thread.current;
    if (node) node.scrollTo({ top: node.scrollHeight, behavior });
  }, []);

  // Follow the conversation only while the reader is already at the end.
  useEffect(() => {
    if (atBottom) scrollToBottom();
  }, [active.messages.length, stages.length, busy, atBottom, scrollToBottom]);

  function onThreadScroll(event) {
    const node = event.currentTarget;
    setAtBottom(node.scrollHeight - node.scrollTop - node.clientHeight < 120);
    setScrolled(node.scrollTop > 4);
  }

  function stop() {
    abort.current?.abort();
    setNotice("Đã dừng phản hồi. Câu hỏi vẫn còn trong lịch sử, bạn có thể sửa và gửi lại.");
  }

  async function send(text, truncateAt = null) {
    const question = text.trim();
    if (!question || busy) return;
    // An edited question starts a fresh turn: everything after it is replaced.
    const pending = truncateAt === null ? active.pending : null;
    setDraft("");
    setError("");
    setNotice("");
    setStages([]);
    setBusy(true);
    setAtBottom(true);
    patchActive((chat) => {
      const kept = truncateAt === null ? chat.messages : chat.messages.slice(0, truncateAt);
      return {
        title: chat.title === "Cuộc trò chuyện mới" || truncateAt === 0 ? question.slice(0, 48) : chat.title,
        messages: [...kept, { role: "user", content: pending ? `Làm rõ: ${question}` : question }],
        pending: null,
      };
    });
    const controller = new AbortController();
    abort.current = controller;
    try {
      await streamAsk(
        { question, system, model, pending_question: pending?.question || "", clarification_for: pending?.requirements || [] },
        (event) => {
          if (event.type === "stage") setStages((all) => [...all, event]);
          if (event.type === "error") setError(event.message);
          if (event.type === "result") {
            const ask = event.result.prediction.decision === "ASK";
            patchActive((chat) => ({
              messages: [...chat.messages, { role: "assistant", system: event.system, result: event.result }],
              pending: ask ? { question: event.resolved_question, requirements: event.result.trace?.requirements?.missing_requirements || [] } : null,
            }));
            if (ask) setTimeout(() => composer.current?.focus(), 60);
          }
        },
        controller.signal
      );
    } catch (issue) {
      if (issue.name !== "AbortError") setError(issue.message);
    } finally {
      abort.current = null;
      setBusy(false);
      setStages([]);
    }
  }

  return (
    <div className="app">
      <Sidebar
        chats={chats}
        activeId={activeId}
        open={sidebar}
        theme={theme}
        onSelect={(id) => {
          setActiveId(id);
          if (narrow) setSidebar(false);
        }}
        onCreate={() => {
          create();
          setTimeout(() => composer.current?.focus(), 60);
        }}
        onDelete={remove}
        onClose={() => setSidebar(false)}
        onToggleTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
      />
      {sidebar && narrow ? <button type="button" className="backdrop" aria-label="Đóng thanh bên" onClick={() => setSidebar(false)} /> : null}

      <main className="main">
        <header className={`topbar${scrolled ? " scrolled" : ""}`}>
          <button type="button" className="icon-btn hide-desktop" onClick={() => setSidebar(true)} aria-label="Mở thanh bên">
            <Icon name="menu" size={18} />
          </button>
          <span className="topbar-title">{active.messages.length ? active.title : "PonyGuard"}</span>
          <span className="topbar-spacer" />
          <span className="pill">{system}</span>
        </header>

        <div className="thread" ref={thread} onScroll={onThreadScroll}>
          <div className="thread-inner">
            {!active.messages.length ? (
              <div className="hero">
                <div className="hero-mark">
                  <Icon name="shield" size={22} />
                </div>
                <h1>Hôm nay bạn muốn hỏi gì?</h1>
                <p>PonyGuard chỉ trả lời khi bằng chứng trong tài liệu được kiểm chứng, hỏi lại khi câu hỏi còn thiếu thông tin, và từ chối kèm lý do khi không đủ căn cứ.</p>
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
                <UserMessage key={index} content={message.content} disabled={busy} onResend={(text) => send(text, index)} />
              ) : (
                <AssistantMessage key={index} message={message} onPickOption={(option) => send(option)} />
              )
            )}

            {busy ? (
              <article className="message assistant">
                <div className="avatar" aria-hidden="true">
                  <Icon name="shield" size={15} />
                </div>
                <div className="message-body" aria-live="polite">
                  {stages.length ? <StageTimeline stages={stages} running /> : <div className="shimmer" style={{ width: "42%" }} />}
                </div>
              </article>
            ) : null}

            {notice ? <p className="notice">{notice}</p> : null}

            {error ? (
              <div className="error" role="alert">
                <Icon name="alert" size={16} />
                <span>{error}</span>
              </div>
            ) : null}
          </div>
        </div>

        {!atBottom && active.messages.length ? (
          <button type="button" className="scroll-bottom" onClick={() => scrollToBottom()} aria-label="Xuống cuối">
            <Icon name="down" size={16} />
          </button>
        ) : null}

        <Composer
          inputRef={composer}
          value={draft}
          onChange={setDraft}
          onSubmit={() => send(draft)}
          onStop={stop}
          busy={busy}
          pending={active.pending?.question || ""}
          onCancelPending={() => patchActive({ pending: null })}
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
