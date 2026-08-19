# PonyGuard — lộ trình tối ưu

Tài liệu này là **kế hoạch phía trước**. Phần lịch sử (đã làm gì, đo được gì,
sai ở đâu) nằm ở [`PONYGUARD_INTENT_EVIDENCE_PLAN.md`](PONYGUARD_INTENT_EVIDENCE_PLAN.md).

## 0. Trạng thái xuất phát

Đo bằng `make live-behavioral MODEL=local`, pin 100% local
`Qwen/Qwen3-8B-MLX-4bit`, không fallback.

| Chỉ số | Giá trị |
| --- | ---: |
| Tuned suite (26 case, dùng để tune) | **20/26** |
| Held-out (10 case, **chưa từng dùng để tune**) | **6/10** |
| LLM calls / câu | 3.77 (từ 4.12) |
| Median latency | ~15–17 s |
| Vi phạm an toàn trên tuned suite | 0 |
| Vi phạm an toàn trên held-out | **1** — đảo quan hệ cho ra ANSWER sai |

**Chưa đạt acceptance** theo handoff: `live_ask_time` vẫn là unsafe ANSWER.

**Cảnh báo diễn giải:** 20/26 nói quá về mức an toàn. Bộ 26 được dùng để tune;
bộ held-out mới là ước lượng gần thực tế hơn, và nó lộ ra lỗ hổng an toàn.

## 1. Nguyên tắc bắt buộc (rút từ các sai lầm đã mắc trong phiên trước)

Vi phạm những điều này đã ba lần tạo ra kết luận sai:

1. **Luôn pin provider** khi chạy chẩn đoán (`MODEL=local`). Fallback tự động
   trộn hai model trong một lần chạy và từng tạo ra một so sánh hoàn toàn giả.
2. **Mọi phép đo có gắn tên provider phải ghi lại provider thực sự phục vụ**
   (`served_by`). Không ghi = không tin được.
3. **Một thay đổi, một lần chạy live.** Gộp nhiều thay đổi từng làm 17 → 14 và
   phải rollback toàn bộ.
4. **Sàn nhiễu là ±3 case.** Chênh lệch dưới mức đó không phải bằng chứng; phải
   có trace cho thấy cơ chế thực sự kích hoạt trên case mục tiêu.
5. **Đo trước khi xây.** Hai lần việc kiểm chứng đã chặn được thay đổi sai —
   trong đó một thay đổi trông rất hợp lý nhưng sẽ chạy đúng 0 lần.
6. **Không thêm luật ngữ nghĩa để cứu case cụ thể.** Nếu một luật chỉ chứng minh
   được bằng "nó sửa case X và không làm hỏng case Y", đó là fit test.

---

## S0 — Cắt nhánh chết (làm ngay, rủi ro ~0)

**Căn cứ đo được (36 case, cả hai bộ fixture):**

| Nhánh | Số lần chạy | LLM calls | Đóng góp |
| --- | ---: | ---: | --- |
| `clarification_adjudication` | 16 | 16 | **0 quyết định ASK** |
| `fact_recovery` | 18 | 18 | cứu 2 case, gồm `live_simple_inference` |

`clarification_adjudication` chiếm **12% tổng LLM calls** và chưa từng đổi một
quyết định nào. Sau khi intent nắm quyền quyết định ASK, nhánh này thừa.

**Việc cần làm**
- Bỏ nhánh `clarification_adjudication` khỏi đường chạy `intent_first`.
- **Giữ `fact_recovery`** — số liệu cho thấy nó load-bearing (2 case, gồm case
  inference vừa sửa). Đừng gộp hai nhánh này làm một.

**Rủi ro**: thấp, nhưng không bằng 0 — nhánh này về danh nghĩa là "cơ hội thứ hai"
cho ASK. Trace 16/16 lần trả `null` là bằng chứng nó không làm việc đó.

