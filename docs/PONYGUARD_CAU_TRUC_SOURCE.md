# PonyGuard-ViQA — Cấu trúc source code

> Tài liệu tra cứu nhanh khi bị hỏi *"file này chứa gì, dùng làm gì?"*

---

## `src/ponyguard_viqa/` — thư viện lõi

| File | Dòng | Chứa gì | Dùng làm gì |
| --- | ---: | --- | --- |
| **`pipelines.py`** | 919 | 3 class `BasicRAG`, `PromptSafeRAG`, `PonyGuard` + toàn bộ tầng kiểm tra | **File quan trọng nhất.** Chứa cả 3 hệ so sánh và 5 tầng của PonyGuard. Chuỗi 7 bước kiểm tra bằng code nằm ở `validated_supports()`. |
| **`core.py`** | 194 | Schema `Requirement`, `Chunk`, enum slot, hàm so khớp nguyên văn | Định nghĩa **hợp đồng dữ liệu** và các hàm kiểm tra chuỗi tất định. `intent_slot_bindings()` ở đây — nơi quyết định câu hỏi có đủ thông tin hay không. |
| **`llm.py`** | 230 | `LocalLLM` (MLX), `GeminiLLM` (REST), `FallbackLLM` | Adapter gọi model. Có **circuit breaker**: provider chết thì ngưng thử 120s thay vì timeout ở từng stage. Ghi lại provider thật phục vụ mỗi call. |
| **`retrieval.py`** | 112 | `Embedder` + `Retriever` | Truy xuất bằng FAISS trên embedding `multilingual-e5-small`. **Dense thuần, không có BM25.** Đo và ghi thời gian từng bước. |
| **`evaluation.py`** | 90 | Hàm `metrics()`, `audit_claims()`, `f1()` | Tính toàn bộ chỉ số báo cáo. `audit_claims()` gọi thêm LLM để kiểm claim của các câu đã trả lời. |
| **`data.py`** | 113 | Chuẩn bị dữ liệu, `verify_frozen_split()` | Chia và đóng băng dataset, xác thực bằng hash manifest để không ai vô tình tinh chỉnh trên tập test. |

### Các hàm cần nhớ trong `pipelines.py`

| Hàm | Tầng | Vai trò |
| --- | --- | --- |
| `analyze_intent()` | 1 | Gọi model phân tích câu hỏi, rồi để code tự tính `question_clear` |
| `extract_facts()` | 2 | Trích bằng chứng kèm quote nguyên văn |
| `verify_relations()` | 3 | Gán nhãn `MATCH` / `CONTRADICTED` / `UNSTATED` |
| `validated_supports()` | 4 | **Chuỗi 7 điều kiện `if/elif`** — nơi ra quyết định thật |
| `inference_proof_is_valid()` | 5b | Tính lại phép toán bằng Python |
| `direction_matches()` | 5c | So chiều quan hệ, chặn đảo chủ ngữ–tân ngữ |

---

## `prompts/` — hợp đồng đầu ra của model

Mỗi file là **một contract**: yêu cầu model trả JSON đúng schema. Đánh version
(`_v1`, `_v2`…) và ghi vào metadata mỗi lần chạy để truy vết được.

| File | Dòng | Dùng cho | Yêu cầu gì |
| --- | ---: | --- | --- |
| `intent_analyzer_v2.txt` | 36 | Tầng 1 | Khai từng slot + span copy nguyên văn từ câu hỏi + nhãn `RESOLVED`/`REFERENTIAL`/`ABSENT` |
| `fact_extractor_v1.txt` | 13 | Tầng 2 | Mỗi bằng chứng phải có chunk_id, quote nguyên văn, đáp án, loại `DIRECT`/`SIMPLE_INFERENCE` |
| `relation_verifier_v1.txt` | 11 | Tầng 3 | Trả 1 trong 3 nhãn, kèm chiều mâu thuẫn nếu có |
| `relation_direction_v1.txt` | 17 | Tầng 5c | Trích bộ ba (chủ ngữ, quan hệ, tân ngữ) cho **cả** câu hỏi và nguồn |
| `basic_rag_v3.txt` | 4 | Basic RAG | Sinh câu trả lời + citation. Baseline. |
| `prompt_safe_rag_v3.txt` | 3 | Prompt-Safe RAG | Như trên + dặn tự từ chối khi thiếu bằng chứng |
| `claim_verifier_v2.txt` | 1 | Audit | Chấm từng claim của câu trả lời là `SUPPORTED` hay không |
| `clarification_writer_v2.txt` | 3 | Nhánh ASK | Viết câu hỏi lại cụ thể, không lặp lại câu hỏi gốc |

*Các file `_v1`, `_v3`, `semantic_evidence_*` còn lại là phiên bản cũ giữ để đối
chiếu, không nằm trong đường chạy chính.*

---

## `src/ui/` — demo

| File | Dòng | Dùng làm gì |
| --- | ---: | --- |
| `app.py` | 314 | App Streamlit để demo trực quan. Cache retriever và model bằng `@st.cache_resource` nên không nạp lại mỗi câu. Cho chọn provider (local / Gemini) và hiện đầy đủ trace: quyết định, citation, lý do từ chối. |

