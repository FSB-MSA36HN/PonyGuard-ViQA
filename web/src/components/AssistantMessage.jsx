import { useState } from "react";
import Collapsible from "./Collapsible.jsx";
import Icon from "./Icon.jsx";
import StageTimeline from "./StageTimeline.jsx";

const DECISION = {
  ANSWER: { label: "TRẢ LỜI", className: "answer" },
  ASK: { label: "HỎI LẠI", className: "ask" },
  ABSTAIN: { label: "TỪ CHỐI", className: "abstain" },
};

function CopyButton({ value }) {
  const [state, setState] = useState("Sao chép");
  return (
    <button
      type="button"
      className="btn btn-ghost btn-small"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setState("Đã sao chép");
        } catch {
          setState("Không sao chép được");
        }
        setTimeout(() => setState("Sao chép"), 1400);
      }}
    >
      <Icon name="copy" size={13} /> {state}
    </button>
  );
}

export default function AssistantMessage({ message, onPickOption }) {
  const { system, result } = message;
  const { prediction, performance, retrieval = {}, trace = {} } = result;
  const decision = DECISION[prediction.decision] || DECISION.ABSTAIN;
  const grounding = prediction.grounding || {};
  const coverage = trace.coverage || {};
  const requirements = trace.requirements || {};
  const supports = trace.evidence?.valid_supports || [];
  const stages = Object.entries(performance.stages || {}).filter(([, value]) => value && typeof value === "object" && "ms" in value);
  const details = JSON.stringify({ timing: performance.stages || {}, trace }, null, 2);
  const options = prediction.decision === "ASK" ? requirements.clarification_options || [] : [];

  return (
    <article className="message assistant">
      <div className="avatar" aria-hidden="true">
        <Icon name={system === "Basic RAG" ? "spark" : "shield"} size={15} />
      </div>
      <div className="message-body">
        <div className="message-head">
          <span className="pill">{system}</span>
          <span className={`decision ${decision.className}`}>{decision.label}</span>
        </div>
        <div className="answer-text">{prediction.answer}</div>
        {prediction.reason ? <p className="caption">{prediction.reason}</p> : null}

        {options.length ? (
          <div className="chips">
            {options.map((option) => (
              <button key={option} type="button" className="chip" onClick={() => onPickOption(option)}>
                {option}
              </button>
            ))}
          </div>
        ) : null}

        {grounding.evidence_quote ? (
          <Collapsible title="Bằng chứng" badge={(grounding.citation_chunk_ids || []).length || null}>
            <blockquote>{grounding.evidence_quote}</blockquote>
            <p className="caption">Chunk: {(grounding.citation_chunk_ids || []).join(", ")}</p>
            {supports.map((support, index) => (
              <p key={index} className="caption">
                {support.support_type === "SIMPLE_INFERENCE" ? "Suy luận đã kiểm chứng số học" : "Trích dẫn trực tiếp"} · {support.chunk_id}
              </p>
            ))}
          </Collapsible>
        ) : null}

        {prediction.decision === "ABSTAIN" && coverage.coverage_gaps ? (
          <Collapsible title="Vì sao chưa trả lời">
            <p>{coverage.reason_summary}</p>
            {(coverage.supported_facts || []).map((fact) => (
              <div key={fact.chunk_id}>
                <blockquote>{fact.text}</blockquote>
                <p className="caption">
                  {fact.chunk_id}
                  {fact.limitation ? ` · ${fact.limitation}` : ""}
                </p>
              </div>
            ))}
            <ul className="gap-list">
              {(Array.isArray(coverage.coverage_gaps) ? coverage.coverage_gaps : [coverage.coverage_gaps]).map((gap, index) => (
                <li key={index}>{gap}</li>
              ))}
            </ul>
            {coverage.safe_rephrase ? <p className="hint">{coverage.safe_rephrase}</p> : null}
          </Collapsible>
        ) : null}

        {(retrieval.chunk_ids || []).length ? (
          <Collapsible title="Đoạn đã truy hồi" badge={retrieval.chunk_ids.length}>
            {retrieval.chunk_ids.map((chunkId, index) => (
              <div key={chunkId} className="chunk">
                <div className="chunk-head">
                  <code>{chunkId}</code>
                  <span className="caption">score {(retrieval.scores?.[index] ?? 0).toFixed(3)}</span>
                </div>
                <p>{retrieval.texts?.[index]}</p>
              </div>
            ))}
          </Collapsible>
        ) : null}

        <Collapsible title="Chi tiết kỹ thuật">
          <StageTimeline stages={stages.map(([name, value]) => ({ stage: name, label: name, ms: value.ms }))} running={false} />
          <div className="detail-actions">
            <CopyButton value={details} />
          </div>
          <pre className="json">{details}</pre>
        </Collapsible>

        <div className="metrics">
          {Math.round(performance.latency_ms)} ms · {performance.llm_calls} lượt gọi LLM · {performance.input_tokens + performance.output_tokens} token
        </div>
      </div>
    </article>
  );
}
