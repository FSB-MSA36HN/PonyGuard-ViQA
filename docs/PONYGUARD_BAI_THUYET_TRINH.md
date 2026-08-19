# PonyGuard-ViQA — Bài thuyết trình (5 người)

**Tổng thời lượng:** 25–30 phút + 5 phút hỏi đáp
**Phân công:** 5 phần lớn, mỗi người 5–6 phút

> **Quy ước:** phần in nghiêng là *gợi ý slide*; phần còn lại là nội dung nói.
> Số liệu PonyGuard trên benchmark còn đang chạy — xem mục "Số liệu cần cập
> nhật" ở cuối trước khi thuyết trình.

---

# PHẦN 1 — Bài toán và động lực
**Người trình bày 1 · 5 phút**

## 1.1 Mở đầu bằng một ví dụ cụ thể (1 phút)

*Slide: một câu hỏi + câu trả lời có trích dẫn, nhưng sai.*

Hãy bắt đầu bằng một câu hỏi rất đời thường:

> *"Tập đoàn Lend Lease được Làng Olympic xây dựng ở đâu?"*

Tài liệu gốc nói: *"Làng Olympic nằm ở Thung lũng Lower Lea, **do tập đoàn Lend
Lease xây dựng**."* Tức là Lend Lease xây Làng Olympic — không phải ngược lại.
Câu hỏi đã **đảo vai** chủ thể và tân ngữ.

Hệ thống của chúng tôi, ở phiên bản chưa hoàn thiện, trả lời:
**"Thung lũng Lower Lea"** — kèm trích dẫn đúng đoạn văn, kèm trích đoạn nguyên
văn không sai một chữ.

Mọi kiểm tra bề mặt đều hợp lệ. Thực thể có trong nguồn. Trích dẫn có thật.
Nhưng câu trả lời **sai**, vì tiền đề của câu hỏi sai và hệ thống không nhận ra.

## 1.2 Vì sao đây là dạng ảo giác nguy hiểm nhất (1.5 phút)

*Slide: 3 dòng — "Nghe có vẻ đúng / Có trích dẫn / Nhưng sai".*

Khi nói về ảo giác của mô hình ngôn ngữ, người ta thường nghĩ tới những câu bịa
đặt lộ liễu. Nhưng trong RAG — sinh câu trả lời dựa trên tài liệu truy xuất —
dạng nguy hiểm nhất lại khác:

- Nó **có trích dẫn** thật, chỉ trong tài liệu thật.
- Nó **trôi chảy**, đúng ngữ pháp, đúng văn phong.
- Nó **không nghe có vẻ sai**, nên người dùng không có lý do để nghi ngờ.

Nguyên nhân gốc: hệ thống RAG thông thường **luôn trả lời**. Nó không có khái
niệm "không nên trả lời câu này". Với nó, mọi câu hỏi đều là một bài toán sinh
văn bản.

## 1.3 Ba tình huống hệ thống nên từ chối (1.5 phút)

*Slide: bảng 3 dòng.*

Có ít nhất ba tình huống mà câu trả lời đúng là **không trả lời**:

| Tình huống | Ví dụ |
| --- | --- |
| Tài liệu không chứa đáp án | Hỏi về khái niệm không có trong corpus |
| Câu hỏi mơ hồ | *"Quốc khánh là ngày nào?"* — của nước nào? |
| Câu hỏi có tiền đề sai | Ví dụ đảo vai ở trên |

Mỗi tình huống cần một phản ứng **khác nhau**: cái thứ hai nên **hỏi lại**, hai
cái còn lại nên **từ chối**. Gộp chung thành một là sai — hỏi lại khi thiếu tài
liệu chỉ làm phiền người dùng mà không giải quyết gì.

## 1.4 Vì sao chi phí không đối xứng (1 phút)

*Slide: cân lệch — "Từ chối sai" nhẹ, "Trả lời sai tự tin" nặng.*

