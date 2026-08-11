# PonyGuard-ViQA — Full Implementation Plan

## 1. Project Overview

### Project name
**PonyGuard-ViQA: A Requirement-Aware Evidence Harness for Hallucination-Resistant Vietnamese Question Answering**

### Core objective
Xây dựng và đánh giá một AI harness mở rộng từ tư tưởng của Ponytail để giảm hallucination trong hệ thống RAG tiếng Việt.

Project phải tạo ra **hai hệ thống chạy trên cùng một dataset và cùng một retrieval setup**:

1. **Baseline RAG**
   - Retrieve tài liệu liên quan.
   - Sinh câu trả lời trực tiếp.
   - Không có evidence gate hoặc controlled inference.

2. **PonyGuard RAG**
   - Phân tích requirement.
   - Kiểm tra evidence.
   - Xác định mức suy luận.
   - Quyết định `ANSWER / ASK / ABSTAIN`.
   - Kiểm tra claim trước khi trả kết quả.

Mục tiêu cuối cùng không phải chỉ tạo chatbot, mà phải tạo được **một benchmark reproducible** chứng minh PonyGuard có giúp:
- Giảm hallucination.
- Giảm unsupported claims.
- Phát hiện tốt câu hỏi không có đáp án.
- Không over-abstain quá mức.
- Đánh đổi bao nhiêu latency và cost so với RAG thông thường.

---

# 2. Final Deliverables

Project hoàn thành khi có đủ các artifact sau:

## 2.1. Source code
Một repository có thể chạy lại toàn bộ pipeline.

## 2.2. Standardized dataset
Một phiên bản UIT-ViQuAD2.0 đã chuẩn hóa cho benchmark, bao gồm:
- Train/development set.
- Validation set.
- Test benchmark cố định.
- Optional clarification set cho `ASK`.

## 2.3. Baseline RAG
Một hệ thống RAG đơn giản nhưng chuẩn để dùng làm baseline.

## 2.4. PonyGuard
Một harness có:
- Requirement Analyzer.
- Retriever.
- Evidence Evaluator.
- Inference Boundary Controller.
- Claim Verifier.
- Decision Gate.

## 2.5. Benchmark runner
Một script chạy cùng một tập test qua:
- Basic RAG.
- Prompt-only RAG.
- PonyGuard.

## 2.6. Evaluation report
Báo cáo có:
- Answer quality.
- Hallucination rate.
- Unsupported claim rate.
- Answer/abstain accuracy.
- Over-abstention.
- Latency.
- Token/cost.

## 2.7. Demo application
Một giao diện đơn giản hiển thị:
- Question.
- Retrieved evidence.
- Requirement analysis.
- Inference level.
- Decision.
- Final answer.
- Verification trace.

---

# 3. Research Question

## Main research question

> Does a requirement-aware evidence harness with controlled inference and claim verification reduce unsupported claims and hallucination in Vietnamese RAG systems compared with standard RAG?

## Secondary questions

1. PonyGuard có phát hiện câu hỏi không thể trả lời tốt hơn Basic RAG không?
2. PonyGuard có giảm hallucination mà không làm over-abstention quá mức không?
3. Requirement analysis có giúp tránh trả lời đúng thông tin nhưng sai entity/attribute không?
4. Controlled inference có giúp giảm suy luận vượt quá context không?
5. Claim verification đóng góp bao nhiêu vào kết quả cuối?
6. Chi phí latency/token tăng bao nhiêu khi thêm harness?

---

# 4. Scope

## In scope

- Vietnamese question answering.
- UIT-ViQuAD2.0.
- Text-only RAG.
- Answerable và unanswerable questions.
- Direct evidence.
- Simple inference.
- Unsupported inference.
- `ANSWER / ASK / ABSTAIN`.
- Claim-level verification.
- Reproducible benchmark.

## Out of scope

Không làm trong phiên bản đầu:

- Multimodal RAG.
- OCR.
- Knowledge graph.
- Fine-tune LLM lớn.
- Training foundation model.
- Web search.
- Multi-agent phức tạp.
- Production authentication.
- Distributed infrastructure.
- Real-time crawling.
- Long-term memory.
- Complex autonomous agents.

Nguyên tắc:

> **Project ưu tiên experimental validity hơn feature count.**

---

# 5. Proposed System Architecture

```text
                         +----------------------+
                         |      User Question   |
                         +----------+-----------+
                                    |
                                    v
                    +-------------------------------+
                    |     Requirement Analyzer      |
                    | entity / attribute / intent   |
                    +---------------+---------------+
                                    |
                                    v
                         +----------------------+
                         |      Retriever       |
                         | vector / hybrid      |
                         +----------+-----------+
                                    |
                                    v
                    +-------------------------------+
                    |      Evidence Evaluator       |
                    | relevance / sufficiency       |
                    | conflict / entity match       |
                    +---------------+---------------+
                                    |
                                    v
                    +-------------------------------+
                    | Inference Boundary Controller |
                    | DIRECT / SIMPLE / UNSUPPORTED  |
                    +---------------+---------------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v                               v
             Evidence sufficient            Evidence insufficient
                    |                               |
                    v                               v
            +---------------+               ASK / ABSTAIN
            | Draft Answer  |
            +-------+-------+
                    |
                    v
            +----------------+
            | Claim Verifier |
            +-------+--------+
                    |
                    v
            +----------------+
            | Decision Gate  |
            +-------+--------+
                    |
          +---------+----------+
          |         |          |
          v         v          v
       ANSWER      ASK       ABSTAIN
```

---


# 5A. Automated Bootstrap Setup

Mục tiêu của phần này là giúp một thành viên mới trong nhóm có thể clone project, lấy source Ponytail và tải dataset UIT-ViQuAD2.0 mà không phải thao tác thủ công nhiều bước.

## 5A.1. Prerequisites

Máy cần có:

```text
Git
Python 3.10+
pip
```

Kiểm tra:

```bash
git --version
python3 --version
pip3 --version
```

---

## 5A.2. Recommended Bootstrap Script

Tạo file:

