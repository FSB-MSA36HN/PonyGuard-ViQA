import { useState } from "react";
import Icon from "./Icon.jsx";

export default function Collapsible({ title, badge, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`collapsible${open ? " open" : ""}`}>
      <button type="button" className="collapsible-head" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span className="collapsible-caret">
          <Icon name="chevron" size={14} />
        </span>
        <span>{title}</span>
        {badge ? <span className="pill">{badge}</span> : null}
      </button>
      {open ? <div className="collapsible-body">{children}</div> : null}
    </div>
  );
}
