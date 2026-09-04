# Bản đồ pipeline PonyGuard-ViQA (dùng để phân công & trả lời vấn đáp)

Dữ liệu: UIT-ViQuAD2.0. Retriever: e5-small + FAISS. Generator: Gemini (fallback MLX Qwen3-8B-4bit).
3 hệ thống chạy chung 1 retriever + 1 LLM adapter, khác nhau ở tầng quyết định.

---

## 0. Hạ tầng dùng chung (mọi pipeline đều đi qua)

| Bước | Code | Ghi chú |
|---|---|---|
| Chuẩn hoá dataset SQuAD-like → jsonl | [data.py:14](src/ponyguard_viqa/data.py:14) `extract_rows`, `normalize_raw` | gán `expected_action` = ANSWER/ABSTAIN từ `is_impossible` |
| Chunk 400 từ / overlap 50 | [retrieval.py:18](src/ponyguard_viqa/retrieval.py:18) `chunk_text` | |
| Build FAISS IndexFlatIP | [retrieval.py:61](src/ponyguard_viqa/retrieval.py:61) `build_index` | lưu `artifacts/index/` |
| Truy hồi top-k=5 | [retrieval.py:45](src/ponyguard_viqa/retrieval.py:45) `Retriever.retrieve` | query prefix `query: `, casefold trước khi embed; đo `last_timing` |
| Gọi LLM + ép JSON | [llm.py:65](src/ponyguard_viqa/llm.py:65) `LocalLLM.json` / `_extract_json` | 1 lần repair nếu JSON hỏng, thất bại → `_parse_error` (fail closed) |
| Gemini-first + fallback local | [llm.py:190](src/ponyguard_viqa/llm.py:190) `FallbackLLM` | cooldown 120 s khi 429/5xx |
| Chấm điểm | [evaluation.py](src/ponyguard_viqa/evaluation.py) | F1, action accuracy, abstain P/R, hallucination rate |
| Entry point | [scripts/run_system.py](scripts/run_system.py), UI [src/ui/app.py:72](src/ui/app.py:72) | |

---

## 1. Pipeline A — Basic RAG (baseline)

[pipelines.py:87](src/ponyguard_viqa/pipelines.py:87) · prompt `basic_rag_v3.txt` · config `configs/baseline.yaml`

```
question → retrieve(top_k=5) → 1 lần LLM sinh JSON {answer, citation_chunk_ids, evidence_quote}
        → validate_grounding() → hợp lệ ? ANSWER : ABSTAIN
```

Điểm bảo vệ duy nhất: `validate_grounding` [pipelines.py:42](src/ponyguard_viqa/pipelines.py:42) — 4 kiểm tra thuần Python:
citation phải thuộc context, quote phải xuất hiện **nguyên văn** trong chunk, answer phải nằm trong quote, answer không được chỉ lặp lại câu hỏi.
`grounded_generation` [pipelines.py:72](src/ponyguard_viqa/pipelines.py:72) cho phép **đúng 1 lần retry sửa format**.

## 2. Pipeline B — Prompt-Safe RAG (baseline mạnh hơn)

[pipelines.py:101](src/ponyguard_viqa/pipelines.py:101) · prompt `prompt_safe_rag_v3.txt`

Giống A, nhưng LLM tự trả thêm `decision: ANSWER|ABSTAIN`. **Quyết định của model không được tin tuyệt đối**: nếu model nói ANSWER mà grounding sai → ép ABSTAIN ([pipelines.py:110](src/ponyguard_viqa/pipelines.py:110)).
Đây là baseline để chứng minh "chỉ dặn dò trong prompt là chưa đủ".

## 3. Pipeline C — PonyGuard (hệ thống chính)

[pipelines.py:116](src/ponyguard_viqa/pipelines.py:116)–[653](src/ponyguard_viqa/pipelines.py:653) · config `configs/ponyguard.yaml` (`policy_version: dynamic_semantic_policy_v6`, `intent_first: true`)

Đầu ra 3 nhãn: **ANSWER / ASK / ABSTAIN**.

### Luồng chạy (nhánh intent_first = mặc định của UI và bài nộp)