Trong tra cứu y tế, pháp lý hay chính sách, hai loại lỗi **không ngang nhau**:

- Từ chối nhầm một câu trả lời được: người dùng mất công tra thủ công.
- Trả lời sai kèm trích dẫn: người dùng **tin và hành động theo**.

Vì vậy chúng tôi không tối ưu độ chính xác trung bình. Chúng tôi tối ưu theo
hướng: **thà bỏ lỡ còn hơn nói sai**.

> **Chốt phần 1:** Vấn đề không phải làm mô hình thông minh hơn, mà là làm nó
> biết giới hạn của chính nó. Bạn tiếp theo sẽ nói về cách chúng tôi thiết kế
> thí nghiệm để đo được điều đó.

---

# PHẦN 2 — Mục tiêu và thiết kế thực nghiệm
**Người trình bày 2 · 5 phút**

## 2.1 Định nghĩa lại đầu ra của hệ thống (1.5 phút)

*Slide: bảng 3 hành động và điều kiện.*

Thay vì buộc hệ thống luôn sinh câu trả lời, chúng tôi định nghĩa lại: nó phải
chọn **một trong ba hành động**, và phải chọn **đúng vì đúng lý do**.

| Hành động | Điều kiện bắt buộc |
| --- | --- |
| `ANSWER` | Văn bản truy xuất **chứng minh được** quan hệ được hỏi, kèm trích dẫn hợp lệ và trích đoạn **nguyên văn** |
| `ASK` | **Bản thân câu hỏi** thiếu một thành phần ngữ nghĩa bắt buộc |
| `ABSTAIN` | Câu hỏi rõ ràng, nhưng bằng chứng vắng mặt / lệch / mâu thuẫn / không đủ |

Điểm cần nhấn: điều kiện của `ASK` nói về **câu hỏi**, không nói về tài liệu.
Đây là ranh giới thiết kế quan trọng mà chúng tôi sẽ quay lại ở Phần 3.

## 2.2 Ràng buộc phương pháp luận (1.5 phút)

*Slide: một dòng lớn — "Một câu hỏi quan sát được là một test case, không phải
một luật".*

Chúng tôi tự đặt một ràng buộc nghiêm ngặt: **không hard-code** bất kỳ thực thể,
câu hỏi, đáp án hay mẫu ngôn ngữ nào vào hệ thống.

Vì sao quan trọng? Khi thấy hệ thống sai ở một câu, phản xạ tự nhiên là thêm một
luật xử lý riêng cho câu đó. Làm vài chục lần, ta có một hệ thống trông rất tốt
trên bộ test và **vô dụng** ngoài thực tế.

Ràng buộc này khiến việc phát triển chậm hơn nhiều, nhưng nó là điều kiện cần để
kết quả có ý nghĩa khoa học. Ở Phần 4, chúng tôi sẽ cho thấy một trường hợp
**định lượng được** là chúng tôi đã suýt vi phạm nó như thế nào.

## 2.3 Ba hệ thống so sánh (1.5 phút)

*Slide: 3 hộp xếp ngang, cùng đáy "Corpus + Retriever + Schema".*

Chúng tôi so sánh ba hệ chạy trên **cùng corpus, cùng bộ truy xuất, cùng schema
đầu ra**:

1. **Basic RAG** — truy xuất rồi sinh câu trả lời. Đường cơ sở.
2. **Prompt-Safe RAG** — như trên, nhưng **prompt yêu cầu** mô hình tự từ chối
   khi không đủ bằng chứng. Đại diện cho cách tiếp cận phổ biến nhất hiện nay:
   "dạy mô hình cẩn thận bằng lời dặn".
3. **PonyGuard** — kiến trúc nhiều tầng kiểm chứng có cấu trúc.

Việc giữ mọi thứ khác **giống hệt nhau** là có chủ đích: nó cô lập đúng biến
chúng tôi muốn đo là **cơ chế kiểm chứng**, chứ không phải chất lượng mô hình
hay chất lượng truy xuất.

