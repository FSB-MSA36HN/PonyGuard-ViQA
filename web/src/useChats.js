import { useCallback, useEffect, useState } from "react";

const KEY = "ponyguard.chats.v1";
const LIMIT = 20; // traces are large; keep the history bounded so storage never fills
const newChat = () => ({ id: crypto.randomUUID(), title: "Cuộc trò chuyện mới", messages: [], pending: null });

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    if (Array.isArray(saved) && saved.length) return saved.slice(-LIMIT);
  } catch {
    // corrupt or unavailable storage falls back to a fresh chat
  }
  return [newChat()];
}

function save(chats) {
  try {
    localStorage.setItem(KEY, JSON.stringify(chats));
  } catch {
    // Over quota: keep the newest conversations rather than losing everything.
    try {
      localStorage.setItem(KEY, JSON.stringify(chats.slice(-3)));
    } catch {
      // storage blocked entirely; the session still works in memory
    }
  }
}

/** Chat list + active id, persisted per browser. No server-side history. */
export function useChats() {
  const [chats, setChats] = useState(load);
  const [activeId, setActiveId] = useState(() => chats[chats.length - 1].id);

  useEffect(() => save(chats), [chats]);

  const active = chats.find((chat) => chat.id === activeId) || chats[chats.length - 1];

  const patchActive = useCallback(
    (patch) => setChats((all) => all.map((chat) => (chat.id === activeId ? { ...chat, ...(typeof patch === "function" ? patch(chat) : patch) } : chat))),
    [activeId]
  );

  const create = useCallback(() => {
    const chat = newChat();
    setChats((all) => [...all, chat].slice(-LIMIT));
    setActiveId(chat.id);
  }, []);

  const remove = useCallback(
    (id) =>
      setChats((all) => {
        const rest = all.filter((chat) => chat.id !== id);
        const next = rest.length ? rest : [newChat()];
        if (id === activeId) setActiveId(next[next.length - 1].id);
        return next;
      }),
    [activeId]
  );

  return { chats, active, activeId, setActiveId, patchActive, create, remove };
}