| # | Giai đoạn | Hàm / dòng | Prompt | Vai trò |
|---|---|---|---|---|
| 1 | Giải quyết câu hỏi follow-up | `resolved_question` [core.py:70](src/ponyguard_viqa/core.py:70) | – | câu làm rõ đầy đủ thì thay hẳn câu gốc |
| 2 | **Intent Analysis** | `analyze_intent` [pipelines.py:123](src/ponyguard_viqa/pipelines.py:123) | `intent_analyzer_v2.txt` | rút `entity`, `requested_attribute`, `answer_type`, scope, `slot_bindings` |
| 3 | Ràng buộc slot theo span chữ | `intent_slot_bindings` [core.py:77](src/ponyguard_viqa/core.py:77) | – | slot chỉ "thiếu" khi model trích **nguyên văn** span trong câu hỏi và gán REFERENTIAL, hoặc slot bắt buộc ABSENT |
| 4 | 3 lớp chống ASK bừa | `enforce_requirement_contract` [pipelines.py:256](src/ponyguard_viqa/pipelines.py:256) → `apply_clarity_guard` [pipelines.py:224](src/ponyguard_viqa/pipelines.py:224) → `apply_user_clarification` [pipelines.py:268](src/ponyguard_viqa/pipelines.py:268) | – | không cho hợp đồng intent vừa trích được slot vừa khai slot đó thiếu; không hỏi lại thứ user đã trả lời |
| 5 | Nếu thiếu slot → **ASK sớm**, không truy hồi | [pipelines.py:464](src/ponyguard_viqa/pipelines.py:464) | `clarification_writer_v2.txt` | `refine_clarification` sinh câu hỏi lại bằng **text thuần** (JSON hỏng không làm câu hỏi mơ hồ); có fallback template `clarification_question` [pipelines.py:356](src/ponyguard_viqa/pipelines.py:356) |
| 6 | Retrieval | [pipelines.py:474](src/ponyguard_viqa/pipelines.py:474) | – | top-k = 5 |
| 7 | **Fact Extraction** | `extract_facts` [pipelines.py:135](src/ponyguard_viqa/pipelines.py:135) | `fact_extractor_v1.txt` | trả mảng `support`: chunk_id, evidence_quote, candidate_answer, support_type DIRECT/SIMPLE_INFERENCE |
| 8 | **Relation Verification** | `verify_relations` [pipelines.py:139](src/ponyguard_viqa/pipelines.py:139) | `relation_verifier_v1.txt` | tối đa 2 ứng viên; quan hệ suy luận thì bỏ qua (không nguồn nào phát biểu) |
| 9 | **Bộ lọc tất định (trái tim của PonyGuard)** | `validated_supports` [pipelines.py:655](src/ponyguard_viqa/pipelines.py:655) | – Python thuần | quote có literal trong chunk? premise SUPPORTED? attribute/relation match? answer nằm trong quote? entity trói literal? xung đột số liệu? |
| 9b | Kiểm chứng suy luận số học | `inference_proof_is_valid` [pipelines.py:686](src/ponyguard_viqa/pipelines.py:686) | – | 2 operand phải trích literal, tự **tính lại** sum/difference/ratio, sai số ≤ 0.1 % |
| 9c | Trói thực thể | `entity_binding_is_literal` [pipelines.py:725](src/ponyguard_viqa/pipelines.py:725) | – | chặn "đúng số, sai người" |
| 10 | **Fact recovery** khi không còn support | [pipelines.py:518](src/ponyguard_viqa/pipelines.py:518) | `fact_extractor_v1.txt` | truy hồi lại bằng `entity + attribute`, gộp chunk mới, trích lại 1 lần |
| 11 | Coverage probe khi lệch scope | [pipelines.py:553](src/ponyguard_viqa/pipelines.py:553) | `semantic_evidence_v5.txt` | thêm chunk rồi tái thẩm định |
| 12 | **Policy quyết định** | `decide` [pipelines.py:211](src/ponyguard_viqa/pipelines.py:211) + `scope_matches` [pipelines.py:219](src/ponyguard_viqa/pipelines.py:219) | – | thiếu slot → ASK; thiếu/xung đột/lệch scope/suy luận không được phép → ABSTAIN; còn lại ANSWER |
| 13 | **Relation direction** (chỉ chạy khi sắp ANSWER) | `direction_matches` [pipelines.py:167](src/ponyguard_viqa/pipelines.py:167) | `relation_direction_v1.txt` | so `span_overlap` để bắt hoán vị chủ thể/khách thể; có ngoại lệ câu hỏi định danh |
| 14 | Trả lời | [pipelines.py:605](src/ponyguard_viqa/pipelines.py:605)+ | `basic_rag_v3.txt` | 1 support DIRECT → dùng thẳng `candidate_answer` (**0 lần gọi LLM sinh**); SIMPLE_INFERENCE → dùng kết quả đã tự tính; nhiều support → mới sinh draft |
| 15 | **Claim Verification** | [pipelines.py:643](src/ponyguard_viqa/pipelines.py:643) + `final_gate` [pipelines.py:348](src/ponyguard_viqa/pipelines.py:348) | `claim_verifier_v2.txt` | tách câu trả lời thành claim; giữ claim SUPPORTED/INFERRED_SUPPORTED, không còn claim nào → ABSTAIN |
| 16 | **Từ chối có căn cứ** | `grounded_refusal` [pipelines.py:387](src/ponyguard_viqa/pipelines.py:387) | – | nêu nguồn đã tìm thấy + lý do cụ thể + gợi ý hỏi lại, không nói "corpus không có" |
| 17 | Trace đầy đủ | `PonyGuardState` [core.py:153](src/ponyguard_viqa/core.py:153) | – | requirements/retrieval/evidence/claims/metrics + timing từng stage |