- So 1 với 2 trả lời: *dặn dò bằng prompt có đủ không?*
- So 2 với 3 trả lời: *kiểm chứng có cấu trúc mang thêm được gì?*

## 2.4 Dữ liệu và hạ tầng (0.5 phút)

*Slide: thông số.*

- **Dữ liệu:** UIT-ViQuAD 2.0, chia đóng băng bằng manifest có hash để đảm bảo
  không ai vô tình tinh chỉnh trên tập test.
- **Truy xuất:** FAISS trên embedding `multilingual-e5-small`, corpus ~5.400
  đoạn văn.
- **Mô hình:** Qwen3-8B chạy cục bộ (MLX, lượng tử hoá 4-bit).

> **Chốt phần 2:** Thiết kế thí nghiệm xong, câu hỏi còn lại là kiến trúc kiểm
> chứng trông như thế nào. Bạn tiếp theo sẽ trình bày.

---

# PHẦN 3 — Kiến trúc PonyGuard
**Người trình bày 3 · 6 phút**

## 3.1 Nguyên lý cốt lõi (1 phút)

*Slide: một dòng lớn — "LLM đề xuất. Mã quyết định."*

Toàn bộ kiến trúc xoay quanh một nguyên lý:

> **Đẩy quyết định ra khỏi mô hình ngôn ngữ, vào mã tất định, bất cứ khi nào có
> thể.**

Mô hình ngôn ngữ được dùng để **trích xuất** và **đề xuất**. Việc **chấp nhận
hay từ chối** do mã kiểm tra thực hiện.

Lý do: mô hình ngôn ngữ giỏi tìm kiếm và diễn đạt, nhưng phán đoán của nó không
ổn định — cùng một loại lỗi, lúc nó bắt được lúc không. Còn mã kiểm tra thì luôn
cho cùng kết quả với cùng đầu vào. Ta xây phần bảo đảm an toàn trên nền tất
định, không xây trên nền xác suất.

## 3.2 Tầng 1 — Phân tích ý định, **trước** khi truy xuất (1.5 phút)

*Slide: sơ đồ — Câu hỏi → Ý định → (ASK) hoặc → Truy xuất.*

Quyết định `ASK` được đưa ra **trước** khi nhìn tài liệu.

Vì sao? Nếu để sau, hệ thống sẽ hỏi lại chỉ vì **không tìm thấy bằng chứng** —
nhưng thiếu bằng chứng là lý do để `ABSTAIN`, không phải để hỏi lại. Hỏi lại
trong tình huống đó là đổ lỗi cho người dùng về một thiếu sót của tài liệu.

Cách làm: mô hình phải khai **từng slot ngữ nghĩa** — thực thể, thuộc tính được
hỏi, thời gian, địa điểm, phạm vi — kèm hai thứ:

- một **đoạn trích nguyên văn từ chính câu hỏi**;
- một **trạng thái** thuộc tập đóng: `RESOLVED` / `REFERENTIAL` / `ABSENT`.

Rồi **mã nguồn** kiểm tra đoạn trích đó có thật sự nằm trong câu hỏi không, và
**tự tính** kết luận "câu hỏi đã đủ thông tin chưa". Mô hình **không được phép**
tự tuyên bố điều đó.

*Nhấn mạnh:* phân biệt `ABSENT` (câu hỏi không ràng buộc chiều này) với
`REFERENTIAL` (có nhắc tới nhưng chưa xác định) là mấu chốt. Nếu gộp, hệ thống
sẽ hỏi lại chỉ vì câu hỏi không nêu năm hay quốc gia — trong khi những thứ đó
thường không cần thiết.

## 3.3 Tầng 2 — Trích xuất bằng chứng có ràng buộc (0.5 phút)

Mô hình phải trả về cho mỗi bằng chứng: mã đoạn văn, **trích đoạn nguyên văn**,
giá trị đáp án ứng viên, và loại hỗ trợ (trực tiếp hoặc suy luận). Không được
diễn giải lại, không được ghép thông tin ngoài tài liệu.