```text
scripts/bootstrap.sh
```

Nội dung:

```bash
#!/usr/bin/env bash

set -e

echo "======================================"
echo " PonyGuard-ViQA Bootstrap"
echo "======================================"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[1/5] Creating required directories..."

mkdir -p external
mkdir -p data/raw
mkdir -p data/processed
mkdir -p data/benchmark
mkdir -p artifacts/index
mkdir -p runs
mkdir -p reports

echo "[2/5] Cloning Ponytail..."

if [ ! -d "external/ponytail" ]; then
    git clone https://github.com/DietrichGebert/ponytail.git external/ponytail
else
    echo "Ponytail already exists. Skipping clone."
fi

echo "[3/5] Creating Python virtual environment..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "[4/5] Installing Python dependencies..."

python -m pip install --upgrade pip

pip install \
    datasets \
    huggingface_hub \
    pandas \
    numpy \
    scikit-learn \
    sentence-transformers \
    faiss-cpu \
    tqdm \
    pydantic \
    python-dotenv

echo "[5/5] Downloading UIT-ViQuAD2.0..."

python scripts/download_dataset.py

echo "======================================"
echo " Bootstrap completed successfully."
echo "======================================"
echo "Activate environment with:"
echo "source .venv/bin/activate"
```

Cấp quyền chạy:

```bash
chmod +x scripts/bootstrap.sh
```

Chạy toàn bộ bootstrap:

```bash
./scripts/bootstrap.sh
```

---

## 5A.3. Dataset Download Script

Tạo file:

```text
scripts/download_dataset.py
```

Nội dung:

```python
from pathlib import Path
from datasets import load_dataset
import json

DATASET_NAME = "taidng/UIT-ViQuAD2.0"

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def save_split(split_name, split_data):
    output_path = OUTPUT_DIR / f"{split_name}.jsonl"

    with output_path.open("w", encoding="utf-8") as f:
        for row in split_data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Saved {split_name}: {len(split_data)} rows -> {output_path}")

def main():
    print(f"Loading dataset: {DATASET_NAME}")

    dataset = load_dataset(DATASET_NAME)

    print(dataset)

    for split_name, split_data in dataset.items():
        save_split(split_name, split_data)

    print("Dataset download completed.")

if __name__ == "__main__":
    main()
```

Luồng:

```text
Hugging Face
      |
      v
load_dataset("taidng/UIT-ViQuAD2.0")
      |
      v
data/raw/
      |
      +-- train.jsonl
      +-- validation.jsonl
      +-- test.jsonl
```

Nếu dataset không có đủ cả ba split, script sẽ lưu toàn bộ các split thực tế mà Hugging Face cung cấp.

---

## 5A.4. Ponytail Location

Sau khi bootstrap:

```text
ponyguard-viqa/
│
├── external/
│   └── ponytail/
│       ├── ...
│
├── src/
├── data/
└── scripts/
```

Khuyến nghị không chỉnh sửa trực tiếp upstream repo nếu chưa cần.

Luồng nên là:

```text
external/ponytail
       |
       v
Study architecture / skills / hooks
       |
       v
Reimplement or adapt concepts
       |
       v
src/ponyguard/
```

Điều này giúp:

- giữ source Ponytail gốc để đối chiếu,
- dễ cập nhật upstream,
- tránh trộn source nghiên cứu với source dependency,
- mô tả rõ phần nào là Ponytail gốc và phần nào là contribution của nhóm.

---

## 5A.5. Pin Ponytail Version for Reproducibility

Sau khi clone:

```bash
cd external/ponytail
git rev-parse HEAD
cd ../..
```

Lưu commit vào:

```text
configs/dependencies.yaml
```

Ví dụ:

```yaml
ponytail:
  repository: https://github.com/DietrichGebert/ponytail.git
  commit: "<PINNED_COMMIT_HASH>"

dataset:
  name: taidng/UIT-ViQuAD2.0
```

Trong giai đoạn development có thể dùng version mới nhất.

Trước final benchmark phải pin commit để đảm bảo reproducibility.

---

## 5A.6. Dataset Verification

Tạo:

```text
scripts/verify_dataset.py
```

```python
from pathlib import Path
import json

DATA_DIR = Path("data/raw")

def count_jsonl(path):
    count = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            json.loads(line)
            count += 1

    return count

def main():
    files = list(DATA_DIR.glob("*.jsonl"))

    if not files:
        raise RuntimeError("No dataset files found.")

    print("Dataset files:")

    for path in files:
        rows = count_jsonl(path)
        print(f"- {path}: {rows} rows")

    print("Dataset verification passed.")

if __name__ == "__main__":
    main()
```

Chạy:

```bash
python scripts/verify_dataset.py
```

---

## 5A.7. One-Command Setup with Makefile

Có thể thêm:

```text
Makefile
```

```makefile
setup:
	chmod +x scripts/bootstrap.sh
	./scripts/bootstrap.sh

dataset:
	.venv/bin/python scripts/download_dataset.py

verify-data:
	.venv/bin/python scripts/verify_dataset.py

build-index:
	.venv/bin/python scripts/build_index.py

benchmark:
	.venv/bin/python scripts/evaluate_all.py
```

Khi đó một thành viên mới chỉ cần chạy:

```bash
make setup
```

để tự động:

```text
Clone Ponytail
+ Create virtual environment
+ Install dependencies
+ Download UIT-ViQuAD2.0
```

---

## 5A.8. Bootstrap Definition of Done

Bootstrap được coi là hoàn thành khi:

- [ ] `external/ponytail/` tồn tại.
- [ ] Ponytail clone thành công.
- [ ] `.venv/` được tạo.
- [ ] Python dependencies được cài.
- [ ] UIT-ViQuAD2.0 tải thành công.
- [ ] Các split được export vào `data/raw/`.
- [ ] `verify_dataset.py` chạy pass.
- [ ] Ponytail commit được ghi lại trước final benchmark.
- [ ] Một thành viên khác có thể clone project mới và chạy `make setup` thành công.

---

# 6. Experiment Systems

Benchmark tối thiểu cần ba hệ thống.

