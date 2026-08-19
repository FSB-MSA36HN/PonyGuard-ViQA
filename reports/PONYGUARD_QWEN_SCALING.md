# Judgement-stage capability by provider

Intent and relation probed in isolation. Intent runs the production path;
relation replays candidates a recorded run produced. Read-only measurement.

## intent

| Provider | Served by | Correct | Errors | Failing cases |
| --- | --- | ---: | ---: | --- |
| `mlx-community/Qwen2.5-3B-Instruct-4bit` | `local:mlx-community/Qwen2.5-3B-Instruct-4bit` | 23/36 | 0 | `live_answer_percentage`, `live_answer_person`, `live_answer_definition`, `live_answer_time`, `live_abstain_event`, `live_ask_attribute`, `live_ask_country`, `live_ask_scope`, `live_ask_time`, `live_ask_location`, `hold_ask_location_missing_country`, `hold_ask_location_family_country`, `hold_abstain_unsupported_join` |
| `mlx-community/Qwen2.5-7B-Instruct-4bit` | `local:mlx-community/Qwen2.5-7B-Instruct-4bit` | 23/36 | 0 | `live_answer_percentage`, `live_ask_attribute`, `live_ask_entity`, `live_ask_country`, `live_ask_target`, `live_ask_scope`, `live_ask_time`, `live_ask_location`, `hold_ask_location_missing_country`, `hold_ask_date_referential_time`, `hold_ask_location_family_country`, `hold_ask_entity_unbounded`, `hold_inference_two_chunks` |
