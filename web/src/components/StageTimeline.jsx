import Icon from "./Icon.jsx";

const ICONS = { understand: "brain", search: "search", evidence: "quote", answer: "spark", verify: "shield", decision: "check" };

/** Live agent trace: each pipeline stage as it is reported by the backend. */
export default function StageTimeline({ stages, running }) {
  if (!stages.length) return null;
  return (
    <ol className="timeline">
      {stages.map((stage, index) => {
        const done = !running || index < stages.length - 1;
        return (
          <li key={`${stage.stage}-${index}`} className={done ? "done" : "active"}>
            <span className="timeline-dot">
              <Icon name={done ? "check" : ICONS[stage.stage] || "spark"} size={13} />
            </span>
            <span className="timeline-label">{stage.label}</span>
            {stage.ms != null ? <span className="timeline-ms">{Math.round(stage.ms)} ms</span> : null}
          </li>
        );
      })}
    </ol>
  );
}