## System A — Basic RAG

Pipeline:

```text
Question
→ Retrieve top-k
→ LLM answer
```

Prompt chỉ yêu cầu trả lời dựa trên context.

Không có:
- Requirement analysis.
- Confidence gate.
- Claim verification.
- Explicit abstention logic.

Đây là baseline chính.

---

## System B — Prompt-Only Safe RAG

Pipeline:

```text
Question
→ Retrieve top-k
→ Prompt:
   "Only answer if context is sufficient.
    Otherwise say you do not know."
→ Answer
```

Mục tiêu:
- Kiểm tra liệu chỉ thêm instruction chống hallucination đã đủ chưa.
- Tách hiệu quả của prompt khỏi hiệu quả của PonyGuard harness.

---

## System C — PonyGuard

Pipeline:

```text
Question
→ Requirement Analyzer
→ Retrieve
→ Evidence Evaluation
→ Inference Boundary
→ Draft Answer
→ Claim Verification
→ ANSWER / ASK / ABSTAIN
```

Đây là phương pháp đề xuất.

---

# 7. Dataset Strategy

## Dataset
**UIT-ViQuAD2.0**

Các trường cần dùng:

```text
context
question
answers
is_impossible
plausible_answers
```

## Core benchmark mapping

```text
is_impossible = false
→ expected_action = ANSWER

is_impossible = true
→ expected_action = ABSTAIN
```

`plausible_answers` được dùng để tạo các case dễ hallucinate:
- đáp án nghe hợp lý,
- có lexical overlap,
- nhưng không được context hỗ trợ.

---

# 8. Dataset Preparation Plan

## Chunk D1 — Download and inspect dataset

### Tasks
- Download UIT-ViQuAD2.0.
- Kiểm tra schema.
- Kiểm tra số lượng sample.
- Kiểm tra answerable/unanswerable ratio.
- Kiểm tra duplicated questions.
- Kiểm tra encoding tiếng Việt.
- Kiểm tra context length distribution.

### Output
```text
data/raw/
  train.json
  validation.json
  test.json
```

### Done when
Có notebook/report mô tả:
- số mẫu,
- tỷ lệ answerable,
- độ dài context,
- độ dài question,
- missing values,
- duplicate rate.

---

## Chunk D2 — Normalize dataset

Tạo unified schema:

```json
{
  "sample_id": "viquad_000001",
  "question": "...",
  "context": "...",
  "gold_answers": ["..."],
  "is_answerable": true,
  "expected_action": "ANSWER",
  "plausible_answers": [],
  "source": "UIT-ViQuAD2.0"
}
```

### Tasks
- Normalize Unicode.
- Trim whitespace.
- Chuẩn hóa newline.
- Giữ nguyên dấu tiếng Việt.
- Gán unique `sample_id`.
- Convert `is_impossible` thành `is_answerable`.
- Tạo `expected_action`.

### Output
```text
data/processed/viquad_normalized.jsonl
```

---

## Chunk D3 — Create benchmark splits

Không tuning trên test benchmark.

### Recommended split

#### Development
2,000 samples:
- 1,000 answerable.
- 1,000 unanswerable.

Dùng để:
- debug,
- prompt iteration,
- threshold tuning.

#### Validation
1,000 samples:
- 500 answerable.
- 500 unanswerable.

Dùng để:
- chọn config,
- chọn top-k,
- chọn threshold.

#### Final Test
2,000 samples:
- 1,000 answerable.
- 1,000 unanswerable.

Dùng một lần cho benchmark cuối.

### Important
Seed cố định:

```python
RANDOM_SEED = 42
```

### Output
```text
data/benchmark/
  dev.jsonl
  validation.jsonl
  test.jsonl
```

---

# 9. Optional ASK Dataset

UIT-ViQuAD2.0 chủ yếu hỗ trợ `ANSWER/ABSTAIN`.

Để benchmark `ASK`, tạo thêm tập nhỏ khoảng 100–200 câu hỏi.

## Types

### Missing entity

Original:

> Albert Einstein sinh năm bao nhiêu?

Modified:

> Ông ấy sinh năm bao nhiêu?

Expected:

```text
ASK
```

### Missing target attribute

Original:

> Hà Nội có diện tích bao nhiêu?

Modified:

> Hà Nội có bao nhiêu?

Expected:

```text
ASK
```

### Ambiguous reference

> Người này sinh ở đâu?

### Output schema

```json
{
  "sample_id": "clarify_001",
  "question": "Ông ấy sinh năm bao nhiêu?",
  "context": "...",
  "expected_action": "ASK",
  "missing_requirement": "entity"
}
```

### Output
```text
data/benchmark/clarification_test.jsonl
```

### Note
Tập này phải được báo cáo riêng với benchmark chính vì được nhóm tự tạo.

---

# 10. Retrieval Corpus Design

Có hai cách.

## Recommended for academic fairness

Tách toàn bộ `context` thành corpus riêng.

```json
{
  "document_id": "doc_0001",
  "text": "...",
  "metadata": {
    "source": "UIT-ViQuAD2.0"
  }
}
```

Mỗi question không được đưa trực tiếp context gốc vào LLM.

Retriever phải tìm lại context từ corpus.

Điều này giúp benchmark thật sự là RAG.

---

# 11. Chunking Strategy

Phiên bản đầu chỉ benchmark 2 cấu hình.

## Config A
- chunk size: 300–400 tokens.
- overlap: 50 tokens.

## Config B
- chunk size: 500–600 tokens.
- overlap: 80 tokens.

Chọn config tốt nhất trên validation.

Không cần benchmark quá nhiều chunk strategy.

---

# 12. Embedding and Vector Database

## Recommended

### Embedding
Chọn một multilingual/Vietnamese sentence embedding model.

Yêu cầu:
- support Vietnamese,
- local inference được nếu có thể,
- stable,
- không quá lớn.

### Vector DB
**FAISS** là lựa chọn đơn giản nhất.

Lý do:
- local,
- reproducible,
- không cần service,
- dễ export index.