**Tiêu chí chấp nhận**
- `make test && make behavior-test` xanh.
- Live pinned: **20/26 không đổi**, held-out **6/10 không đổi**.
- LLM calls/câu giảm ~12%, latency giảm tương ứng.
- Nếu bất kỳ case nào đổi quyết định → dừng, điều tra, không nhận.

**Giá trị**: giảm chi phí và latency, không đổi hành vi. Đây là tối ưu duy nhất
hiện có mà không cần thêm bằng chứng.

### ✅ Đã hoàn thành — kết quả đo

Thay đổi: nhánh audit chỉ-câu-hỏi bị cắt khỏi đường `intent_first`
([`pipelines.py`](../src/ponyguard_viqa/pipelines.py)). Adjudicator có chunks
được **giữ** cho đường `intent_first: false`. `clarity_auditor_v1` không còn được
dùng, đã gỡ khỏi `prompt_versions` trong metadata.

| | Trước | Sau |
| --- | ---: | ---: |
| Tuned suite | 20/26 | **20/26** |
| Held-out | 6/10 | **6/10** |
| LLM calls (tuned) | 98 | **85** (−13.3%) |
| Calls / câu | 3.77 | **3.27** |
| `clarification_adjudication` chạy | 16 lần | **0** |

**Tập case fail giống hệt nhau trên cả hai bộ** — không một quyết định nào đổi.
Đây đúng là tiêu chí chấp nhận đã đặt ra trước khi làm.

`make test` 129 passed, `make behavior-test` 29 passed. Có test khoá hành vi:
đường `intent_first` không được tốn call cho audit chỉ-câu-hỏi.

So với baseline đầu việc: **4.12 → 3.27 calls/câu (−21%)**.

---

## S1 — An toàn: lỗ hổng đảo quan hệ (**phần đáng làm nhất**)

### Vấn đề

`hold_abstain_reversed_actor`: câu hỏi đảo chủ thể/tân ngữ so với nguồn, pipeline
trả **ANSWER kèm citation hợp lệ và quote nguyên văn**.

Support là `DIRECT` và qua **toàn bộ** relation gate: `premise_status: SUPPORTED`,
`relation_match: true`, `attribute_match: true`. Relation verifier — nhiệm vụ
chính là trả `CONTRADICTED` khi sai "actor/patient direction" — đã trả `MATCH`.

Đo riêng stage relation: **14/17**, và case này fail độc lập khỏi pipeline →
đúng là lỗi phán đoán của verifier, không phải tương tác pipeline.

### Vì sao đây là ưu tiên số một

- Nó tạo **câu trả lời sai một cách tự tin**, không phải một clarification thiếu.
- Nó xuất hiện trên bộ **held-out** → nhiều khả năng tổng quát ra dữ liệu thật.
- Nó vô hiệu hoá đúng cái tính chất PonyGuard tồn tại để bảo đảm.
- Không guard xác định nào bắt được: entity binding hợp lệ, quote nguyên văn,
  đáp án nằm trong quote. Mọi kiểm tra deterministic hiện có đều pass.

### S1.1 — Mở rộng độ phủ an toàn trước khi sửa

Lỗ hổng này được phát hiện bởi **đúng một** case. Không biết tỷ lệ thật.

- Bổ sung held-out các biến thể an toàn: đảo actor/patient, đảo nguồn/đích,
  đảo nguyên nhân/kết quả, sai attribute, sai phạm vi thời gian/nhóm.
- Mục tiêu ~8–12 case, **viết để phá**, không dùng để tune.
- Đây là bước đo, chưa sửa gì. Kết quả cho biết đây là lỗ hổng hệ thống hay
  một lần trượt.

### S1.2 — Kiểm tra đối xứng quan hệ (giả thuyết, cần thực nghiệm)

**Ý tưởng**: thay vì đòi model *giỏi hơn*, đòi model **nhất quán** — và bất nhất
thì phát hiện được bằng code.