## 3.4 Tầng 3 — Xác minh quan hệ (1 phút)

*Slide: 3 nhãn MATCH / CONTRADICTED / UNSTATED.*

Một tầng riêng đánh giá: nguồn có thật sự xác lập **đúng quan hệ được hỏi**
không? Ba kết quả có thể: `MATCH`, `CONTRADICTED`, `UNSTATED`.

Tầng này tồn tại để chặn những lỗi mà so khớp từ vựng **không thấy**:

- đảo chủ thể ↔ tân ngữ (ví dụ mở đầu bài),
- sai thuộc tính (hỏi A trả lời B),
- sai phạm vi thời gian hoặc nhóm đối tượng,
- tiền đề của câu hỏi không được tài liệu hỗ trợ.

## 3.5 Tầng 4 — Kiểm chứng tất định trong mã (1.5 phút)

*Slide: checklist 4 mục.*

Đây mới là tầng quyết định thật sự. Mọi câu trả lời phải qua **toàn bộ**:

1. Trích đoạn phải xuất hiện **nguyên văn** trong đoạn văn được trích dẫn.
2. Giá trị đáp án phải **nằm trong** trích đoạn đó.
3. Thực thể được hỏi phải neo được vào **cả** câu hỏi lẫn nguồn.
4. Đáp án không được chỉ lặp lại một phần câu hỏi.

Và một tính chất quan trọng: nếu một sự kiện trực tiếp vượt qua được các kiểm
tra này, thì **đáp án, trích đoạn và trích dẫn của nó trở thành bất biến**. Tầng
sinh ngôn ngữ phía sau chỉ được **diễn đạt lại**, không được thay thế hay loại
bỏ. Điều này ngăn một lỗi rất khó chịu: bằng chứng đã kiểm chứng xong lại bị
tầng viết câu trả lời làm hỏng.

## 3.6 Tầng 5 — Đường chứng minh suy luận và kiểm tra chiều (0.5 phút)

Hai tầng cuối, sẽ được nói kỹ ở Phần 4 vì gắn với hai phát hiện kỹ thuật:

- **Chứng minh suy luận:** với câu hỏi cần phép tính (hiệu, tổng, tỷ lệ), hệ
  thống bắt buộc phải có **toán hạng tường minh** kèm trích đoạn, rồi **tính lại
  bằng mã**.
- **Kiểm tra chiều quan hệ:** so vai của thực thể trong câu hỏi với vai của nó
  trong nguồn, bằng đối sánh chuỗi tất định.

> **Chốt phần 3:** Kiến trúc là vậy. Nhưng điều thú vị nhất của dự án lại nằm ở
> những gì chúng tôi **học được khi nó không hoạt động**.

---

# PHẦN 4 — Phương pháp đánh giá và các phát hiện kỹ thuật
**Người trình bày 4 · 6–7 phút**

## 4.1 Vì sao cần ba bộ đánh giá tách biệt (1.5 phút)

*Slide: 3 hộp — Tuned / Held-out / Safety.*

| Bộ | Vai trò |
| --- | --- |
| **Tuned** (26 ca) | Dùng trong lúc phát triển — **lạc quan có hệ thống** |
| **Held-out** (10 ca) | Chưa từng dùng để tinh chỉnh — ước lượng gần thực tế |
| **An toàn** (12 ca) | Chuyên đảo quan hệ, lệch thuộc tính, sai mốc thời gian |

Chi tiết quan trọng: bộ an toàn **cố ý chứa 3 ca đối chứng đúng chiều**.

Vì sao? Nếu bộ test chỉ toàn câu cần từ chối, thì một hệ thống suy biến kiểu
**"luôn luôn từ chối"** sẽ đạt điểm tuyệt đối. Ba ca đối chứng đảm bảo hệ thống
phải vừa biết từ chối **vừa** còn biết trả lời. Đây là biện pháp chống tự lừa
dối, không phải thủ tục hình thức.