### Nhánh không intent_first (dùng cho ablation)
Bỏ bước 2–5, thay bằng `semantic_evidence_v5.txt` một lượt ([pipelines.py:479](src/ponyguard_viqa/pipelines.py:479)), rồi có thêm 3 cơ chế cứu:
`requirement_recovery_v1` (JSON hỏng), `clarification_adjudicator_v3` (có nên ASK không), `evidence_recovery_v1` (`recover_direct_evidence` [pipelines.py:437](src/ponyguard_viqa/pipelines.py:437)).

### Ablation switch
`enabled = {requirement, inference, verification}` [pipelines.py:119](src/ponyguard_viqa/pipelines.py:119) — tắt lần lượt để đo đóng góp từng tầng (`scripts/run_ablation.py`).

---

## 4. Gợi ý phân công (điền tên vào cột đầu)

| Người | Mảng phụ trách | File/chức năng phải thuộc | Câu thầy dễ hỏi |
|---|---|---|---|
| A | Dữ liệu + Retrieval | `data.py`, `retrieval.py`, `scripts/prepare_data.py`, `build_index.py`, `evaluate_retrieval.py` | Vì sao chunk 400/50? e5 cần prefix query/passage để làm gì? recall@5 và MRR bao nhiêu? |
| B | LLM adapter + hạ tầng chạy | `llm.py`, `configs/*.yaml`, `scripts/run_system.py`, `warm_models.py` | JSON hỏng thì xử lý sao? vì sao Gemini-first mà vẫn giữ MLX? `stage_max_tokens` để làm gì? |
| C | Baselines + Intent/ASK | `BasicRAG`, `PromptSafeRAG`, `analyze_intent`, `intent_slot_bindings`, 3 guard slot, `clarification_writer` | Prompt-safe khác Basic chỗ nào? Làm sao tránh hỏi lại lung tung? Bằng chứng nào cho việc slot bị thiếu? |
| D | Lõi kiểm chứng bằng chứng | `validated_supports`, `entity_binding_is_literal`, `inference_proof_is_valid`, `verify_relations`, `direction_matches` | Vì sao không tin verdict của LLM? Chặn "đúng số sai người" thế nào? Suy luận số học được chứng minh ra sao? |
| E | Policy + Verification + Đánh giá + UI | `decide`, `final_gate`, `grounded_refusal`, `evaluation.py`, `scripts/evaluate_all.py`, `run_ablation.py`, `src/ui/app.py`, `tests/` | ANSWER/ASK/ABSTAIN quyết bằng luật gì? Ablation cho thấy tầng nào quan trọng nhất? Đo hallucination bằng cách nào? |

Nhóm dưới 5 người: gộp A+B (hạ tầng) và C+E (quyết định & đánh giá), giữ D độc lập vì đó là phần đóng góp chính.

## 5. Ba câu chốt để bảo vệ

1. **Đóng góp chính không phải prompt, mà là lớp kiểm chứng tất định bằng Python** — mọi phán quyết của LLM đều bị đối chiếu lại với văn bản gốc (`validated_supports`, `validate_grounding`, `inference_proof_is_valid`).
2. **ASK là nhãn thứ ba thật sự**, chỉ bật khi một slot được trói vào span nguyên văn của câu hỏi — không phải model "thấy mơ hồ" là hỏi.
3. **Từ chối vẫn phải có căn cứ**: `grounded_refusal` trích nguồn đã tìm thấy + lý do + gợi ý thu hẹp, và chỉ khẳng định "evidence đã truy hồi chưa đủ", không khẳng định về toàn corpus.

## 6. Test tương ứng (dẫn chứng khi thầy hỏi "kiểm thử thế nào")

`tests/test_core.py` (chuẩn hoá, khớp quote) · `test_grounding.py` (4 luật grounding) · `test_ambiguity.py` + `test_intent_slot_binding.py` (ASK) · `test_reasoned_evidence.py` + `test_inference_proof_path.py` (suy luận) · `test_relation_direction.py` (hoán vị quan hệ) · `test_behavioral_matrix.py` (ma trận hành vi đầu-cuối).