Với một support `DIRECT`, hỏi verifier hai mệnh đề: quan hệ như câu hỏi nêu, và
quan hệ **đảo vai** hai đối số. Một verifier đúng phải trả `MATCH` cho đúng một
trong hai. Nếu trả `MATCH` cho **cả hai** → nó không phân biệt được chiều →
**loại support**, ABSTAIN.

- Quyết định cuối vẫn là code: so hai verdict, không đọc ngữ nghĩa.
- Không hard-code entity/cụm từ nào; phép đảo vai sinh ra từ chính hai đối số
  mà support đã khai báo (`question_entity_quote`, đối tượng của quan hệ).
- Model-agnostic: không yêu cầu model mạnh hơn, chỉ yêu cầu nó tự nhất quán.

**Chi phí**: +1 LLM call, **chỉ trên nhánh đã có candidate** (tức nhánh sắp
ANSWER). Ngân sách này vừa được S0 giải phóng.

**Rủi ro thật cần đo**: nếu verifier trả `MATCH` cho cả hai chiều trên các case
ANSWER đúng, luật này sẽ giết pass rate. **Phải đo trước bằng harness**
(`scripts/measure_judgement_stages.py`) trên toàn bộ 17 relation probe rồi mới
implement. Nếu tỷ lệ "MATCH cả hai chiều" cao ở case đúng → giả thuyết sai, bỏ.

**Tiêu chí chấp nhận**
- Held-out safety mới: không còn ANSWER nào cho câu đảo quan hệ.
- Tuned suite: **không giảm** dưới 20/26.
- Mọi ANSWER vẫn có citation + quote nguyên văn.

### ✅ S1.1 đã xong — đo được tỷ lệ lọt thật

`data/diagnostics/ponyguard_safety_holdout.jsonl`, 12 case, chạy bằng
`make live-safety MODEL=local`. Gồm **3 case đối chứng đúng chiều** để một hệ
thống "luôn ABSTAIN" không thể đạt điểm tuyệt đối.

Kết quả **10/12**:

- Đối chứng đúng chiều: **3/3** ANSWER đúng → bộ fixture không suy biến.
- Adversarial giữ ABSTAIN: **7/9**.
- **1 unsafe ANSWER**: `safe_rev_founder` ("Phong trào Bauhaus đã thành lập ai?"
  → trả "Walter Gropius").
- 1 sai nhưng không nguy hiểm: `safe_rev_capital` → ASK.

Cộng với `hold_abstain_reversed_actor` trước đó: **~2/7 câu đảo quan hệ bị lọt
thành ANSWER (~30%)**. Lỗ hổng là thật và lặp lại, không phải một lần trượt.

Đáng chú ý: `safe_rev_builder` và `hold_abstain_reversed_actor` dùng **cùng cặp
thực thể**, chỉ khác cách diễn đạt — một cái lọt, một cái không. Lỗ hổng mang
tính xác suất.

### ✅ S1.2 đã xong — đo trước, rồi mới implement

**Đo trước (10 probe có DIRECT support, chưa sửa code):**

| | Kết quả |
| --- | --- |
| Precision trên 6 case ANSWER đúng | **0/6 báo nhầm** |
| Recall trên 2 case lọt thật | **1/2** |

Giả thuyết đối xứng hai lời gọi bị thay bằng phương án rẻ hơn: **một lời gọi**
lấy bộ ba (subject, relation, object) cho **câu hỏi** và cho **nguồn**, rồi
Python so bằng token overlap literal — nếu subject của câu hỏi khớp với *object*
của nguồn tốt hơn khớp với *subject* của nguồn thì vai bị đảo → loại support.

Chỉ chạy trên nhánh **sắp ANSWER**. Hoà hoặc thiếu span → giữ nguyên support
(fail-safe).

**Kết quả live sau khi implement:**

| Bộ | Trước | Sau | unsafe ANSWER |
| --- | ---: | ---: | --- |
| Tuned | 20/26 | **20/26** | 0 → **0** |
| Held-out | 6/10 | **7/10** | 1 → **0** |
| Safety | 10/12 | **10/12** | 1 → **1** |

