# PonyGuard-ViQA — Thuyết minh kỹ thuật

> **Mục đích:** dàn ý kỹ thuật đầy đủ, dùng làm khung viết báo cáo môn học hoặc
> paper. Mỗi mục tương ứng một section trong bài viết cuối; ánh xạ sang cấu trúc
> paper ở [Mục 11](#11-gợi-ý-cấu-trúc-paper).
>
> **Quy ước thuật ngữ:** giữ nguyên tiếng Anh cho các thuật ngữ đã chuẩn trong
> ngành (retrieval, grounding, citation, precision, recall, abstain…). Chỉ dịch
> khi tiếng Việt thực sự rõ nghĩa hơn.

---

## 1. Tóm tắt

Hệ hỏi–đáp tiếng Việt dựa trên retrieval (RAG) có một khuyết tật về mặt thiết
kế: **nó luôn sinh câu trả lời**. Khi tài liệu không chứa đáp án, khi câu hỏi mơ
hồ, hoặc khi câu hỏi mang tiền đề sai, model vẫn tạo ra một câu trả lời trôi
chảy kèm citation hợp lệ.

PonyGuard-ViQA đề xuất một kiến trúc trong đó **quyết định chấp nhận câu trả lời
do code đưa ra**, còn LLM chỉ làm việc trích xuất và đề xuất. Hệ thống chọn một
trong ba hành động — `ANSWER` / `ASK` / `ABSTAIN` — mỗi hành động gắn với một
điều kiện kiểm tra được.

Trên UIT-ViQuAD 2.0, PonyGuard giảm tỷ lệ trả lời câu không nên trả lời từ
**0.402 xuống 0.134** so với RAG baseline, đồng thời nâng precision (khi hệ
thống chọn trả lời thì có đúng chỗ không) từ **0.530 lên 0.705** — cho thấy cải
thiện đến từ **khả năng phân biệt**, không phải từ việc siết ngưỡng cho an toàn.
Cái giá là recall giảm và chi phí tính toán tăng khoảng 1.9 lần.

---

## 2. Đặt vấn đề

### 2.1 Ba loại câu hỏi không nên trả lời

| Loại | Ví dụ | Hành động đúng |
| --- | --- | --- |
| Tài liệu không có đáp án | Khái niệm ngoài corpus | `ABSTAIN` |
| Câu hỏi thiếu thông tin để xác định | *"Quốc khánh là ngày nào?"* | `ASK` |
| Câu hỏi có tiền đề sai | Đảo chủ ngữ với tân ngữ | `ABSTAIN` |

**Điểm cần nhấn:** loại 2 khác hẳn loại 1 và 3. Gộp chung là sai về thiết kế —
hỏi lại người dùng không giải quyết được việc corpus thiếu dữ liệu; ngược lại,
từ chối thẳng một câu hỏi mơ hồ sẽ che mất việc người dùng chỉ cần nói rõ thêm
một chi tiết là trả lời được.

### 2.2 Ca minh họa — lỗi qua được mọi kiểm tra bề mặt

Câu hỏi: *"Tập đoàn Lend Lease được Làng Olympic xây dựng ở đâu?"*
Nguồn: *"Làng Olympic nằm ở Thung lũng Lower Lea **do tập đoàn Lend Lease xây
dựng**."*

Câu hỏi đã **đảo chủ ngữ với tân ngữ**. Hệ thống trả lời *"Thung lũng Lower
Lea"*, và:

- thực thể được hỏi **có** trong nguồn ✓
- quote **nguyên văn** ✓
- đáp án **nằm trong** quote ✓
- citation trỏ đúng chunk ✓

Mọi ràng buộc ở mức từ ngữ đều thỏa. Cái sai nằm ở **ai làm gì với ai** — thứ mà
so khớp chuỗi không nhìn thấy. Ca này được dùng xuyên suốt tài liệu như một phép
thử chẩn đoán.

### 2.3 Chi phí hai loại lỗi không ngang nhau

Trong tra cứu chuyên ngành:

- **Từ chối nhầm** → người dùng mất công tra tay. Thiệt hại có giới hạn, và
  **nhìn thấy được**.
- **Trả lời sai kèm citation** → người dùng tin và làm theo. Thiệt hại không
  giới hạn, và **không ai biết**.

Vì vậy hàm mục tiêu **không phải** accuracy trung bình, mà là giảm loại lỗi thứ
hai với ràng buộc giữ recall ở mức chấp nhận được.

---

## 3. Phát biểu bài toán

Cho câu hỏi $q$ và corpus $\mathcal{C}$, hệ thống trả về bộ ba $(a, c, e)$:
$a$ là hành động, $c$ là tập chunk được cite, $e$ là quote nguyên văn.

$$a \in \{\texttt{ANSWER}, \texttt{ASK}, \texttt{ABSTAIN}\}$$

Điều kiện để chấp nhận `ANSWER` — phải thỏa **đồng thời**:

1. $e$ xuất hiện **nguyên văn** trong một chunk $d \in c$, với $d \in \mathcal{C}$;
2. giá trị đáp án nằm trong $e$;
3. thực thể được hỏi khớp được với **cả** $q$ lẫn $d$;
4. quan hệ được hỏi được $d$ **nói ra** (không mâu thuẫn, không vắng mặt);
5. chiều của quan hệ trong $d$ **khớp** chiều trong $q$.

Điều kiện cho `ASK`: tồn tại một thông tin bắt buộc mà **bản thân $q$** không xác
định. Lưu ý điều kiện này **không tham chiếu tới $\mathcal{C}$** — đây là một
quyết định thiết kế, bàn ở [Mục 5.1](#51-tầng-1--phân-tích-intent).

`ABSTAIN` là hành động mặc định khi không thỏa điều kiện nào ở trên.

---

## 4. Thiết kế thực nghiệm

### 4.1 Ba hệ so sánh

| Hệ | Cơ chế | Đại diện cho |
| --- | --- | --- |
| **Basic RAG** | Retrieve → sinh | Baseline |
| **Prompt-Safe RAG** | Retrieve → sinh, prompt bảo model tự từ chối | Cách phổ biến: dặn dò bằng prompt |
| **PonyGuard** | Kiểm tra nhiều tầng, quyết định bằng code | Đề xuất của nghiên cứu |

Cả ba dùng **cùng corpus, cùng retriever, cùng top-k, cùng schema output, cùng
model nền**. Chỉ khác nhau ở cơ chế kiểm tra. Thiết kế này cô lập biến cần đo và
cho phép quy chênh lệch về đúng nguyên nhân.

- So **1 ↔ 2**: dặn dò bằng prompt có đủ không?
- So **2 ↔ 3**: kiểm tra có cấu trúc đóng góp thêm bao nhiêu?

### 4.2 Dữ liệu và hạ tầng

| Thành phần | Cấu hình |
| --- | --- |
| Dataset | UIT-ViQuAD 2.0, split đóng băng, verify bằng hash manifest |
| Corpus | ~5.442 chunk, kích thước 400 token, overlap 50 |
| Embedding | `intfloat/multilingual-e5-small` |
| Index | FAISS, top-k = 5 |
| Model nền | `Qwen3-8B` (MLX, 4-bit), temperature 0 |
| Ghim provider | Bắt buộc, ghi vào metadata mỗi lần chạy |

**Lưu ý phương pháp:** cơ chế fallback provider tự động từng âm thầm chuyển
model giữa chừng và tạo ra một so sánh vô nghĩa. Từ đó mọi lần chạy đều ghim cố
định một model và **ghi lại model nào thực sự phục vụ từng call**.

---

## 5. Kiến trúc PonyGuard

**Nguyên tắc:** LLM *đề xuất*, code *quyết định*.

Lý do: phán đoán của LLM không ổn định theo cách diễn đạt — trong thực nghiệm,
cùng một cặp thực thể với hai cách hỏi khác nhau cho hai kết quả khác nhau. Code
thì cùng input luôn ra cùng output. Phần bảo đảm an toàn được đặt trên nền code.

```
q ──► [1] Intent ──(thiếu thông tin)──► ASK
        │
        └─(rõ)─► [2] Retrieve ─► [3] Trích xuất ─► [4] Verify quan hệ
                                                          │
                                   ┌──────────────────────┘
                                   ▼
                           [5] Kiểm tra bằng code ──(fail)──► ABSTAIN
                                   │
                                   ├─► [5b] Tính lại phép toán (nếu suy luận)
                                   ├─► [5c] Kiểm tra chiều quan hệ
                                   ▼
                              Answer plan bị khóa ─► ANSWER
```

### 5.1 Tầng 1 — Phân tích intent

Chạy **trước** khi retrieve. Lý do: nếu quyết định `ASK` đến sau, hệ thống sẽ hỏi
lại chỉ vì không tìm thấy bằng chứng — nhưng thiếu bằng chứng là điều kiện của
`ABSTAIN`, không phải của `ASK`.

Contract output yêu cầu, cho **từng** thông tin trong câu hỏi:

```json
{"slot": "entity | requested_attribute | country | location | time | scope | reference | target",
 "span": "<chuỗi copy nguyên văn từ câu hỏi>",
 "status": "RESOLVED | REFERENTIAL | ABSENT"}
```

Code sau đó kiểm tra:

- `span` có thật là chuỗi con của câu hỏi không (chuẩn hóa khoảng trắng, hoa
  thường);
- `status` có nằm trong enum không;
- và **tự tính** kết luận "câu hỏi đã đủ thông tin chưa".

Model **không được** tự tuyên bố câu hỏi đã hoàn chỉnh.

**Phân biệt then chốt:** `ABSENT` (câu hỏi không ràng buộc chiều này — bình
thường) khác `REFERENTIAL` (câu hỏi có nhắc tới nhưng chưa xác định — cần hỏi
lại). Gộp hai cái thì hệ thống sẽ hỏi lại chỉ vì câu hỏi không nêu năm hay quốc
gia.

**Hướng fail an toàn:** contract hỏng, span không khớp, hoặc `ABSENT` trên chiều
tùy chọn đều **không** sinh `ASK`. Tầng này chỉ có thể chuyển `ABSTAIN → ASK` khi
model đưa ra một span nguyên văn và gán nhãn chưa xác định.

### 5.2 Tầng 2–3 — Retrieve và trích xuất có ràng buộc

Mỗi bằng chứng phải kèm: chunk id, **quote nguyên văn**, giá trị đáp án ứng viên,
loại bằng chứng (`DIRECT` | `SIMPLE_INFERENCE`), và cặp span thực thể (trong câu
hỏi / trong nguồn). Không được diễn giải lại, không được ghép thông tin ngoài
tài liệu.

### 5.3 Tầng 4 — Verify quan hệ

Enum ba giá trị: `MATCH` / `CONTRADICTED` / `UNSTATED`.

- `CONTRADICTED`: nguồn nói về thực thể khác, thuộc tính khác, chiều chủ ngữ –
  tân ngữ khác, loại đại lượng khác, hoặc phạm vi khác.
- `UNSTATED`: tiền đề cần thiết vắng mặt, hoặc tham chiếu chưa được xác định.
- `MATCH`: toàn bộ quan hệ được hỏi, gồm cả chiều và phạm vi, đều được nguồn nói
  ra.

Chỉ `MATCH` mới cho phép chấp nhận bằng chứng `DIRECT`.

### 5.4 Tầng 5 — Kiểm tra bằng code

Chuỗi kiểm tra chạy tuần tự, mọi bước phải qua:

| # | Kiểm tra | Loại bỏ khi |
| --- | --- | --- |
| 1 | Chunk được cite có tồn tại trong tập retrieve | chunk id bịa |
| 2 | Quote xuất hiện nguyên văn trong chunk đó | diễn giải lại |
| 3 | Tiền đề câu hỏi ở trạng thái `SUPPORTED` | tiền đề sai |
| 4 | Thuộc tính và quan hệ khớp | trả lời lệch câu hỏi |
| 5 | Giá trị đáp án nằm trong quote | bịa số liệu |
| 6 | Thực thể khớp cả câu hỏi lẫn nguồn | nhầm thực thể |
| 7 | Đáp án không chỉ lặp lại câu hỏi | trả lời rỗng |

**Khóa answer plan:** khi một bằng chứng `DIRECT` qua hết, bộ ba (đáp án, quote,
citation) bị **khóa**. Tầng sinh câu chữ phía sau chỉ được diễn đạt lại, không
được thay hay bỏ. Ràng buộc này chặn một lỗi đã gặp thật: bằng chứng verify xong
lại bị tầng viết câu trả lời làm hỏng.

### 5.5 Tầng 5b — Nhánh chứng minh suy luận

Với `SIMPLE_INFERENCE`, contract yêu cầu:

```json
{"operation": "sum | difference | ratio",
 "operands": [{"value": "...", "chunk_id": "...", "evidence_quote": "..."},
              {"value": "...", "chunk_id": "...", "evidence_quote": "..."}],
 "result": "...", "unit": "..."}
```

Code kiểm tra: mỗi số hạng phải cite chunk có thật, quote nguyên văn, giá trị nằm
trong quote, và **có liên quan tới câu hỏi**; sau đó phép toán được **tính lại
bằng code** và so với `result` theo sai số tương đối.

Lý do tầng này phải bỏ qua việc verify quan hệ tổng hợp: xem
[Mục 8.1](#81-phát-hiện-1--hỏi-sai-câu-hỏi-ở-tầng-verify).

### 5.6 Tầng 5c — Kiểm tra chiều quan hệ

Chỉ chạy trên nhánh **sắp trả lời**. Model trích bộ ba (chủ ngữ, quan hệ, tân
ngữ) cho **câu hỏi** và cho **nguồn**; code so bằng độ trùng token nguyên văn.
Nếu chủ ngữ trong câu hỏi trùng với **tân ngữ** của nguồn nhiều hơn là trùng với
chủ ngữ của nguồn ⇒ quan hệ bị đảo ⇒ loại bằng chứng.

Hòa hoặc thiếu span thì **giữ nguyên** (fail an toàn theo hướng không tạo từ chối
giả). Đo được: 0 lần báo nhầm trên 8 lần chạy, bắt được 1/2 ca đảo vai đã biết.

---

## 6. Cấu trúc repo

```
PonyGuard-ViQA/
├── src/ponyguard_viqa/
│   ├── core.py          # Schema, ràng buộc slot, hàm so khớp nguyên văn
│   ├── pipelines.py     # Ba pipeline + toàn bộ tầng kiểm tra
│   ├── retrieval.py     # FAISS + embedder
│   ├── evaluation.py    # Bộ metric
│   └── llm.py           # Adapter model, ghi nhận provider thực tế
├── prompts/             # Contract output, đánh version (v1, v2, …)
├── configs/             # base.yaml + config từng hệ
├── data/
│   ├── benchmark/       # Split đóng băng + hash manifest
│   └── diagnostics/     # 3 bộ test chẩn đoán (Mục 7)
├── scripts/
│   ├── run_system.py                # Chạy một hệ
│   ├── evaluate_all.py              # Benchmark cả ba hệ
│   ├── report_live_diagnostics.py
│   └── measure_judgement_stages.py  # Đo riêng từng tầng, không chạy pipeline
└── tests/               # 136 test deterministic (model scripted, không gọi mạng)
```

Ba điểm đáng nêu trong báo cáo:

- **Contract prompt được đánh version** và ghi vào metadata mỗi lần chạy, nên mọi
  kết quả truy ngược được về đúng phiên bản prompt.
- **`measure_judgement_stages.py`** cho phép đo riêng tầng intent và tầng verify
  quan hệ **mà không chạy cả pipeline** — công cụ chẩn đoán rẻ, dùng để bác bỏ
  giả thuyết trước khi viết code.
- **136 test deterministic** dùng model scripted, kiểm tra *contract* chứ không
  kiểm tra độ thông minh của model.

---

## 7. Cách đánh giá

### 7.1 Bốn bộ test, vai trò khác nhau

| Bộ | Cỡ | Vai trò |
| --- | ---: | --- |
| **Benchmark đóng băng** | 2.000 | Kết quả báo cáo (nghiên cứu này dùng mẫu 200) |
| **Chẩn đoán — tuned** | 26 | Dùng lúc phát triển → **luôn lạc quan hơn thực tế** |
| **Chẩn đoán — held-out** | 10 | Chưa từng dùng để chỉnh |
| **Chẩn đoán — safety** | 12 | Đảo quan hệ, sai thuộc tính, sai mốc thời gian |

Bộ safety **cố ý có 3 câu đúng chiều**. Không có chúng, một hệ thống ngu ngốc
kiểu "cứ từ chối hết" sẽ đạt điểm tuyệt đối. Chi tiết này nên nêu rõ trong paper.

### 7.2 Bộ metric

| Nhóm | Metric |
| --- | --- |
| An toàn | `false_answer_rate` (trả lời câu gold không-trả-lời-được), `hallucinated_answer_rate` (claim bị auditor bác) |
| Độ bao phủ | `recall`, `over_abstention_rate` |
| Khả năng phân biệt | precision, **balanced accuracy** |
| Grounding | `grounding_validity_rate`, `citation_coverage` |
| Chi phí | số lần gọi LLM, latency median / p90 |

**Cảnh báo dễ nhầm:** `false_answer_rate` và `hallucinated_answer_rate` có **mẫu
số khác nhau** — cái đầu tính trên các câu gold không-trả-lời-được, cái sau tính
trên các câu hệ thống đã trả lời. Nhầm hai cái này là lỗi báo cáo rất dễ mắc.

---

## 8. Các phát hiện kỹ thuật

### 8.1 Phát hiện 1 — Hỏi sai câu hỏi ở tầng verify

Với câu hỏi kiểu *"chênh lệch giữa A và B là bao nhiêu?"*, tầng verify nhận được
câu hỏi: *"nguồn có nói về quan hệ **chênh lệch** không?"* và luôn trả lời không.

Câu trả lời đó **đúng về mặt logic**. Không nguồn nào nói ra một quan hệ **được
suy ra**; nếu nguồn đã nói rồi thì bài toán không còn là suy luận nữa. Việc đặt
câu hỏi đó cho tầng verify là hỏi một câu **về bản chất nó không thể trả lời khác
được**.

Hệ quả: bộ kiểm tra số học được cài đặt đúng nhưng **không bao giờ chạy tới** —
bằng chứng đã bị loại ở tầng trước.

**Cách sửa:** với câu suy luận, thay việc verify quan hệ tổng hợp bằng
(a) verify **từng số hạng** — mỗi số hạng là một dữ kiện nguồn nói thẳng ra — và
(b) **tính lại phép toán bằng code**.

Kết quả **chặt hơn**, không lỏng hơn: bốn bước kiểm tra độc lập thay cho một
phán đoán của model. Đã verify trên dữ liệu chưa từng thấy với hai số hạng nằm ở
**hai chunk khác nhau**.

> **Tổng quát hóa:** một tầng verify chỉ hoạt động khi ta hỏi nó đúng mệnh đề mà
> nó có thể phán được. Áp tiêu chí verify trực tiếp lên một quan hệ được suy ra
> thì luôn thất bại, bất kể model mạnh đến đâu.

### 8.2 Phát hiện 2 — Câu hỏi mơ hồ chỉ lộ ra khi nhìn vào evidence

Các câu như *"Thủ đô nằm ở đâu?"* hoặc *"Dân số Hà Nội **khi đó** là bao nhiêu?"*
**hoàn chỉnh về mặt ngữ pháp**. Cái thiếu là **không xác định được đang nói tới
cái nào**.

Kiểm chứng bằng cách đọc trực tiếp các chunk retrieve được:

- Câu mơ hồ: **nhiều** chunk cùng trả lời quan hệ được hỏi nhưng cho giá trị khác
  nhau, phân biệt bởi một chiều mà câu hỏi chưa xác định. Ví dụ *"dân số Hà Nội
  khi đó"*: 53 nghìn (1954), 132.145 (thập niên 1940), ~8 triệu (hiện đại).
- Câu trả lời được: **đúng một** chunk nói về quan hệ đó.

Tín hiệu phân biệt **tồn tại** và **phân biệt được**.

**Nhưng đây là một mâu thuẫn thiết kế chưa giải quyết:** quyết định `ASK` phải
đến *trước* khi retrieve ([Mục 5.1](#51-tầng-1--phân-tích-intent)), trong khi tín
hiệu này chỉ có *sau* khi retrieve. Ngoài ra, thực nghiệm cho thấy pipeline hiện
tại **gộp** nhiều đáp án về một bằng chứng duy nhất trước mọi điểm quyết định,
nên tín hiệu bị mất trước khi dùng được.

### 8.3 Phát hiện 3 — Lỗi này không giảm khi tăng size model

Đo riêng tầng intent trên ba model local, cùng bộ 36 câu:

| Model | Kết quả |
| --- | ---: |
| Qwen2.5-3B-Instruct-4bit | 23/36 |
| Qwen2.5-7B-Instruct-4bit | 23/36 |
| Qwen3-8B-MLX-4bit | 29/36 |

3B → 7B **phẳng**; 7B → 8B là đổi thế hệ chứ không phải đổi size. Quan trọng hơn
tổng điểm: **năm câu sai trên cả ba model**. Chênh lệch đến từ các câu khác dao
động; phần lõi khó thì không đổi.

**Ý nghĩa:** khoanh vùng được đâu là **giới hạn kiến trúc** (sửa được bằng thiết
kế) và đâu là **giới hạn năng lực model** (phải đổi model). Kết luận: các câu
đang chặn hệ thống không thuộc loại giải quyết được bằng cách tăng tham số.

### 8.4 Phát hiện 4 — Bằng chứng định lượng về overfitting ở mức thiết kế luật

Trong quá trình phát triển, nhóm thêm hai luật để xử lý các ca quan sát được. Cả
hai đều viết **tổng quát** — không chứa thực thể, không chứa cụm từ tiếng Việt cụ
thể — nên thỏa ràng buộc "không hard-code" về mặt hình thức.

Sau đó nhóm viết các **test phản chứng**, cố tình thiết kế để **bác bỏ** đặc tả
của chính hai luật đó. Ví dụ: *"Thủ đô của **nước đó** nằm ở đâu?"* — hỏi về địa
điểm nhưng "nước đó" chưa xác định; hành động đúng là `ASK`. Cả hai luật đều nuốt
mất câu hỏi lại chính đáng này.

Gỡ hai luật ra:

| Bộ test | Ảnh hưởng |
| --- | --- |
| Tuned | **−1 câu** |
| Held-out | **không đổi** |
| Safety | **không đổi** |

Toàn bộ giá trị của chúng nằm trên chính bộ dữ liệu chúng được thiết kế dựa
theo, và bằng không trên dữ liệu mới.

> **Bài học:** ràng buộc "không hard-code" là **cần nhưng chưa đủ**. Một luật viết
> tổng quát vẫn là fit test nếu nó được **chọn** bằng cách xem nó sửa được câu
> nào. Muốn đủ thì phải có held-out set + test phản chứng cho từng luật.

---

## 9. Kết quả

Test set đóng băng UIT-ViQuAD 2.0, mẫu 200 câu (103 trả lời được / 97 không),
ghim model `Qwen3-8B` local, không fallback.

### 9.1 Phân bố hành động

| Hệ | `ANSWER` | `ABSTAIN` | `ASK` | Trả lời câu không nên trả lời |
| --- | ---: | ---: | ---: | ---: |
| Basic RAG | 83 | 117 | 0 | 39 / 97 |
| Prompt-Safe RAG | 72 | 128 | 0 | 31 / 97 |
| **PonyGuard** | 44 | 130 | 26 | **13 / 97** |

### 9.2 Metric chính

| Metric | Basic | Prompt-Safe | **PonyGuard** |
| --- | ---: | ---: | ---: |
| `false_answer_rate` ↓ | 0.402 | 0.320 | **0.134** |
| Specificity (từ chối đúng) ↑ | 0.598 | 0.680 | **0.866** |
| Precision ↑ | 0.530 | 0.569 | **0.705** |
| Recall ↑ | 0.427 | 0.398 | 0.301 |
| **Balanced accuracy** ↑ | 0.513 | 0.539 | **0.583** |
| `unanswerable_f1` ↑ | 0.542 | 0.587 | **0.599** |
| `answer_f1` ↑ | 0.153 | **0.187** | 0.126 |
| `grounding_validity_rate` | 1.000 | 1.000 | 1.000 |
| Số lần gọi LLM | 2.17 | 2.27 | 4.03 |
| Latency median | 11.7 s | 11.2 s | 24.8 s |
| Latency p90 | 29.6 s | 31.8 s | 49.9 s |

### 9.3 Phân biệt tốt hơn, hay chỉ siết ngưỡng?

Đây là câu phản biện quan trọng nhất. Nếu PonyGuard chỉ đơn thuần nhát hơn, thì
**precision gần như không đổi** trong khi recall sụt.

Thực tế: precision tăng **0.530 → 0.705** (tăng 33% tương đối), và **balanced
accuracy tăng 0.513 → 0.583**. Cả hai cho thấy hệ thống đi **ra khỏi** đường
trade-off cũ, chứ không trượt dọc theo nó.

Đối chiếu: Prompt-Safe chỉ tăng precision 0.530 → 0.569 trong khi over-abstention
tăng — đúng kiểu "nhát hơn chứ không tinh hơn".

### 9.4 Recall mất ở đâu

Trong 72 câu trả lời được mà PonyGuard bỏ sót:

| Nguyên nhân | Số câu | Nghĩa là |
| --- | ---: | --- |
| Đáp án gold **không có** trong chunk nào retrieve được | 34 | **Giới hạn retriever** — chung cho cả ba hệ |
| Đáp án gold **có** trong context | 38 | **Kiểm tra quá chặt** — thuộc về PonyGuard |

Tính theo giới hạn retriever (đáp án nằm trong context ≈ 54/103 cho cả ba hệ):

| Hệ | Bắt được / retrieve được |
| --- | ---: |
| Basic RAG | 44 / 54 = **81%** |
| Prompt-Safe RAG | 41 / 54 = **76%** |
| PonyGuard | 31 / 53 = **58%** |

**Đây là phân tích quan trọng nhất của nghiên cứu.** Nó cho thấy khoảng một nửa
phần recall bị mất **không phải** do PonyGuard mà do retriever — giới hạn chung
của cả ba hệ chỉ khoảng 52% số câu trả lời được. Phần còn lại (58% so với 81% của
baseline) mới là cái giá thật của việc kiểm tra chặt, và là mục tiêu cải thiện rõ
ràng.

---

## 10. Hạn chế và hướng phát triển

### 10.1 Hạn chế

1. **Vẫn còn hai câu trả lời sai** trên bộ test độc lập: một câu đảo chủ ngữ –
   tân ngữ được chấp nhận, và một câu có mốc thời gian chưa xác định vẫn được trả
   lời. Cả hai có citation hợp lệ, tức là qua được **toàn bộ** các bước kiểm tra
   hiện có. Chưa đạt mục tiêu thiết kế.
2. **Tỷ lệ lọt của lỗi đảo quan hệ ≈ 30% và lúc được lúc không** — cùng cặp thực
   thể, đổi cách diễn đạt thì lúc chặn được lúc lọt.
3. **Chi phí ~1.9×** về số lần gọi LLM và ~2.1× về latency median.
4. **Recall giảm 30% tương đối** so với baseline; một nửa do giới hạn retriever,
   một nửa do kiểm tra chặt.
5. **Kết quả trên mẫu 200/2000**; sai số ~±3.5 điểm phần trăm. Bản đầy đủ cần
   ~20 giờ chạy local.
6. **`answer_f1` thấp hơn Prompt-Safe** (0.126 vs 0.187) — một phần do recall
   thấp, một phần do PonyGuard xuất quote nguyên văn ngắn gọn nên bị thiệt khi
   chấm token-F1 với đáp án gold diễn đạt tự do.
7. **So sánh năng lực giữa các provider chưa xong** do hết quota API.

### 10.2 Hướng phát triển

| Hướng | Cơ sở |
| --- | --- |
| **Hỏi model nhiều lần, yêu cầu tất cả đồng ý** | Lỗi đảo quan hệ lọt ~30% và không ổn định ⇒ yêu cầu $k$ lần thống nhất sẽ giảm mạnh tỷ lệ lọt |
| **Chuyển guard sang fail-closed** | Hiện các guard fail-open; với hệ ưu tiên an toàn thì nên bắt buộc có bằng chứng dương |
| **Verify từ phía đáp án** thay vì phía nguồn | Hai lần bắt model trích vai từ nguồn đều thất bại; ghép mệnh đề hoàn chỉnh rồi hỏi nguồn có suy ra được không là việc dễ hơn |
| **Retrieval hai tầng** (rộng → rerank) | Giới hạn retriever chỉ ~52% là trần trên của mọi hệ |
| **Route theo năng lực từng tầng** | Chỉ khi có phép đo cross-provider hợp lệ |

---

## 11. Gợi ý cấu trúc paper

| Section | Lấy từ mục |
| --- | --- |
| Abstract | 1 |
| 1. Introduction | 2.1, 2.2, 2.3 |
| 2. Problem Formulation | 3 |
| 3. Related Work | *cần bổ sung* — selective prediction, abstention in QA, RAG faithfulness |
| 4. Method | 5 (toàn bộ) |
| 5. Experimental Setup | 4, 7 |
| 6. Results | 9.1, 9.2 |
| 7. Analysis | 9.3, 9.4, 8.1, 8.2 |
| 8. Discussion | 8.3, 8.4 |
| 9. Limitations | 10.1 |
| 10. Future Work | 10.2 |

**Ba đóng góp có thể tuyên bố:**

1. Kiến trúc QA đặt **quyết định chấp nhận** vào code, dùng LLM chỉ để trích xuất
   và đề xuất; kèm bằng chứng thực nghiệm rằng cải thiện đến từ **khả năng phân
   biệt** chứ không phải từ việc nhát hơn.
2. Chỉ ra rằng **verify một quan hệ được suy ra bằng tiêu chí verify trực tiếp là
   sai về bản chất**, và đề xuất nhánh thay thế dựa trên verify từng số hạng cộng
   tính lại bằng code.
3. **Quy trình đánh giá chống tự huyễn hoặc**: tách tuned / held-out / safety, có
   câu đúng chiều chống hệ thống ngu ngốc, và bắt buộc test phản chứng cho từng
   luật — kèm bằng chứng định lượng về overfitting ở mức thiết kế luật.

**Cần bổ sung trước khi nộp paper:**

- Section Related Work (selective prediction, conformal abstention, RAG
  faithfulness, ambiguous question detection).
- Chạy benchmark đầy đủ 2.000 mẫu.
- Kiểm định thống kê cho chênh lệch giữa các hệ (bootstrap CI).
- Hoàn tất so sánh năng lực giữa các provider.