### Output
```text
artifacts/index/
  faiss.index
  documents.jsonl
```

---

# 13. Retriever Benchmark

Trước khi đánh giá hallucination, phải chắc retrieval đủ tốt.

## Metrics

### Recall@k
Gold context có nằm trong top-k không?

Test:

```text
Recall@1
Recall@3
Recall@5
Recall@10
```

### Recommended
Chọn `top_k` bằng validation.

Ví dụ:

```text
top_k = 5
```

### Rule
Cả Basic RAG và PonyGuard phải dùng **cùng một retriever**.

Nếu PonyGuard dùng retriever tốt hơn thì benchmark không công bằng.

---

# 14. Phase 1 — Build Basic RAG

## Chunk R1 — Retriever API

Interface:

```python
retrieve(question, top_k=5)
```

Return:

```json
[
  {
    "document_id": "...",
    "chunk_id": "...",
    "text": "...",
    "score": 0.87
  }
]
```

---

## Chunk R2 — Answer Generator

Input:

```json
{
  "question": "...",
  "contexts": [...]
}
```

Output:

```json
{
  "answer": "...",
  "citations": [...]
}
```

### Prompt rule
Không thêm PonyGuard logic.

Baseline phải càng đơn giản càng tốt.

---

## Chunk R3 — Basic RAG logging

Log mỗi request:

```json
{
  "sample_id": "...",
  "question": "...",
  "retrieved_chunks": [...],
  "answer": "...",
  "latency_ms": 1234,
  "input_tokens": 1000,
  "output_tokens": 100
}
```

### Done when
Có thể chạy:

```bash
python run_basic_rag.py --input data/benchmark/dev.jsonl
```

và sinh:

```text
runs/basic_rag/dev_predictions.jsonl
```

---

# 15. Phase 2 — Prompt-Only Safe RAG

## Goal
Tạo baseline mạnh hơn Basic RAG nhưng chưa có harness.

## Prompt behavior

Model được yêu cầu:

- chỉ dùng context,
- không đoán,
- nếu thiếu bằng chứng thì từ chối.

Output:

```json
{
  "decision": "ANSWER | ABSTAIN",
  "answer": "..."
}
```

### Done when
Có:

```text
runs/prompt_safe_rag/
```

---

# 16. Phase 3 — PonyGuard Core

Đây là phần chính.

---

# 17. Chunk P1 — Requirement Analyzer

## Goal
Biến user question thành một cấu trúc requirement.

### Input

```text
Tiếng Anh có bao nhiêu lớp từ chính?
```

### Output

```json
{
  "entity": "tiếng Anh",
  "requested_attribute": "số lớp từ chính",
  "answer_type": "number",
  "question_clear": true,
  "missing_requirements": []
}
```

### Another example

Input:

```text
Ông ấy sinh năm bao nhiêu?
```

Output:

```json
{
  "entity": null,
  "requested_attribute": "năm sinh",
  "answer_type": "date/year",
  "question_clear": false,
  "missing_requirements": ["entity"]
}
```

### Implementation
Structured LLM output.

### Rule
Nếu:

```text
question_clear = false
```

thì decision candidate:

```text
ASK
```

---

# 18. Chunk P2 — Evidence Evaluator

## Goal
Kiểm tra retrieval có đủ evidence cho requirement không.

### Input
- Requirement object.
- Retrieved chunks.

### Output

```json
{
  "entity_match": true,
  "attribute_match": true,
  "evidence_found": true,
  "evidence_sufficient": true,
  "conflict_detected": false,
  "supporting_chunk_ids": ["chunk_3"],
  "missing_evidence": []
}
```

## Checks

1. Entity có match không?
2. Attribute cần tìm có xuất hiện không?
3. Answer type có match không?
4. Có đủ dữ kiện không?
5. Có conflict không?

### Important
Không dùng retrieval similarity làm evidence sufficiency duy nhất.

---

# 19. Chunk P3 — Inference Boundary Controller

## Goal
Phân loại mức suy luận.

## Initial taxonomy

### DIRECT
Đáp án nằm trực tiếp trong evidence.

### SIMPLE_INFERENCE
Có thể suy ra bằng:
- arithmetic đơn giản,
- nối tối đa 2 facts rõ ràng,
- coreference đơn giản.

### UNSUPPORTED
Phải:
- thêm assumption,
- dùng external knowledge,
- đoán intent,
- suy luận vượt quá evidence.

## Output

```json
{
  "inference_level": "DIRECT",
  "reasoning_allowed": true,
  "reason": "Answer is explicitly stated in chunk_3"
}
```

## Policy

```text
DIRECT
→ continue

SIMPLE_INFERENCE
→ continue + mark as inferred

UNSUPPORTED
→ ABSTAIN
```

---

# 20. Chunk P4 — Decision Planner

Trước khi generate answer:

```json
{
  "decision": "ANSWER",
  "reason": "Evidence sufficient and inference within allowed boundary"
}
```

Possible values:

```text
ANSWER
ASK
ABSTAIN
```

## Decision rules

### ASK
Nếu:
- requirement thiếu thông tin quan trọng.

### ABSTAIN
Nếu:
- evidence không đủ,
- entity mismatch,
- attribute mismatch,
- conflicting evidence,
- inference unsupported.

### ANSWER
Nếu:
- question rõ,
- evidence đủ,
- inference được phép.

---

# 21. Chunk P5 — Draft Answer Generator

Chỉ chạy khi:

```text
decision = ANSWER
```

Input:
- Question.
- Supporting evidence only.
- Inference level.

Output:

```json
{
  "draft_answer": "...",
  "used_chunk_ids": ["chunk_3"]
}
```

Quan trọng:

Không đưa toàn bộ retrieved context nếu Evidence Evaluator đã loại các chunk không hỗ trợ.

---

# 22. Chunk P6 — Claim Extractor

## Goal
Tách answer thành atomic claims.

Example:

```text
"Albert Einstein sinh năm 1879 tại Đức."
```

→

```json
[
  "Albert Einstein sinh năm 1879.",
  "Albert Einstein sinh tại Đức."
]
```

Output:

```json
{
  "claims": [
    {
      "claim_id": "c1",
      "text": "..."
    }
  ]
}
```

---

# 23. Chunk P7 — Claim Verifier

Mỗi claim được đánh giá với supporting evidence.

## Labels

```text
SUPPORTED
CONTRADICTED
UNSUPPORTED
```

Optional:

```text
INFERRED_SUPPORTED
```

### Output

```json
{
  "claims": [
    {
      "claim_id": "c1",
      "label": "SUPPORTED",
      "evidence_chunk_ids": ["chunk_3"]
    }
  ]
}
```

---

# 24. Chunk P8 — Final Safety Gate

## Rules

### All claims supported

```text
ANSWER
```

### Some unsupported claims but removable

Remove unsupported claims and regenerate concise answer.

### Key claim unsupported

```text
ABSTAIN
```

### Contradicted key claim

```text
ABSTAIN
```

### Output schema

```json
{
  "decision": "ANSWER",
  "answer": "...",
  "confidence": 0.91,
  "inference_level": "DIRECT",
  "citations": ["chunk_3"],
  "verification": [...]
}
```

---

# 25. PonyGuard State Object

To make harness testable, maintain one structured state.

```json
{
  "sample_id": "...",
  "question": "...",

  "requirements": {
    "entity": "...",
    "attribute": "...",
    "answer_type": "...",
    "question_clear": true
  },

  "retrieval": {
    "chunks": [...]
  },

  "evidence": {
    "sufficient": true,
    "supporting_chunks": [...]
  },

  "reasoning": {
    "level": "DIRECT",
    "allowed": true
  },

  "decision": "ANSWER",

  "draft_answer": "...",

  "claims": [...],

  "final_answer": "...",

  "metrics": {
    "latency_ms": 0,
    "input_tokens": 0,
    "output_tokens": 0
  }
}
```

Đây là khác biệt giữa một **prompt** và một **harness**.

---

# 26. Recommended Repository Structure

```text
ponyguard-viqa/
│
├── README.md
├── pyproject.toml
├── .env.example
│
├── configs/
│   ├── baseline.yaml
│   ├── prompt_safe.yaml
│   └── ponyguard.yaml
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── benchmark/
│
├── artifacts/
│   └── index/
│
├── src/
│   ├── data/
│   │   ├── download.py
│   │   ├── normalize.py
│   │   └── split.py
│   │
│   ├── retrieval/
│   │   ├── chunker.py
│   │   ├── embedder.py
│   │   ├── index.py
│   │   └── retriever.py
│   │
│   ├── baseline/
│   │   ├── basic_rag.py
│   │   └── safe_prompt_rag.py
│   │
│   ├── ponyguard/
│   │   ├── state.py
│   │   ├── requirement_analyzer.py
│   │   ├── evidence_evaluator.py
│   │   ├── inference_controller.py
│   │   ├── decision_gate.py
│   │   ├── answer_generator.py
│   │   ├── claim_extractor.py
│   │   ├── claim_verifier.py
│   │   └── pipeline.py
│   │
│   ├── evaluation/
│   │   ├── answer_metrics.py
│   │   ├── action_metrics.py
│   │   ├── hallucination_metrics.py
│   │   ├── cost_metrics.py
│   │   └── benchmark_runner.py
│   │
│   └── ui/
│       └── app.py
│
├── scripts/
│   ├── build_index.py
│   ├── run_basic_rag.py
│   ├── run_safe_rag.py
│   ├── run_ponyguard.py
│   └── evaluate_all.py
│
├── runs/
│   ├── basic_rag/
│   ├── prompt_safe/
│   └── ponyguard/
│
├── reports/
│   ├── figures/
│   ├── tables/
│   └── final_results.md
│
└── tests/
```

---

# 27. Configuration Standard

Ví dụ:

```yaml
model:
  provider: openai_or_local
  name: model_name
  temperature: 0

retrieval:
  top_k: 5
  chunk_size: 400
  chunk_overlap: 50

ponyguard:
  enable_requirement_analysis: true
  enable_evidence_check: true
  enable_inference_boundary: true
  enable_claim_verification: true

benchmark:
  seed: 42
```

Tất cả experiment phải lưu config.

---

# 28. Benchmark Output Schema

Mỗi system phải output cùng schema tối thiểu.

```json
{
  "sample_id": "viquad_001",
  "system": "ponyguard",

  "question": "...",

  "gold": {
    "expected_action": "ANSWER",
    "answers": ["..."]
  },

  "prediction": {
    "decision": "ANSWER",
    "answer": "..."
  },

  "retrieval": {
    "chunk_ids": [...],
    "scores": [...]
  },

  "performance": {
    "latency_ms": 1450,
    "input_tokens": 1200,
    "output_tokens": 90
  }
}
```

PonyGuard có thể có thêm trace.

---

# 29. Evaluation Metrics

## 29.1. Retrieval

```text
Recall@1
Recall@3
Recall@5
MRR
```

---

## 29.2. Answer quality

Cho answerable samples:

```text
Exact Match
Token F1
```

Optional:
- semantic similarity.

---

## 29.3. Action quality

Binary benchmark:

```text
ANSWER
ABSTAIN
```

Metrics:

```text
Accuracy
Precision
Recall
F1
```

Đặc biệt report:

```text
Unanswerable Detection Precision
Unanswerable Detection Recall
Unanswerable Detection F1
```

---

## 29.4. Hallucination

### Unsupported Claim Rate

```text
unsupported claims / total generated claims
```

### Hallucinated Answer Rate

```text
answers containing >=1 unsupported or contradicted claim
/
total answered samples
```

### False Answer Rate

System trả lời dù sample phải `ABSTAIN`.

---

## 29.5. Over-abstention

```text
answerable questions incorrectly abstained
/
all answerable questions
```

Đây là metric bắt buộc.

Nếu PonyGuard từ chối mọi thứ thì hallucination thấp nhưng hệ thống vô dụng.

---

## 29.6. ASK benchmark

Optional clarification set:

```text
ASK accuracy
ASK precision
ASK recall
```