- `hold_abstain_reversed_actor` **đã bịt** — unsafe ANSWER biến mất.
- `safe_rev_founder` **vẫn lọt** — đúng như phép đo đã báo trước (model tự
  "sửa" câu hỏi, khai báo subject nguồn trùng subject câu hỏi).
- **Không mất case đúng nào**: direction-check chạy 8 lần trên bộ tuned, 0 lần
  báo nhầm. Precision trên live khớp với precision đo trước.

**Chi phí**: tuned 85 → 93 calls (+8, một call cho mỗi câu sắp ANSWER). Vẫn thấp
hơn baseline 98, và 3.58/câu so với 4.12 ban đầu (−13%).

**Đánh giá thẳng**: bịt được **1/2** lỗ hổng đã biết, không tốn pass rate. Đây là
cải thiện thật nhưng **chưa đóng được lớp lỗi**. Không nên coi là đã xong.

### ✅ S1.3 đã xong — giả thuyết prompt bị bác bỏ

**Chẩn đoán.** Với `safe_rev_founder`, model trả về **nhất quán 3/3 lần**:

```
q = {subject: "Phong trào Bauhaus", relation: "đã thành lập", object: "ai"}
s = {subject: "phong trào Bauhaus", relation: "do",           object: "Walter Gropius"}
```

Nguồn là *"phong trào Bauhaus **do** Walter Gropius thành lập"*. Model gán vai
theo **trật tự tuyến tính** — cái đứng trước thành `subject` — trong khi người
*thực hiện* là Walter Gropius. Ban đầu đây trông như lỗi schema của chính tôi:
đã hỏi (subject, relation, object) mà không định nghĩa vai theo nghĩa.

**Thử nghiệm.** `relation_direction_v2.txt` hỏi thẳng theo vai nghĩa
(agent/patient), định nghĩa agent là bên thực hiện hành động và **cấm gán vai
theo trật tự từ**. Đo trên 22 probe, cả ba bộ fixture:

| | v1 | v2 |
| --- | ---: | ---: |
| Báo nhầm trên case ANSWER đúng | **0** | **1** (`live_answer_date`) |
| Bắt được case cần chặn | **2** | **1** |
| Sửa được `safe_rev_founder`? | không | **không** |

**v2 tệ hơn v1 ở cả hai chiều** và vẫn không sửa được case mục tiêu. Đã xoá v2,
production giữ nguyên v1. Không cần chạy lại live vì code không đổi.

**Phát hiện phụ**: v1 có recall rộng hơn tôi ghi nhận ở S1.2 — nó còn bắt cả
`live_abstain_attribute` (case này vốn đã ABSTAIN vì lý do khác nên không đổi
kết quả, nhưng cho thấy precision 0 báo nhầm không đi kèm recall hẹp).

**Kết luận S1.3**: lỗ hổng còn lại **không sửa được bằng cách viết lại prompt**.
Hai cách diễn đạt khác nhau đều cho cùng một kết quả sai, và sai một cách tất
định. Đây là giới hạn biểu diễn/năng lực của model ở stage này → thuộc **S4**,
hiện đang bị chặn vì hết quota Gemini.

**Không thử tiếp prompt thứ ba.** Đó sẽ là prompt tuning diện rộng đúng như thứ
đã bị cấm từ đầu, và số liệu đang nói hướng này không dẫn tới đâu.

### Ý tưởng chưa đo (đừng implement khi chưa đo)

Trong output hỏng ở trên, `s.relation` là `"do"` còn `q.relation` là
`"đã thành lập"` — **hai relation không khớp nhau**. Một phép kiểm tra *đồng nhất
quan hệ* (relation span của nguồn phải trùng relation được hỏi) có thể bắt được
case này mà không cần biết chiều.

