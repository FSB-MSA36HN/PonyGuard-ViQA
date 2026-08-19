# Judgement-stage capability by provider

Intent and relation probed in isolation. Intent runs the production path;
relation replays candidates a recorded run produced. Read-only measurement.

## Provenance warning

An earlier version of this report listed a `gemini-3.6-flash` column with
identical scores and an identical failing-case list to `local`. That column was
**invalid**: `FallbackLLM` degraded every Gemini call to the local model on
`429`, and the harness did not record which provider served each call. All 36
intent bindings were byte-identical across the two columns, which is what
exposed it. The harness now builds each named provider with **no fallback** and
records `served_by` per probe, so a degraded column reports errors instead of
another model's results.

Re-measured with the fixed harness, `gemini-3.6-flash` returns
`Gemini temporarily unavailable (429)` on all 36 intent probes. **The cross-provider comparison is
currently blocked by quota and remains unmeasured.**

## intent — local only (validated)

| Provider | Served by | Correct | Errors | Failing cases |
| --- | --- | ---: | ---: | --- |
| `local` | `local:Qwen/Qwen3-8B-MLX-4bit` | 29/36 | 0 | `live_ask_attribute`, `live_ask_entity`, `live_ask_scope`, `live_ask_time`, `hold_ask_location_missing_country`, `hold_ask_location_family_country`, `hold_abstain_unsupported_join` |

## relation — local only (validated)

| Provider | Served by | Correct | Errors | Failing cases |
| --- | --- | ---: | ---: | --- |
| `local` | `local:Qwen/Qwen3-8B-MLX-4bit` | 14/17 | 0 | `live_answer_person`, `hold_inference_two_chunks`, `hold_abstain_reversed_actor` |