---

## 29.7. Efficiency

```text
Mean latency
P50 latency
P95 latency
Mean input tokens
Mean output tokens
Estimated cost/question
LLM calls/question
```

---

# 30. Main Benchmark Table

Final report phải có bảng dạng:

| Metric | Basic RAG | Prompt-Safe RAG | PonyGuard |
|---|---:|---:|---:|
| Answer EM | | | |
| Answer F1 | | | |
| Unanswerable F1 | | | |
| Hallucinated Answer Rate | | | |
| Unsupported Claim Rate | | | |
| Over-Abstention Rate | | | |
| Mean Latency | | | |
| Tokens / Question | | | |
| LLM Calls / Question | | | |

---

# 31. Breakdown Analysis

Không chỉ report average.

## Breakdown 1 — Answerable vs Unanswerable

```text
Answerable
Unanswerable
```

## Breakdown 2 — Retrieval success

```text
Gold evidence retrieved
Gold evidence not retrieved
```

Mục tiêu:
Phân biệt hallucination do retrieval và hallucination do generation.

## Breakdown 3 — Question difficulty

Optional:

```text
Direct
Simple inference
Unsupported
```

## Breakdown 4 — Answer length

Optional:
- short,
- medium,
- long.

---

# 32. Ablation Study

Ablation giúp project có tính học thuật hơn.

Chạy PonyGuard theo các cấu hình:

## Full PonyGuard

```text
Requirement
+ Evidence
+ Inference
+ Claim verification
```

## Minus Requirement

```text
Evidence
+ Inference
+ Claim verification
```

## Minus Inference Boundary

```text
Requirement
+ Evidence
+ Claim verification
```

## Minus Claim Verification

```text
Requirement
+ Evidence
+ Inference
```

Report:

| Variant | Hallucination Rate | Unanswerable F1 | Over-Abstention |
|---|---:|---:|---:|
| Full | | | |
| - Requirement | | | |
| - Inference | | | |
| - Claim Verification | | | |

Mục tiêu:
Biết module nào thực sự tạo giá trị.

---

# 33. Error Analysis

Random sample khoảng 100 lỗi của PonyGuard.

Gán category:

```text
RETRIEVAL_FAILURE
ENTITY_MISMATCH
ATTRIBUTE_MISMATCH
EVIDENCE_FALSE_POSITIVE
EVIDENCE_FALSE_NEGATIVE
OVER_ABSTENTION
VERIFIER_FALSE_POSITIVE
VERIFIER_FALSE_NEGATIVE
UNSUPPORTED_INFERENCE
ANSWER_GENERATION_ERROR
```

Báo cáo:
- số lượng,
- tỷ lệ,
- ví dụ,
- nguyên nhân,
- hướng cải thiện.

---

# 34. Testing Strategy

## Unit tests

### Retriever
- top-k đúng format.
- deterministic với fixed index.

### Requirement Analyzer
- parse valid JSON.
- detect missing entity.

### Evidence Evaluator
- direct evidence case.
- missing evidence case.

### Inference Controller
- DIRECT.
- SIMPLE.
- UNSUPPORTED.

### Decision Gate
- ASK.
- ABSTAIN.
- ANSWER.

### Claim Verifier
- supported.
- contradicted.
- unsupported.

---

# 35. Prompt Versioning

Mọi prompt phải có version:

```text
requirement_analyzer_v1
evidence_checker_v1
claim_verifier_v1
```

Không sửa prompt trực tiếp mà không ghi version.

Run metadata:

```json
{
  "prompt_versions": {
    "requirement": "v2",
    "evidence": "v3",
    "claim_verifier": "v1"
  }
}
```

---

# 36. Reproducibility Rules

Mọi experiment phải cố định:

```text
dataset version
sample ids
random seed
embedding model
LLM model
temperature
top-k
chunk size
prompts
thresholds
```

Không thay model giữa Basic RAG và PonyGuard trong main comparison.

Main benchmark phải so sánh **cùng LLM**.

---

# 37. Development Milestones

## Milestone 0 — Repository setup

### Tasks
- Init repo.
- Python environment.
- Config system.
- Logging.
- `.env.example`.
- README skeleton.

### Deliverable
Project chạy được `hello benchmark`.

---

## Milestone 1 — Dataset ready

### Tasks
- Download.
- Normalize.
- Split.
- EDA.
- Freeze benchmark IDs.

### Deliverable
```text
data/benchmark/
```

### Exit criteria
Không thay đổi final test set sau milestone này.

---

## Milestone 2 — Retrieval ready

### Tasks
- Corpus.
- Chunking.
- Embedding.
- FAISS index.
- Recall@k evaluation.

### Exit criteria
Retriever đạt mức recall đủ dùng trên validation.

Nếu retrieval quá thấp, sửa trước khi làm RAG.

---

## Milestone 3 — Basic RAG ready

### Tasks
- Basic prompt.
- Answer generator.
- Logging.
- Dev benchmark.

### Deliverable
Baseline metrics đầu tiên.

---

## Milestone 4 — Prompt-Safe RAG ready

### Tasks
- Add abstention instruction.
- Structured decision.
- Benchmark.

### Deliverable
Baseline số 2.

---

## Milestone 5 — PonyGuard requirement + evidence

### Tasks
- Requirement Analyzer.
- Evidence Evaluator.
- State object.
- Trace logging.

### Deliverable
PonyGuard có thể quyết định evidence đủ/chưa đủ.

---

## Milestone 6 — Controlled inference

### Tasks
- Inference taxonomy.
- Boundary prompt/rules.
- Policy gate.

### Deliverable
`DIRECT / SIMPLE_INFERENCE / UNSUPPORTED`.

---

## Milestone 7 — Claim verification

### Tasks
- Atomic claim extraction.
- Supported/unsupported/contradicted verifier.
- Final safety gate.

### Deliverable
End-to-end PonyGuard.

---

## Milestone 8 — Full benchmark

### Tasks
Chạy:

```text
Basic RAG
Prompt-Safe RAG
PonyGuard
```

trên cùng final test set.

