# PonyGuard-ViQA — Kịch bản thuyết trình 10 phút

**Nhóm 5 người · mỗi người ~2 phút · mỗi người 1 slide**

| # | Phần | Người nói |
| --- | --- | --- |
| 1 | Bài toán và động lực (kèm mở bài) | **Đức** |
| 2 | Mục tiêu và thiết kế thực nghiệm | **Hòa** |
| 3 | Kiến trúc PonyGuard | **Dương** |
| 4 | Cách đánh giá và các phát hiện | **Hiệp** |
| 5 | Kết quả, hạn chế và hướng phát triển | **Hải** |

> **Cách dùng:** chữ thường là **lời nói**. *In nghiêng* là gợi ý slide.
> `[ngoặc vuông]` là chỉ dẫn sân khấu, không đọc. Bảng trong slide thì **chiếu
> chứ không đọc** — chỉ nói con số được in đậm.
>
> Chuẩn bị + phản biện: [`PONYGUARD_PLAN_AND_QA.md`](PONYGUARD_PLAN_AND_QA.md) ·
> Chi tiết kỹ thuật: [`PONYGUARD_THUYET_MINH.md`](PONYGUARD_THUYET_MINH.md)

---

## PHẦN 1 — Bài toán và động lực
### Đức · 2 phút

*Slide: tên đề tài; dưới là câu hỏi + câu trả lời có citation, đóng dấu đỏ "SAI".*

Xin chào thầy cô và các bạn. Nhóm em trình bày đề tài **PonyGuard-ViQA — hệ hỏi
đáp tiếng Việt biết từ chối trả lời**.

Em là Đức, nói về bài toán. Sau đó Hòa nói thiết kế thực nghiệm, Dương nói kiến
trúc, Hiệp nói cách đánh giá và các phát hiện, Hải kết bằng kết quả.

`[Vào ví dụ]`

Em bắt đầu bằng một câu hỏi:

> *"Tập đoàn Lend Lease được Làng Olympic xây dựng ở đâu?"*

Tài liệu nói ngược lại: **Lend Lease xây Làng Olympic**. Câu hỏi này đã **đảo chủ
ngữ với tân ngữ**.

Hệ thống của nhóm em, ở một phiên bản đang phát triển, trả lời **"Thung lũng
Lower Lea"** — kèm citation đúng chunk, quote nguyên văn không sai một chữ.

Thực thể **có** trong nguồn, quote **đúng** nguyên văn, đáp án **nằm trong**
quote. Mọi ràng buộc mức từ ngữ đều thỏa. Cái sai nằm ở **ai làm gì với ai** —
thứ mà so khớp chuỗi không nhìn thấy.

Đây là dạng hallucination nguy hiểm nhất trong RAG, vì **nó không nghe có vẻ
sai**. Người dùng không có lý do gì để nghi ngờ.

Nguyên nhân đơn giản: RAG thông thường **luôn trả lời**. Nó không có khái niệm
"câu này không nên trả lời".

Và trong tra cứu y tế hay pháp lý, hai loại lỗi **không ngang nhau**. Từ chối
nhầm thì người dùng mất công tra tay — thiệt hại có giới hạn và **nhìn thấy
được**. Còn trả lời sai kèm citation thì người dùng tin và làm theo — thiệt hại
không giới hạn và **không ai biết**.

Nên mục tiêu của nhóm em không phải accuracy trung bình, mà là: **thà bỏ sót còn
hơn nói sai**.

`[Chuyển]` Đo điều đó thế nào cho khoa học — em mời Hòa.

---

## PHẦN 2 — Mục tiêu và thiết kế thực nghiệm
### Hòa · 2 phút

*Slide: trái — bảng 3 hành động; phải — 3 hộp hệ thống trên cùng nền
"Corpus + Retriever + Schema".*

Cảm ơn Đức. Em là Hòa.

Việc đầu tiên là **định nghĩa lại output**. Thay vì luôn sinh câu trả lời, hệ
thống chọn **một trong ba hành động**, mỗi hành động gắn với một điều kiện
**kiểm tra được**: `ANSWER` khi tài liệu chứng minh được, có citation và quote
nguyên văn. `ASK` khi **câu hỏi** thiếu thông tin. `ABSTAIN` khi **tài liệu**
thiếu.

Em nhấn mạnh ranh giới giữa `ASK` và `ABSTAIN`, vì đây là quyết định thiết kế
chứ không phải chi tiết code. Gộp hai cái là sai — hỏi lại người dùng không giúp
gì khi corpus vốn không có dữ liệu.

`[Sang thiết kế so sánh]`

Để tách riêng đóng góp của cơ chế kiểm tra, nhóm em so **ba hệ** chạy trên **cùng
corpus, cùng retriever, cùng top-k, cùng schema, cùng model nền**:

**Basic RAG** — retrieve rồi sinh, đây là baseline. **Prompt-Safe RAG** — thêm
chỉ dẫn bảo model tự từ chối khi thiếu bằng chứng, đại diện cho cách phổ biến
nhất hiện nay là dặn dò bằng prompt. Và **PonyGuard** — kiểm tra nhiều tầng có
cấu trúc.

Vì mọi thứ khác giống hệt nhau, chênh lệch đo được **quy về đúng** biến ta muốn
đo.

Nhóm em cũng tự đặt một ràng buộc: **không hard-code** bất kỳ thực thể hay đáp án
nào. Một câu hỏi quan sát được là một **test case**, không phải một luật nhét vào
pipeline. Ràng buộc này làm mọi thứ chậm hơn nhiều — và Hiệp sẽ cho thấy nhóm em
suýt vi phạm nó thế nào.

Dữ liệu: UIT-ViQuAD 2.0, split đóng băng verify bằng hash, corpus 5.400 chunk,
retrieve bằng FAISS, model nền Qwen3-8B chạy local.

`[Chuyển]` Kiến trúc đó trông thế nào — em mời Dương.

---

## PHẦN 3 — Kiến trúc PonyGuard
### Dương · 2 phút

*Slide: sơ đồ dọc 5 tầng; tiêu đề lớn "LLM đề xuất — Code quyết định".*

Cảm ơn Hòa. Em là Dương.

Cả hệ thống xoay quanh **một nguyên tắc**:

> **Đưa quyết định ra khỏi LLM, giao cho code.**

LLM dùng để **trích xuất** và **đề xuất**. Việc **chấp nhận hay loại bỏ** thì code
làm. Lý do: phán đoán của LLM **không ổn định theo cách diễn đạt** — cùng một cặp
thực thể, đổi cách hỏi thôi là model cho hai kết quả khác nhau. Code thì cùng
input luôn ra cùng output.

`[Đi qua 5 tầng, nhịp nhanh]`

**Tầng 1 — phân tích intent, chạy trước khi retrieve.** Model khai từng thông tin
trong câu hỏi, kèm **một đoạn copy nguyên văn từ chính câu hỏi** và một nhãn: đã
rõ, là tham chiếu chưa xác định, hay không có. Rồi **code** kiểm tra đoạn đó có
thật nằm trong câu hỏi không và **tự tính** kết luận. Model không được tự tuyên
bố câu hỏi đã đủ thông tin.

Vì sao chạy trước khi retrieve? Vì nếu để sau, hệ thống sẽ hỏi lại chỉ vì không
tìm thấy bằng chứng — mà đó là lý do để **từ chối**, không phải để hỏi.

**Tầng 2 — trích xuất bằng chứng:** mỗi bằng chứng phải kèm quote nguyên văn,
không được diễn giải lại.

**Tầng 3 — verify quan hệ**, ba nhãn: khớp, mâu thuẫn, hoặc nguồn không nói. Tầng
này chặn đảo chủ ngữ tân ngữ, sai thuộc tính, sai mốc thời gian.

**Tầng 4 — kiểm tra bằng code.** Đây mới là chỗ ra quyết định thật: bảy bước tuần
tự, từ chunk được cite có tồn tại không, quote có nguyên văn không, cho tới thực
thể có khớp **cả** câu hỏi lẫn nguồn không. Qua hết bảy bước thì bộ ba đáp án –
quote – citation bị **khóa lại**; tầng viết câu chữ phía sau chỉ được diễn đạt
lại, **không được thay**.

**Tầng 5 — hai nhánh riêng:** một nhánh **tính lại phép toán bằng code** cho câu
suy luận, và một nhánh **kiểm tra chiều quan hệ** cho ca đảo vai bạn Đức nêu ở
đầu.

`[Chuyển]` Phần thú vị nhất lại là những gì nhóm em học được **khi nó chạy sai**.
Em mời Hiệp.

---

## PHẦN 4 — Cách đánh giá và các phát hiện
### Hiệp · 2 phút

*Slide: trên — 3 hộp Tuned / Held-out / Safety; dưới — chia đôi
"Hỏi sai câu hỏi" | "Overfitting: −1 vs 0".*

Cảm ơn Dương. Em là Hiệp.

**Về cách đánh giá:** nhóm em tách **ba bộ test** — bộ **tuned** dùng lúc phát
triển nên luôn lạc quan hơn thực tế, bộ **held-out** chưa từng dùng để chỉnh, và
bộ **safety** chuyên về đảo quan hệ.

Chi tiết em muốn nhấn: bộ safety **cố ý có ba câu đúng chiều**. Nếu chỉ toàn câu
cần từ chối, một hệ thống ngu ngốc kiểu **"cứ từ chối hết"** sẽ được điểm tuyệt
đối.

`[Phát hiện 1]`

**Phát hiện thứ nhất — nhóm em đã hỏi sai câu hỏi.**

