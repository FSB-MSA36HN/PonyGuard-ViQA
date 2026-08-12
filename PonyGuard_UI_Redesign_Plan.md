# PonyGuard UI Redesign Plan

## Outcome

Replace the form-and-columns demo with a conversational AI workspace: a persistent chat timeline, a model-style system picker, visible local-processing status, and evidence/trace details that stay out of the main answer path.

## Scope

1. Use Streamlit native `chat_message`, `chat_input`, `status`, session state, and CSS only; add no UI dependency.
2. Make **Basic RAG** and **PonyGuard** appear as selectable AI modes in the sidebar. The selection affects the next message and is shown on each assistant reply.
3. Preserve the existing `ASK` follow-up semantics: the next user message is merged as clarification, then retried against retrieval/evidence rather than treated as a fact.
4. Render decisions, grounding, evidence quote, timing, and trace in compact expandable panels.
5. Add an empty-chat welcome screen with example prompts, a New chat action, and responsive styling.

## Interaction flow

```text
choose AI mode → ask in chat input → local processing status
→ assistant answer/ASK/ABSTAIN card → optional evidence + trace
→ clarification input (only after ASK) → retrieve and evaluate again
```

## Safety and performance

- Reuse the existing shared model/retriever cache.
- Do not render invalid grounding as a factual answer.
- Do not fabricate per-stage progress; show a genuine local-processing state and report measured stage timings after completion.
- Keep full trace optional to avoid overwhelming normal chat use.

## Verification

- Compile the Streamlit app.
- Run the existing test suite and mock benchmark smoke.
- Start Streamlit and verify its health/startup output.