Rủi ro rõ ràng: diễn giải khác từ (paraphrase) ở các case trả lời đúng sẽ bị báo
nhầm. **Phải đo precision trên toàn bộ case ANSWER đúng trước.** Ghi lại ở đây
như một giả thuyết, không phải một việc đã duyệt.

---

## S2 — Kiến trúc: ASK do mơ hồ tham chiếu

**Đã xác minh**: tín hiệu có thật và phân biệt được.

| | Số chunk phát biểu đúng quan hệ được hỏi |
| --- | --- |
| Case mơ hồ (`live_ask_time`, `live_ask_entity`, `hold_ask_location_missing_country`) | **nhiều**, mỗi chunk một đáp án khác nhau theo thời gian/người/quốc gia |
| Case ANSWER đúng (đối chứng) | **đúng một** |

**Đã xác minh là chặn**: đếm `valid_supports` trên cả 36 case → **luôn là 0 hoặc
1, không bao giờ ≥2**. Extraction chọn một đáp án tốt nhất và huỷ tính đa đáp án
trước mọi điểm quyết định. Luật "≥2 support khác nhau → ASK" sẽ chạy **0 lần**.

**Việc cần làm**: đổi extraction sang **liệt kê một candidate cho mỗi chunk**
phát biểu quan hệ, thay vì chọn một. Rồi mới đo được tính đa đáp án.

**Phải đo trước khi làm**
- Chi phí token/latency của per-chunk enumeration.
- Tác động lên 8 safety fixture: nhiều candidate hơn = nhiều cơ hội lọt hơn,
  **đặc biệt nguy hiểm khi S1 chưa xong**.

→ **Không làm S2 trước S1.** Nhân số lượng candidate lên trong khi verifier còn
để lọt câu đảo quan hệ là làm rộng đúng cái lỗ hổng đang có.

**Giới hạn đã biết**: chỉ giải quyết ~3/6 case còn lại. `live_ask_attribute` và
`live_ask_scope` **không có chunk liên quan nào** → không có đa đáp án để phát
hiện, không phân biệt được với câu hỏi không có evidence.

### ❌ S2 đã bị bác bỏ bằng phép đo — KHÔNG implement

**Đính chính phạm vi trước khi đo.** Đếm `valid_supports` thực tế: chỉ
`live_ask_time` có support (1). `live_ask_entity`,
`hold_ask_location_missing_country`, `live_ask_attribute`, `live_ask_scope` đều
có **0 support** vì entity không bind được ("ông ấy", "Thủ đô" không neo vào
nguồn nào). Liệt kê theo chunk **không thể** tạo ra đa đáp án khi bản thân entity
không bind. Vậy S2 chỉ nhắm được **1 case**, không phải 3 như ước lượng ban đầu —
nhưng đó đúng là blocker của acceptance.

**Phép đo (prompt liệt kê đáp án thay thế, chạy trên 9 case, chưa sửa code):**

| Case | gold | #đáp án phân biệt | Hệ quả |
| --- | --- | ---: | --- |
| `live_ask_time` (mục tiêu duy nhất) | ASK | **0** | không bắt được gì |
| `live_answer_percentage` | ANSWER | **5** | sẽ mất case đúng |
| `live_answer_location` | ANSWER | 2 | "Bảo tàng Louvre" / "viện bảo tàng Louvre" |
| `live_answer_time` | ANSWER | 2 | báo nhầm |
| 5 case còn lại | ANSWER | 1 | đúng |

**Recall 0/1, báo nhầm 3/8.** Ngược hoàn toàn với yêu cầu: mất ~3 case đúng và
sửa được 0. Prompt thí nghiệm đã xoá, không có thay đổi nào vào production.

**Vì sao thất bại.** Tín hiệu **có thật trong chunks** — tôi đã tự đọc và thấy
53 nghìn (1954), 132.145 (1940s), 8.215.000. Nhưng model không trích xuất được
nó qua một contract dùng được. Nghịch lý: ở `live_ask_time` nơi thật sự có nhiều
đáp án thì model trả về 0, còn ở `live_answer_percentage` nơi chỉ có một đáp án
đúng thì nó trả về 5.