## 4.2 Phát hiện 1 — Một lỗi phạm trù trong xác minh suy luận (1.5 phút)

*Slide: câu hỏi "chênh lệch giữa A và B" + dấu hỏi lớn.*

Với câu hỏi *"chênh lệch giữa A và B là bao nhiêu?"*, tầng xác minh quan hệ được
hỏi: *"nguồn có phát biểu quan hệ **chênh lệch** không?"* — và luôn trả lời
**không**.

Và câu trả lời đó **đúng**. Không nguồn nào phát biểu một quan hệ **dẫn xuất** —
vì nếu nó có phát biểu thì đó đã không còn là suy luận nữa. Chúng tôi đã hỏi
một câu hỏi **sai phạm trù**.

Hậu quả cụ thể: bộ kiểm chứng số học chúng tôi viết ra hoàn toàn đúng, nhưng
**không bao giờ được chạy tới** — vì tầng phía trước đã loại bằng chứng rồi.

**Cách sửa:** với suy luận, bỏ hẳn phán đoán về quan hệ tổng hợp; thay bằng kiểm
chứng **từng toán hạng** — mỗi toán hạng là một sự kiện được phát biểu tường
minh — cộng với **tính lại phép toán trong mã**.

Nhấn mạnh: cách này **an toàn hơn**, không phải lỏng hơn. Ta thay **một** phán
đoán của mô hình bằng **bốn** kiểm tra độc lập: trích đoạn nguyên văn, giá trị
nằm trong trích đoạn, toán hạng neo được vào câu hỏi, và phép toán khớp. Đã
kiểm chứng trên dữ liệu chưa từng thấy, với hai toán hạng nằm ở **hai đoạn văn
khác nhau**.

## 4.3 Phát hiện 2 — Mơ hồ tham chiếu chỉ lộ ra trong bằng chứng (1.5 phút)

*Slide: "Thủ đô nằm ở đâu?" — hoàn chỉnh về cú pháp, nhưng không xác định.*

Các câu như *"Thủ đô nằm ở đâu?"* hay *"Dân số Hà Nội **khi đó** là bao nhiêu?"*
**hoàn chỉnh về mặt cú pháp**: có chủ ngữ, có thuộc tính được hỏi. Cái thiếu
không phải một thành phần ngữ pháp, mà là **tính xác định của tham chiếu**.

Chúng tôi kiểm chứng bằng cách đọc trực tiếp các đoạn văn truy xuất được:

- Với câu mơ hồ: **nhiều** đoạn cùng trả lời quan hệ được hỏi nhưng cho giá trị
  khác nhau — phân biệt bởi thời gian, quốc gia, hoặc con người.
  Ví dụ với *"dân số Hà Nội khi đó"*: 53 nghìn (1954), 132.145 (thập niên 1940),
  và con số hiện đại hơn 8 triệu.
- Với câu trả lời được: **đúng một** đoạn phát biểu quan hệ đó.

Tức là tín hiệu phân biệt **có thật** và **phân biệt được**.

**Nhưng đây là một căng thẳng thiết kế chưa giải quyết xong:** quyết định hỏi
lại phải đến **trước** truy xuất (lý do ở Phần 3), trong khi tín hiệu này chỉ
tồn tại **sau** truy xuất. Chúng tôi nêu thẳng như một vấn đề mở.

## 4.4 Phát hiện 3 — Tăng kích thước mô hình không giải quyết được (1 phút)

*Slide: bảng 3 dòng.*

| Mô hình | Kết quả tầng ý định |
| --- | ---: |
| Qwen2.5-3B | 23/36 |
| Qwen2.5-7B | 23/36 |
| Qwen3-8B (đang dùng) | 29/36 |

3B → 7B **phẳng hoàn toàn**. Và quan trọng hơn con số tổng: **năm ca sai trên cả
ba mô hình**. Chênh lệch điểm đến từ các ca khác dao động, còn lõi khó thì bất
biến.