### Deliverable
Raw predictions + metrics.

---

## Milestone 9 — Ablation + error analysis

### Deliverable
- Ablation table.
- Error taxonomy.
- Failure examples.

---

## Milestone 10 — Demo UI

### UI layout

#### Left
- Question input.
- Ask button.

#### Center
- Final answer.
- Decision.
- Confidence.

#### Right
- Requirement.
- Retrieved chunks.
- Evidence result.
- Inference level.
- Claim verification.

### Important
Có toggle:

```text
Basic RAG
PonyGuard
```

để demo cùng một câu hỏi.

---

## Milestone 11 — Final report

Report structure:

```text
1. Introduction
2. Problem Definition
3. Related Work
4. Dataset
5. Baseline RAG
6. PonyGuard Architecture
7. Experimental Setup
8. Results
9. Ablation Study
10. Error Analysis
11. Limitations
12. Conclusion
```

---

# 38. Suggested Work Breakdown by Implementation Chunk

Nếu làm theo từng task nhỏ:

## Chunk 01
Repository + config + logging.

## Chunk 02
Download UIT-ViQuAD2.0.

## Chunk 03
EDA + data quality.

## Chunk 04
Normalize dataset.

## Chunk 05
Freeze benchmark splits.

## Chunk 06
Build corpus.

## Chunk 07
Chunk corpus.

## Chunk 08
Generate embeddings.

## Chunk 09
Build FAISS index.

## Chunk 10
Evaluate Recall@k.

## Chunk 11
Implement Basic RAG.

## Chunk 12
Run Basic RAG dev benchmark.

## Chunk 13
Implement Prompt-Safe RAG.

## Chunk 14
Benchmark Prompt-Safe RAG.

## Chunk 15
Create PonyGuard state schema.

## Chunk 16
Implement Requirement Analyzer.

## Chunk 17
Implement Evidence Evaluator.

## Chunk 18
Implement Inference Boundary Controller.

## Chunk 19
Implement Decision Gate.

## Chunk 20
Implement Draft Answer Generator.

## Chunk 21
Implement Claim Extractor.

## Chunk 22
Implement Claim Verifier.

## Chunk 23
Implement Final Safety Gate.

## Chunk 24
End-to-end PonyGuard dev run.

## Chunk 25
Tune on validation only.

## Chunk 26
Freeze config.

## Chunk 27
Run final Basic RAG benchmark.

## Chunk 28
Run final Prompt-Safe benchmark.

## Chunk 29
Run final PonyGuard benchmark.

## Chunk 30
Calculate all metrics.

## Chunk 31
Ablation experiments.

## Chunk 32
Error analysis.

## Chunk 33
Create charts and tables.

## Chunk 34
Build Streamlit/Gradio demo.

## Chunk 35
Write report.

## Chunk 36
Prepare presentation/demo script.

---

# 39. Priority Levels

## Must-have

- Dataset normalization.
- Retrieval.
- Basic RAG.
- Prompt-Safe RAG.
- Requirement Analyzer.
- Evidence Evaluator.
- ANSWER/ABSTAIN.
- Claim verification.
- Benchmark.
- Hallucination metrics.
- Over-abstention metrics.
- Final report.

## Should-have

- Controlled inference.
- UI trace.
- Ablation.
- Error analysis.

## Nice-to-have

- ASK dataset.
- Hybrid retrieval.
- Separate NLI verifier.
- Local open-source LLM.
- Confidence calibration.
- Advanced visualization.

Nếu thiếu thời gian, cắt Nice-to-have trước.

---

# 40. MVP Definition

MVP tối thiểu:

```text
UIT-ViQuAD2.0
      ↓
Shared Retriever
      ↓
Basic RAG vs PonyGuard
      ↓
PonyGuard:
Requirement → Evidence Check → Answer/Abstain → Claim Verify
      ↓
Benchmark
```

MVP cần chứng minh được:

> PonyGuard giảm false answer/hallucination trên unanswerable questions so với Basic RAG mà không làm giảm quá mạnh khả năng trả lời các câu answerable.

---

# 41. Success Criteria

Project được xem là có kết quả tích cực nếu PonyGuard:

1. Giảm **Hallucinated Answer Rate** so với Basic RAG.
2. Tăng **Unanswerable Detection F1**.
3. Giảm **Unsupported Claim Rate**.
4. Không có **Over-Abstention Rate** quá cao.
5. Answer F1 trên answerable samples không giảm nghiêm trọng.
6. Chi phí latency/token vẫn ở mức hợp lý.
7. Ablation cho thấy ít nhất một module PonyGuard có đóng góp đo được.

Không cần PonyGuard thắng mọi metric.

Một kết quả kiểu:

> hallucination giảm mạnh nhưng latency tăng 2.2x

vẫn là kết quả nghiên cứu hợp lệ nếu được phân tích rõ.

---

# 42. Key Research Risks

## Risk 1 — Retrieval failure

Nếu retriever không lấy được gold context thì PonyGuard không thể trả lời đúng.

### Mitigation
Report riêng:

```text
retrieval-success subset
retrieval-failure subset
```

---

## Risk 2 — Verifier hallucination

LLM verifier cũng có thể đánh giá sai.

### Mitigation
- Structured labels.
- Temperature 0.
- Separate verifier prompt.
- Manual audit một subset.
- Optional NLI baseline.

---

## Risk 3 — Over-abstention

Harness quá nghiêm và từ chối nhiều câu đúng.

### Mitigation
Tune trên validation.

Bắt buộc report over-abstention.

---

## Risk 4 — Benchmark leakage

Không dùng final test để chỉnh prompt.

### Mitigation
Freeze sample IDs sớm.

---

## Risk 5 — Baseline unfairness

Không để PonyGuard dùng:
- model tốt hơn,
- retrieval tốt hơn,
- context nhiều hơn

trong main comparison.

---

## Risk 6 — Too many LLM calls

PonyGuard có thể quá chậm.

### Mitigation
Target:

```text
Basic RAG: 1 generation call
PonyGuard: 3–5 calls maximum
```