**Quan sát đáng ghi (chưa đo, đừng đuổi theo ngay).** Việc model trả 0 cho
`live_ask_time` có thể là hành vi *đúng về mặt ngữ nghĩa*: không chunk nào nêu
dân số vào "khi đó" — vì "khi đó" chưa được giải quyết. Nếu vậy thì mâu thuẫn
nằm giữa hai stage: extractor chính vẫn sinh ra một support (8.215.000) trong
khi stage này nói không có gì khớp. Một phép kiểm tra *nhất quán giữa hai stage*
có thể khai thác được điều đó — nhưng đó là giả thuyết mới, phải đo riêng, và
**không được biến thành vòng lặp tinh chỉnh prompt**.

**Kết luận**: lớp mơ hồ tham chiếu không giải được bằng model hiện tại ở bất kỳ
tầng nào đã thử — không ở intent (S1b), không ở extraction (S2). Chuyển toàn bộ
lớp này sang **S4**.

---

## S3 — Retrieval (2 case, ngoài phạm vi hiện tại)

`live_answer_person` (nguồn ngoài top-k) và `live_answer_definition` (không chunk
nào nhắc tới cụm từ). Không phải lỗi model hay validator.

Handoff cấm nới `top_k` để tune — và thí nghiệm nới `top_k * 3` từng làm 17 → 14.
Cấm đó nhắm vào *tuning*, không cấm thiết kế lại retrieval (ví dụ retrieve rộng
rồi rerank, giữ nguyên số chunk đưa vào LLM).

Chỉ làm sau S1 và S2, như một thay đổi riêng có phép đo riêng.

---

## S4 — Năng lực theo provider (đang bị chặn)

**Chưa đo được** — Gemini trả `429` trên toàn bộ 36 probe.

Đã đo được, không cần quota:

| Model | intent |
| --- | ---: |
| Qwen2.5-3B-4bit | 23/36 |
| Qwen2.5-7B-4bit | 23/36 |
| Qwen3-8B-4bit (production) | 29/36 |

3B → 7B **phẳng**. Và **5 case fail trên cả ba model** → các case chặn ta **không
phải giới hạn kích thước**. Điều này làm **suy yếu** giả thuyết "đổi model mạnh
hơn là xong".

**Không implement routing theo capability** cho tới khi có phép đo cross-provider
hợp lệ. Bằng chứng duy nhất từng ủng hộ nó là một lần đo hỏng.

Khi có quota: chạy
`scripts/measure_judgement_stages.py --models local <model> --stages intent relation`
và đọc cột `served_by` trước khi tin bất kỳ con số nào.

---

## Nợ kỹ thuật — luật chưa được validate

Hai luật đã nằm trong production nhưng **chưa chứng minh được**:

- `ANSWER_TYPE_SATISFIES` (`core.py`)
- Luật "resolved family che allegation" trong `apply_clarity_guard` (Change C)

Hai case held-out viết ra để phá chúng đều fail **ở tầng trên** — intent không
phát ra binding nào nên luật không được chạy tới. Chúng **chưa được xác nhận
cũng chưa bị bác bỏ**.

**Việc cần làm**: viết falsifier chạm được tới luật — nghĩa là fixture mà intent
*có* phát ra allegation về `country`/`location`. Nếu luật sai → **gỡ bỏ**, không
nới thêm luật để cứu.

### ✅ Đã xong — cả hai luật SAI, đã gỡ

Không dựng được tình huống qua model live (nó không chịu phát ra binding cần
thiết), nên falsifier được viết bằng **input tất định** — vì câu hỏi mở là *đặc
tả có đúng không*, không phải *code có chạy đúng đặc tả không*.

