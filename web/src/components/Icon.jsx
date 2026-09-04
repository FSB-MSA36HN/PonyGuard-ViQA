const PATHS = {
  plus: "M12 5v14M5 12h14",
  trash: "M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13",
  send: "M12 19V5M5 12l7-7 7 7",
  stop: "M7 7h10v10H7z",
  check: "M4 12l5 5L20 6",
  chat: "M21 12a8 8 0 0 1-8 8H4l2.2-2.6A8 8 0 1 1 21 12z",
  search: "M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16zM21 21l-4.3-4.3",
  brain: "M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8V16a3 3 0 0 0 4 2.8V4zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 1 5.8V16a3 3 0 0 1-4 2.8V4z",
  shield: "M12 3l7 3v6c0 4.2-2.9 7.6-7 9-4.1-1.4-7-4.8-7-9V6l7-3z",
  quote: "M6 17h4l2-4V7H5v6h3l-2 4zm10 0h4l2-4V7h-7v6h3l-2 4z",
  chevron: "M9 6l6 6-6 6",
  down: "M12 5v14M6 13l6 6 6-6",
  copy: "M9 9h10v10H9zM5 15V5h10",
  spark: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2 2-6z",
  edit: "M4 20h4L18 6l-4-4L4 16v4zM13 3l4 4",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6L6 18",
  sun: "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14A8.5 8.5 0 0 1 10 4a8.5 8.5 0 1 0 10 10z",
  alert: "M12 8v5M12 16.5v.5M10.3 4l-7 12A2 2 0 0 0 5 19h14a2 2 0 0 0 1.7-3l-7-12a2 2 0 0 0-3.4 0z",
};

export default function Icon({ name, size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] || PATHS.spark} />
    </svg>
  );
}