Kết luận: các ca đang chặn hệ thống **không bị giới hạn bởi kích thước mô hình**.
Vì vậy "dùng mô hình lớn hơn" là một **giả thuyết cần kiểm chứng**, không phải
một kế hoạch — và đó là một kết quả có giá trị, vì nó ngăn ta đầu tư sai chỗ.

## 4.5 Phát hiện 4 — Một minh chứng định lượng về overfitting (1.5 phút)

*Slide: 2 cột — "Bộ tuned: −1 ca" / "Held-out: không đổi".*

Đây là bài học phương pháp luận đáng giá nhất của dự án.

Trong quá trình phát triển, chúng tôi thêm **hai luật** để xử lý các ca quan sát
được. Cả hai đều viết dưới dạng **tổng quát** — không chứa thực thể nào, không
chứa cụm từ tiếng Việt nào. Nhìn bề ngoài hoàn toàn hợp lệ theo ràng buộc ở
Phần 2.

Sau đó chúng tôi viết các **ca phản chứng** — fixture được thiết kế riêng để
**bác bỏ** chính hai luật đó. Ví dụ: *"Thủ đô của **nước đó** nằm ở đâu?"* — một
câu hỏi về địa điểm nhưng quốc gia lại là tham chiếu chưa xác định. Đúng ra phải
hỏi lại. Cả hai luật đều **nuốt mất** lời hỏi lại chính đáng đó.

Gỡ bỏ hai luật này làm mất **đúng một ca**, và **chỉ trên bộ đã tinh chỉnh**.
Bộ held-out **không đổi một điểm nào**.

Nói cách khác: **toàn bộ giá trị của chúng nằm trên chính tập dữ liệu chúng được
thiết kế dựa theo, và bằng không trên dữ liệu mới.**

> Bài học: *một luật viết tổng quát vẫn có thể là fit test — nếu nó được **chọn**
> bằng cách nhìn xem nó sửa được ca nào.* Ràng buộc "không hard-code" là cần,
> nhưng **chưa đủ**. Phải có tập held-out và phải có ca phản chứng.

> **Chốt phần 4:** Bạn cuối cùng sẽ nói về kết quả và những gì chúng tôi vẫn
> chưa làm được.

---

# PHẦN 5 — Kết quả, hạn chế và hướng phát triển
**Người trình bày 5 · 5–6 phút**

## 5.1 Kết quả trên benchmark (1.5 phút)

*Slide: bảng so sánh 3 hệ.*

Đánh giá trên tập test đóng băng của UIT-ViQuAD 2.0 (mẫu 200 câu, cân bằng
103 câu trả lời được / 97 câu không trả lời được):

| Hệ | Trả lời | Từ chối | **Ảo giác** | Bỏ lỡ |
| --- | ---: | ---: | ---: | ---: |
| Basic RAG | 83 | 117 | **39** | 59 |
| Prompt-Safe RAG | 72 | 128 | **31** | 62 |
| PonyGuard | *(cập nhật)* | | | |

> **"Ảo giác"** = câu đáng lẽ phải từ chối nhưng hệ thống vẫn trả lời.

Điểm đáng chú ý nhất ở đây: **Prompt-Safe RAG chỉ giảm ảo giác từ 39 xuống 31**
— khoảng 20% — trong khi **bỏ lỡ nhiều hơn** (59 → 62).

Nói cách khác: chỉ **dặn dò mô hình cẩn thận bằng prompt** thì nó trở nên **rụt
rè hơn chứ không chính xác hơn**. Nó từ chối thêm một số câu, nhưng phần lớn là
từ chối nhầm những câu đáng lẽ trả lời được. Đây chính là lý do cần kiểm chứng
có cấu trúc thay vì chỉ viết prompt tốt hơn.

## 5.2 Kết quả trên các bộ chẩn đoán (1 phút)

*Slide: 3 con số.*