---

## `scripts/` — công cụ chạy

| File | Dùng làm gì |
| --- | --- |
| **`run_system.py`** | Chạy **một** hệ trên một file input. Có cờ `--model` để **ghim provider** — bắt buộc dùng khi chạy chẩn đoán. |
| **`evaluate_all.py`** | Chạy **cả 3 hệ** trên benchmark rồi xuất bảng so sánh. Đây là script tạo ra kết quả trong báo cáo. |
| **`measure_judgement_stages.py`** | Đo riêng tầng intent và tầng verify **mà không chạy cả pipeline**. Công cụ chẩn đoán rẻ, dùng để bác bỏ giả thuyết trước khi viết code. |
| `report_live_diagnostics.py` | Sinh báo cáo Markdown từ file dự đoán của 3 bộ chẩn đoán |
| `prepare_data.py` · `build_index.py` | Chia dữ liệu, chunk hoá, build FAISS index |
| `download_dataset.py` · `verify_dataset.py` | Tải UIT-ViQuAD và xác thực hash |
| `error_analysis.py` · `run_ablation.py` | Phân tích lỗi và chạy ablation từng thành phần |
| `warm_models.py` · `bootstrap.sh` | Nạp sẵn model, cài môi trường |

---

## `configs/` — cấu hình

| File | Chứa gì |
| --- | --- |
| **`base.yaml`** | Cấu hình gốc: model `Qwen3-8B-MLX-4bit`, embedding `multilingual-e5-small`, `top_k: 5`, chunk 400/overlap 50, token budget từng stage |
| `ponyguard.yaml` | `extends: base.yaml` + bật `intent_first: true` và 4 cờ kiểm tra |
| `baseline.yaml` · `prompt_safe.yaml` | Cấu hình 2 hệ so sánh — **kế thừa cùng `base.yaml`** nên chắc chắn dùng chung corpus, retriever, model |

Việc cả 3 config cùng `extends: base.yaml` chính là thứ đảm bảo so sánh công bằng.

---

## `data/` — dữ liệu

### `data/benchmark/` — bộ đóng băng

`test.jsonl` (2.000 câu) · `dev.jsonl` · `validation.jsonl`, mỗi file kèm
`.manifest.json` chứa hash. Script sẽ **từ chối chạy** nếu hash không khớp.

### `data/diagnostics/` — 3 bộ chẩn đoán

| File | Số câu | Vai trò |
| --- | ---: | --- |
| `ponyguard_behavioral_live.jsonl` | 26 | **Tuned** — dùng lúc phát triển, luôn lạc quan hơn thực tế |
| `ponyguard_holdout_live.jsonl` | 10 | **Held-out** — chưa từng dùng để chỉnh hệ thống |
| `ponyguard_safety_holdout.jsonl` | 12 | **Safety** — 9 câu bẫy + **3 câu đúng chiều** làm đối chứng |

Ba câu đối chứng trong bộ safety là để một hệ "cứ từ chối hết" không thể đạt
điểm tuyệt đối.

---

## `tests/` — 138 test tất định

Dùng **model kịch bản** (scripted), không gọi mạng, chạy dưới 1 giây. Kiểm tra
**contract** chứ không kiểm tra độ thông minh của model.

| File | Dòng | Kiểm tra gì |
| --- | ---: | --- |
| `test_intent_slot_binding.py` | 333 | Tầng 1: span binding, phân biệt `ABSENT` vs `REFERENTIAL`, **các ca phản chứng** |
| `test_ambiguity.py` | 313 | Nhánh ASK, clarity guard, xử lý câu trả lời làm rõ của người dùng |
| `test_grounding.py` | 215 | Citation, quote nguyên văn, tính bất biến của answer plan |
| `test_core.py` | 156 | Hàm chuỗi và schema trong `core.py` |
| `test_behavioral_matrix.py` | 124 | Ma trận quyết định `ANSWER`/`ASK`/`ABSTAIN` cho mọi tổ hợp đầu vào |
| `test_inference_proof_path.py` | 124 | Tầng 5b: số học, toán hạng giả, phép nối vô căn cứ |
| `test_relation_direction.py` | 110 | Tầng 5c: đảo vai, câu hỏi đồng nhất, circuit breaker |
| `test_reasoned_evidence.py` | 100 | Ranh giới suy luận và từ chối có căn cứ |

---

## `runs/` và `reports/` — kết quả

`runs/<hệ>/*.jsonl` chứa **trace đầy đủ** từng câu: quyết định, chunk truy xuất,
lý do loại từng bằng chứng, thời gian và provider của **từng stage**. Đây là thứ
cho phép mọi kết luận trong báo cáo đều truy ngược được.

`reports/` chứa bảng metric và báo cáo Markdown sinh tự động.

---

## Nếu chỉ được nhớ 3 file

1. **`pipelines.py`** — toàn bộ kiến trúc và 3 hệ so sánh
2. **`core.py`** — nơi code (chứ không phải model) ra quyết định
3. **`configs/base.yaml`** — bằng chứng cả 3 hệ chạy cùng điều kiện
