import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";

/** A sent question can be edited; resending replaces everything after it. */
export default function UserMessage({ content, disabled, onResend }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const box = useRef(null);

  useEffect(() => {
    const node = box.current;
    if (!editing || !node) return;
    node.focus();
    node.setSelectionRange(node.value.length, node.value.length);
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 220)}px`;
  }, [editing, value]);

  function start() {
    setValue(content.replace(/^Làm rõ:\s*/, ""));
    setEditing(true);
  }

  function submit() {
    const text = value.trim();
    if (!text) return;
    setEditing(false);
    onResend(text);
  }

  if (editing) {
    return (
      <article className="message user editing">
        <div className="edit-box">
          <textarea
            ref={box}
            value={value}
            aria-label="Sửa câu hỏi"
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") setEditing(false);
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <div className="edit-actions">
            <button type="button" className="btn-ghost" onClick={() => setEditing(false)}>
              Huỷ
            </button>
            <button type="button" className="btn-primary" onClick={submit} disabled={!value.trim()}>
              Gửi lại
            </button>
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="message user">
      <button type="button" className="icon-btn edit-btn" onClick={start} disabled={disabled} aria-label="Sửa câu hỏi" title="Sửa câu hỏi">
        <Icon name="edit" size={15} />
      </button>
      <div className="bubble">{content}</div>
    </article>
  );
}