| Bộ | Kết quả |
| --- | ---: |
| Tuned (26 ca) | 19/26 |
| Held-out (10 ca) | 7/10 |
| An toàn (12 ca) | 10/12 |

Chi phí vận hành: **3.5 lần gọi mô hình mỗi câu hỏi**, giảm 15% sau khi chúng
tôi đo được một nhánh xử lý **chưa từng ảnh hưởng đến bất kỳ quyết định nào** và
loại bỏ nó.

Khoảng cách giữa 19/26 (bộ đã tinh chỉnh) và 7/10 (bộ chưa từng thấy) chính là
lý do chúng tôi không báo cáo một con số duy nhất.

## 5.3 Hạn chế — nêu thẳng (1.5 phút)

*Slide: tiêu đề "Những gì chúng tôi chưa làm được".*

Hệ thống **vẫn để lọt hai câu trả lời sai** trên tập kiểm tra độc lập:

- một câu hỏi **đảo chủ thể–tân ngữ** được chấp nhận (chính ví dụ mở đầu bài);
- một câu hỏi có **mốc thời gian chưa xác định** vẫn được trả lời.

Cả hai đều kèm **trích dẫn hợp lệ** và **trích đoạn nguyên văn** — tức là chúng
vượt qua **mọi** kiểm tra tất định hiện có. Đây đúng là loại lỗi hệ thống được
sinh ra để chặn, nên chúng tôi **không coi dự án là đã đạt yêu cầu**.

Nguyên nhân đã khoanh vùng được: hai **tầng phán đoán** (phân tích ý định và
xác minh quan hệ) không đáng tin trên mô hình cục bộ đang dùng — trong khi các
tầng **trích xuất** và **kiểm chứng tất định** hoạt động tốt.

Một chi tiết quan trọng: tỷ lệ lọt của lỗi đảo quan hệ đo được khoảng **30%**, và
mang tính **chập chờn** — cùng một cặp thực thể, chỉ khác cách diễn đạt, có lúc
bị chặn có lúc lọt.

## 5.4 Hướng phát triển (1 phút)

*Slide: 3 mũi tên.*

Chính tính **chập chờn** đó gợi ra hướng đi tiếp theo:

1. **Lấy mẫu nhiều lần và yêu cầu nhất trí.** Nếu một lỗi chỉ xuất hiện 30% số
   lần, thì hỏi 5 lần và chỉ chấp nhận khi cả 5 lần đồng ý sẽ giảm mạnh tỷ lệ
   lọt. Đây là cách khai thác trực tiếp đặc tính đã đo được.
2. **Chuyển các guard từ "mặc định cho qua" sang "mặc định chặn".** Hiện khi
   contract lỗi hoặc kết quả hoà, hệ thống giữ lại bằng chứng. Với hệ thống mà
   mục đích là an toàn, nên yêu cầu **bằng chứng dương** rằng mọi thứ khớp.
3. **Kiểm tra ở phía đáp án thay vì phía nguồn.** Hai lần bắt mô hình trích vai
   từ nguồn đều thất bại. Hướng ngược lại: ghép mệnh đề hoàn chỉnh từ **đáp án
   đã sinh** rồi hỏi nguồn có kéo theo mệnh đề đó không — một phán đoán dễ hơn
   nhiều.

## 5.5 Đóng góp và kết luận (1 phút)

*Slide: 4 gạch đầu dòng.*

1. Một kiến trúc QA đặt **quyết định chấp nhận** vào mã tất định, chỉ dùng mô
   hình ngôn ngữ để trích xuất và đề xuất.
2. Một **đường chứng minh suy luận tính lại bằng mã**, xuất phát từ nhận xét
   rằng quan hệ dẫn xuất không thể xác minh như quan hệ trực tiếp.
3. Một **quy trình đánh giá tách tuned / held-out / an toàn**, có ca đối chứng
   chống hệ thống suy biến, kèm minh chứng định lượng về overfitting ở mức
   thiết kế luật.