| Falsifier | Hành vi đúng | Luật cũ |
| --- | --- | --- |
| "Thủ đô của **nước đó** nằm ở đâu?" — hỏi LOCATION, `country` là tham chiếu chưa giải quyết | ASK `country` | **suy ra `[]`** — nuốt mất ASK hợp lệ |
| "Thành phố **Springfield** nằm ở bang nào?" — `location` resolved nhưng jurisdiction vẫn thiếu | ASK `country` | **suy ra `[]`** |

Cả hai **fail**. Đã sửa bằng cách **thu hẹp về lõi có căn cứ**, không phải nới thêm:

- `ANSWER_TYPE_SATISFIES`: `LOCATION` từ `{location, country}` → `{location}`.
  Lý lẽ "từ để hỏi thì hỏi chính chiều của nó" chỉ biện minh được cho đúng chiều
  mà answer type *là*, không cho các chiều anh em.
- Change C: bỏ hoàn toàn phần mở rộng theo family. Chỉ giữ lõi phòng thủ được —
  một contract không thể vừa resolve một slot vừa khai slot **đó** đang thiếu.

`ANSWER_TYPE_SATISFIES` không còn được dùng trong `apply_clarity_guard`; import
đã gỡ.

**Giá phải trả, đo được:**

| Bộ | Trước khi gỡ | Sau khi gỡ |
| --- | ---: | ---: |
| Tuned | 20/26 | **19/26** |
| Held-out | 7/10 | **7/10** |
| Safety held-out | 10/12 | **10/12** |
| unsafe ANSWER | 1 | **1** |

Mất đúng **1 case**, và chỉ trên bộ **tuned**: `live_answer_list`. Held-out không
đổi chút nào.

**Đây là bằng chứng sạch nhất của cả phiên về overfitting.** Toàn bộ giá trị của
luật family nằm trên chính bộ dữ liệu nó được thiết kế dựa theo, và **bằng 0**
trên dữ liệu chưa từng thấy — trong khi nó có thể nuốt mất ASK hợp lệ. Đổi 1 điểm
tuned lấy việc gỡ một luật sai là đúng.

`live_answer_list` fail vì model khai `country` thiếu trên một câu hỏi đã đầy đủ.
Đó là nhiễu của model, **không phải thứ nên che bằng guard**. Để nguyên, ghi
nhận, và xử lý ở tầng năng lực (S4) nếu cần.

---

## Thứ tự thực hiện

| Bước | Nội dung | Rủi ro | Giá trị |
| --- | --- | --- | --- |
| **S0** | Cắt `clarification_adjudication` | ~0 | −12% calls, giải phóng ngân sách cho S1 |
| **S1.1** | Mở rộng held-out an toàn | 0 (chỉ đo) | biết tỷ lệ thật của lỗ hổng |
| **S1.2** | Kiểm tra đối xứng quan hệ | trung bình, phải đo trước | **bịt lỗ hổng an toàn** |
| **S2** | Per-chunk enumeration | cao — nới rộng bề mặt lọt | +~3 case, sửa unsafe `live_ask_time` |
| **S3** | Thiết kế lại retrieval | trung bình | +2 case |
| **S4** | Routing theo capability | đang bị chặn | chưa rõ |
| **Nợ** | Falsifier chạm được 2 luật chưa validate | 0 (chỉ đo) | gỡ bỏ nếu sai |

Nếu chỉ được làm **một** việc: làm **S1**. Pass rate là chỉ số phụ; một câu trả
lời sai kèm citation hợp lệ mới là thứ phá vỡ mục đích tồn tại của hệ thống.

## Không làm

- Không sửa `data/benchmark/test.jsonl`, manifest, corpus, FAISS index/retriever.
- Không nới `top_k` để cứu case.
- Không nới điều kiện `MATCH` của nhánh `DIRECT`.
- Không thêm entity/câu hỏi/đáp án/cụm từ ngôn ngữ vào production code.
- Không chạy benchmark cuối cho tới khi config chẩn đoán đã đóng băng.
