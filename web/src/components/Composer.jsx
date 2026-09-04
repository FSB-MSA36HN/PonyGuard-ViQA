import { useEffect, useRef } from "react";
import Icon from "./Icon.jsx";

export default function Composer({ value, onChange, onSubmit, onStop, busy, pending, onCancelPending, system, onSystem, model, onModel, options, inputRef }) {
  const fallback = useRef(null);
  const box = inputRef || fallback;

  useEffect(() => {
    const node = box.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 200)}px`;
  }, [value, box]);

  const send = () => {
    if (!busy && value.trim()) onSubmit();
  };

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        {pending ? (
          <div className="pending-note">
            <Icon name="alert" size={15} />
            <span>Đang bổ sung thông tin cho: “{pending}”</span>
            <button type="button" onClick={onCancelPending} aria-label="Bỏ qua, hỏi câu mới">
              <Icon name="close" size={14} />
            </button>
          </div>
        ) : null}

        <div className="composer-shell">
          <textarea
            ref={box}
            rows={1}
            value={value}
            placeholder={pending ? "Nhập thông tin làm rõ…" : "Hỏi PonyGuard…"}
            aria-label="Câu hỏi"
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              // A Vietnamese IME commits with Enter; never send mid-composition.
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                send();
              }
            }}
          />
          <div className="composer-bar">
            <div className="segmented" role="group" aria-label="Hệ thống">
              {(options.systems || []).map((name) => (
                <button key={name} type="button" className={name === system ? "active" : ""} aria-pressed={name === system} onClick={() => onSystem(name)}>
                  {name}
                </button>
              ))}
            </div>
            <select
              className="model-select"
              value={model}
              onChange={(event) => onModel(event.target.value)}
              aria-label="Nguồn model"
              title={options.gemini_model ? `Tự động: ${options.gemini_model}, hết quota thì chuyển sang ${options.local_model}` : undefined}
            >
              {(options.models || []).map((name) => (
                <option key={name} value={name}>
                  {name === "local" ? `Chỉ máy cục bộ · ${options.local_model || "MLX"}` : "Tự động"}
                </option>
              ))}
            </select>
            {busy ? (
              <button type="button" className="btn-send btn-stop" onClick={onStop} aria-label="Dừng">
                <Icon name="stop" size={13} />
              </button>
            ) : (
              <button type="submit" className="btn-send" disabled={!value.trim()} aria-label="Gửi câu hỏi">
                <Icon name="send" size={16} />
              </button>
            )}
          </div>
        </div>
        <p className="composer-hint">Enter để gửi · Shift + Enter để xuống dòng</p>
      </form>
    </div>
  );
}