Với câu kiểu *"chênh lệch giữa A và B là bao nhiêu?"*, tầng verify nhận được câu
hỏi: *"nguồn có nói về quan hệ **chênh lệch** không?"* — và luôn trả lời không.

Mà trả lời vậy là **đúng** — không nguồn nào nói ra một quan hệ **được suy ra**,
nếu nguồn nói rồi thì đâu còn là suy luận. Nhóm em đã hỏi tầng verify một câu mà
**bản chất nó không thể trả lời khác được**. Hậu quả: bộ kiểm tra số học viết
đúng nhưng **không bao giờ chạy tới**.

Cách sửa: bỏ hẳn việc verify quan hệ tổng hợp, thay bằng verify **từng số hạng
một** rồi **tính lại phép toán bằng code**. Cách này **chặt hơn** chứ không lỏng
hơn — thay một phán đoán của model bằng bốn bước kiểm tra độc lập.

Bài học: **một tầng verify chỉ hoạt động khi ta hỏi nó đúng câu nó trả lời
được.**

`[Phát hiện 2]`

**Phát hiện thứ hai — bằng chứng định lượng về overfitting.**

Nhóm em từng thêm hai luật để xử lý các ca quan sát được, cả hai viết **hoàn toàn
tổng quát**, không chứa thực thể nào — đúng ràng buộc "không hard-code".

Sau đó nhóm em viết **test phản chứng** để **bác bỏ** chính hai luật đó. Cả hai
đều **nuốt mất** những câu đáng lẽ phải hỏi lại.

Gỡ hai luật ra: bộ **tuned mất đúng một câu**, bộ **held-out không đổi một điểm
nào**. Nghĩa là toàn bộ giá trị của chúng nằm trên chính bộ dữ liệu chúng được
thiết kế dựa theo, và **bằng không** trên dữ liệu mới.

> Bài học: "không hard-code" là **cần nhưng chưa đủ**. Một luật viết tổng quát
> vẫn là fit test nếu nó được **chọn** bằng cách xem nó sửa được câu nào.

`[Chuyển]` Kết quả ra sao — em mời Hải.

---

## PHẦN 5 — Kết quả, hạn chế và hướng phát triển
### Hải · 2 phút 15

*Slide: biểu đồ so sánh Basic RAG, Prompt-Safe và PonyGuard.*

Cảm ơn Hiệp. Em là Hải. Phần này trả lời ba câu đơn giản: PonyGuard có chặn
được câu trả lời sai hơn Basic RAG không, câu trả lời nó giữ lại đáng tin đến
đâu, và phải đánh đổi điều gì.

Nhóm đánh giá ba hệ trên cùng 200 câu test đóng băng, cùng corpus, retriever và
model local. Trong đó có 103 câu có đáp án và 97 câu không nên trả lời.

**Kết quả quan trọng nhất là độ an toàn.** Với 97 câu không có đáp án, Basic RAG
vẫn trả lời sai 39 câu. PonyGuard còn 13 câu. Nghĩa là các bước kiểm tra đã chặn
được thêm 26 câu trả lời sai trong cùng điều kiện thử.

**Chất lượng của những câu được trả lời cũng tốt hơn.** Ở Basic RAG, khoảng 53%
câu trả lời được chấp nhận là đúng; với PonyGuard là 70,5%. Vì vậy kết quả không
chỉ đến từ việc hệ thống từ chối nhiều hơn: các câu trả lời còn lại đáng tin hơn.
Điểm chất lượng quyết định tổng thể cũng tăng từ 0,513 lên 0,583.

`[Chuyển sang slide chất lượng hiện tại]`

Tuy nhiên đây chưa phải một hệ có thể dùng cho mọi tình huống. Nó vẫn trả lời 13
trong 97 câu lẽ ra phải từ chối. Và trong 103 câu có đáp án, PonyGuard mới trả
lời đúng 31 câu; Basic RAG trả lời đúng 44 câu.

Nhóm đã tách nguyên nhân để biết cần cải thiện ở đâu. Trong 72 câu PonyGuard bỏ
sót, 34 câu không có đáp án trong các chunk đã truy hồi—đây là giới hạn retrieval.
38 câu còn lại là phần chi phí của các guard hiện tại đang quá chặt.

Đánh đổi thứ hai là tốc độ: thời gian phản hồi trung vị của PonyGuard là 24,8
giây, so với 11,7 giây ở Basic RAG.

Vì vậy, kết luận hiện tại là PonyGuard phù hợp khi ưu tiên giảm câu trả lời sai
một cách tự tin, nhưng chưa phù hợp cho tình huống rủi ro cao. Bước tiếp theo là
cải thiện retrieval, hiệu chỉnh guard để nhận thêm bằng chứng trực tiếp, rồi
đánh giá trên toàn bộ test set và các lĩnh vực khác.

Nhóm em xin hết. Rất mong nhận được câu hỏi từ thầy cô và các bạn.