4. Bằng chứng cho thấy một lớp lỗi cụ thể **không giảm theo kích thước mô hình**
   — khoanh vùng được đâu là giới hạn kiến trúc, đâu là giới hạn năng lực.

**Câu kết:**

> Kết quả có giá trị nhất của dự án không phải con số pass rate, mà là việc
> chúng tôi biết **chính xác** cái gì đang chặn mình, và chứng minh được điều đó
> bằng phép đo — thay vì bằng phỏng đoán.

---

# Phụ lục A — Câu hỏi có thể bị hỏi

| Câu hỏi | Người trả lời | Gợi ý |
| --- | --- | --- |
| *Sao không dùng GPT-4 / Gemini cho khoẻ?* | P4 | Chúng tôi đã thử đo. Nhưng phát hiện 3 cho thấy lớp lỗi này **không giảm theo kích thước mô hình** — 5 ca sai trên cả 3 mô hình. Nên đổi mô hình là giả thuyết cần kiểm chứng, chưa có bằng chứng. Ngoài ra hệ chạy cục bộ có ý nghĩa về chi phí và quyền riêng tư. |
| *200 mẫu có ít quá không?* | P5 | Có, đây là mẫu con của tập 2000 đã đóng băng; sai số quanh ±3.5%. Chúng tôi báo cáo rõ là mẫu con chứ không gọi là kết quả cuối. Bản đầy đủ cần ~20 giờ chạy cục bộ. |
| *Vì sao ABSTAIN nhiều thế?* | P5 | Vì chi phí không đối xứng (Phần 1.4). Chúng tôi cố ý chọn điểm vận hành thiên về từ chối. Nhưng bộ an toàn có 3 ca đối chứng để bảo đảm hệ **không** suy biến thành "luôn từ chối". |
| *Làm sao biết không phải fit test?* | P4 | Đó chính là phát hiện 4. Bộ held-out chưa từng dùng để tinh chỉnh, và chúng tôi đã **gỡ bỏ** hai luật khi ca phản chứng cho thấy chúng sai — chấp nhận mất điểm. |
| *ASK khác gì ABSTAIN?* | P2 | `ASK` khi **câu hỏi** thiếu thông tin; `ABSTAIN` khi **tài liệu** thiếu. Trộn hai cái là sai vì hỏi lại không giải quyết được việc corpus không có dữ liệu. |
| *Có so với các phương pháp khác không?* | P2 | Prompt-Safe RAG chính là đại diện cho hướng phổ biến nhất hiện nay. So sánh 1↔2↔3 được thiết kế để tách riêng đóng góp của kiểm chứng có cấu trúc. |

# Phụ lục B — Số liệu cần cập nhật trước khi thuyết trình

- [ ] **Dòng PonyGuard ở bảng 5.1** — benchmark đang chạy, lấy từ
      `reports/final_results.md` khi xong.
- [ ] Nếu chạy được bản đầy đủ 2000 mẫu, thay số và **bỏ** chú thích "mẫu 200".
- [ ] Kiểm tra lại 3 con số ở 5.2 nếu có thay đổi mã sau buổi này.

# Phụ lục C — Phân công tóm tắt

| Phần | Người | Thời lượng | Trọng tâm |
| --- | --- | --- | --- |
| 1. Bài toán và động lực | P1 | 5' | Ví dụ đảo vai, chi phí không đối xứng |
| 2. Mục tiêu và thiết kế thí nghiệm | P2 | 5' | Ba hành động, ràng buộc không hard-code, ba hệ |
| 3. Kiến trúc PonyGuard | P3 | 6' | "LLM đề xuất, mã quyết định" — năm tầng |
| 4. Đánh giá và phát hiện kỹ thuật | P4 | 6–7' | Ba bộ test, bốn phát hiện |
| 5. Kết quả, hạn chế, hướng đi | P5 | 5–6' | Bảng so sánh, hai lỗi còn lọt, ba hướng |
