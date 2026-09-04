import Icon from "./Icon.jsx";

export default function Sidebar({ chats, activeId, open, theme, onSelect, onCreate, onDelete, onClose, onToggleTheme }) {
  return (
    <aside className={`sidebar${open ? "" : " closed"}`} aria-label="Lịch sử trò chuyện">
      <div className="sidebar-top">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="shield" size={15} />
          </span>
          PonyGuard
        </div>
        <div style={{ display: "flex" }}>
          <button type="button" className="icon-btn" onClick={onToggleTheme} aria-label={theme === "dark" ? "Chuyển giao diện sáng" : "Chuyển giao diện tối"} title="Đổi giao diện">
            <Icon name={theme === "dark" ? "sun" : "moon"} size={16} />
          </button>
          <button type="button" className="icon-btn hide-desktop" onClick={onClose} aria-label="Đóng thanh bên">
            <Icon name="close" size={16} />
          </button>
        </div>
      </div>

      <button type="button" className="btn-new" onClick={onCreate}>
        <Icon name="plus" size={15} /> Cuộc trò chuyện mới
      </button>

      <div className="sidebar-label">Lịch sử</div>
      <nav className="chat-list">
        {[...chats].reverse().map((chat) => (
          <div key={chat.id} className={`chat-item${chat.id === activeId ? " active" : ""}`}>
            <button type="button" className="chat-open" onClick={() => onSelect(chat.id)} title={chat.title}>
              <Icon name="chat" size={15} />
              <span>{chat.title}</span>
            </button>
            <button type="button" className="chat-delete" onClick={() => onDelete(chat.id)} aria-label={`Xoá ${chat.title}`}>
              <Icon name="trash" size={14} />
            </button>
          </div>
        ))}
      </nav>

      <p className="sidebar-foot">Mọi câu trả lời đều được kiểm chứng trực tiếp trên văn bản nguồn: có bằng chứng thì trả lời, thiếu thông tin thì hỏi lại, không đủ căn cứ thì từ chối kèm lý do.</p>
    </aside>
  );
}