Có thể merge:
- requirement + evidence planning,
- claim extraction + verification

nếu cần.

---

# 43. Recommended First Version of PonyGuard

Để đơn giản nhất:

## Call 1
Requirement Analysis.

## Retrieval
Không phải LLM call.

## Call 2
Evidence Evaluation + Inference Level + Decision.

Nếu `ABSTAIN/ASK`:
stop.

## Call 3
Generate answer.

## Call 4
Claim Verification + final answer correction.

Tổng tối đa:

```text
4 LLM calls/question
```

Đây là cấu hình cân bằng tốt cho project môn học.

---

# 44. Example End-to-End Trace

## Input

```text
Ngôn ngữ Ấn-Âu có bao nhiêu lớp từ?
```

## Requirement Analyzer

```json
{
  "entity": "ngôn ngữ Ấn-Âu",
  "requested_attribute": "số lớp từ",
  "answer_type": "number",
  "question_clear": true
}
```

## Retrieved document

```text
"Tiếng Anh có bảy lớp từ chính..."
```

## Evidence Evaluator

```json
{
  "entity_match": false,
  "attribute_match": true,
  "evidence_sufficient": false,
  "reason": "Evidence describes English, not the whole Indo-European family."
}
```

## Inference Controller

```json
{
  "inference_level": "UNSUPPORTED",
  "reasoning_allowed": false
}
```

## Final decision

```text
ABSTAIN
```

## Final answer

```text
Tài liệu hiện có chỉ cung cấp thông tin về tiếng Anh và không đủ
để xác định số lớp từ của toàn bộ nhóm ngôn ngữ Ấn-Âu.
```

Basic RAG có thể lấy con số "7" và trả lời sai.

Đây là loại case project muốn đo.

---

# 45. Final Experiment Protocol

## Step 1
Freeze final test dataset.

## Step 2
Freeze retriever.

## Step 3
Freeze LLM model.

## Step 4
Freeze prompts/config.

## Step 5
Run Basic RAG.

## Step 6
Run Prompt-Safe RAG.

## Step 7
Run PonyGuard.

## Step 8
Calculate metrics bằng cùng một evaluator.

## Step 9
Run manual audit trên random subset.

Recommended:

```text
100–200 samples
```

## Step 10
Generate final tables/charts.

---

# 46. Final Presentation Story

Slide/demo nên kể câu chuyện theo thứ tự:

## Problem
RAG vẫn hallucinate khi retrieval có vẻ liên quan nhưng evidence không đủ.

## Baseline
Basic RAG:

```text
retrieve → answer
```

## Insight
`Relevant evidence` không đồng nghĩa với `sufficient evidence`.

## Proposed Solution
PonyGuard:

```text
understand requirement
→ retrieve
→ verify evidence
→ constrain inference
→ verify claims
→ answer / ask / abstain
```

## Experiment
Cùng:
- dataset,
- model,
- retriever,
- test set.

Khác:
- harness.

## Result
So sánh:
- hallucination,
- answer quality,
- abstention,
- latency.

## Contribution
Không train một LLM mới.

Project nghiên cứu:

> **Liệu một evidence-aware AI harness có thể kiểm soát hành vi của LLM tốt hơn một RAG pipeline và prompt thông thường hay không?**

---

# 47. Definition of Done

Project hoàn thành khi:

- [ ] UIT-ViQuAD2.0 đã được chuẩn hóa.
- [ ] Benchmark split đã freeze.
- [ ] Shared retriever đã build.
- [ ] Recall@k đã được đo.
- [ ] Basic RAG chạy end-to-end.
- [ ] Prompt-Safe RAG chạy end-to-end.
- [ ] PonyGuard Requirement Analyzer hoàn thành.
- [ ] Evidence Evaluator hoàn thành.
- [ ] Inference Boundary hoàn thành.
- [ ] Decision Gate hoàn thành.
- [ ] Claim Verifier hoàn thành.
- [ ] PonyGuard chạy end-to-end.
- [ ] Mọi system chạy trên cùng final test set.
- [ ] Metrics được tính tự động.
- [ ] Có bảng benchmark cuối.
- [ ] Có ablation study.
- [ ] Có error analysis.
- [ ] Có demo Basic RAG vs PonyGuard.
- [ ] Có README hướng dẫn reproduce.
- [ ] Có báo cáo kết quả cuối.

---

# 48. Recommended Development Order

Thứ tự triển khai được khuyến nghị:

```text
DATA
 ↓
RETRIEVAL
 ↓
BASIC RAG
 ↓
BENCHMARK INFRASTRUCTURE
 ↓
PROMPT-SAFE RAG
 ↓
PONYGUARD REQUIREMENT ANALYZER
 ↓
EVIDENCE EVALUATOR
 ↓
ANSWER / ABSTAIN GATE
 ↓
CONTROLLED INFERENCE
 ↓
CLAIM VERIFICATION
 ↓
VALIDATION + TUNING
 ↓
FREEZE
 ↓
FINAL BENCHMARK
 ↓
ABLATION
 ↓
ERROR ANALYSIS
 ↓
DEMO
 ↓
REPORT
```

Không nên xây UI trước benchmark.

Không nên tối ưu PonyGuard trước khi Basic RAG và evaluation pipeline hoạt động.

---

# 49. Minimal Team Split

Nếu nhóm 3 người:

## Member 1 — Data + Retrieval
- Dataset.
- Preprocessing.
- Embeddings.
- FAISS.
- Retrieval metrics.

## Member 2 — PonyGuard
- Requirement.
- Evidence.
- Inference.
- Verification.

## Member 3 — Benchmark + Demo
- Baselines.
- Evaluation runner.
- Metrics.
- UI.
- Report figures.

Cả nhóm cùng:
- prompt design,
- experiment interpretation,
- paper/report.

---

# 50. One-Sentence Project Definition

> **PonyGuard-ViQA builds a structured evidence-aware harness around a Vietnamese RAG system so that the model must understand what evidence is required, verify whether that evidence exists, limit unsupported inference, and validate generated claims before deciding to answer, ask for clarification, or abstain.**
