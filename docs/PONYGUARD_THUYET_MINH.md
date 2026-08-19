# PonyGuard-ViQA — Thuyết minh dự án

## 1. Bài toán

Hệ thống hỏi–đáp tiếng Việt dựa trên truy xuất (RAG) có một điểm yếu cố hữu:
**nó luôn trả lời**. Khi tài liệu không chứa câu trả lời, khi câu hỏi mơ hồ, hoặc
khi câu hỏi chứa tiền đề sai, mô hình vẫn sinh ra một câu trả lời trôi chảy và
kèm trích dẫn trông rất thuyết phục. Đây là dạng ảo giác nguy hiểm nhất: nó
không nghe *có vẻ* sai.

Trong ứng dụng thực (y tế, pháp lý, tra cứu chính sách), chi phí của một câu trả
lời sai tự tin cao hơn nhiều so với chi phí của một lời từ chối.

## 2. Mục tiêu

Xây dựng một hệ thống QA tiếng Việt biết **khi nào không nên trả lời**, thay vì
chỉ tối ưu độ chính xác khi trả lời.

Hệ thống phải chọn một trong ba hành động, và phải chọn đúng lý do:

| Hành động | Điều kiện |
| --- | --- |
| `ANSWER` | Văn bản truy xuất **chứng minh được** quan hệ được hỏi, kèm trích dẫn và trích đoạn nguyên văn hợp lệ |
| `ASK` | **Bản thân câu hỏi** thiếu một thành phần ngữ nghĩa bắt buộc |
| `ABSTAIN` | Câu hỏi rõ ràng nhưng bằng chứng vắng mặt, lệch, mâu thuẫn hoặc không đủ |

Ràng buộc phương pháp luận quan trọng: **không được hard-code** thực thể, câu
hỏi, đáp án hay mẫu ngôn ngữ nào vào hệ thống. Một câu hỏi quan sát được là một
*test case*, không phải một luật để thêm vào pipeline. Nếu không có ràng buộc
này, ta chỉ đang nhồi bộ test chứ không xây hệ thống.

## 3. Thiết kế thực nghiệm

Ba hệ thống chạy trên **cùng một corpus, cùng retriever, cùng schema đầu ra**,
để cô lập đúng biến cần đo là *cơ chế kiểm chứng*:

1. **Basic RAG** — truy xuất rồi sinh câu trả lời. Đường cơ sở.
2. **Prompt-Safe RAG** — như trên, nhưng prompt yêu cầu mô hình tự từ chối khi
   không đủ bằng chứng. Đại diện cho cách tiếp cận "dạy mô hình cẩn thận".
3. **PonyGuard** — kiến trúc nhiều tầng kiểm chứng, mô tả ở mục 4.

So sánh 1 với 2 trả lời câu hỏi: *chỉ dặn dò bằng prompt có đủ không?*
So sánh 2 với 3 trả lời: *kiểm chứng có cấu trúc mang lại thêm gì?*

Dữ liệu: UIT-ViQuAD 2.0, chia đóng băng theo manifest có hash. Truy xuất bằng
FAISS trên embedding `multilingual-e5-small`.

## 4. Kiến trúc PonyGuard

Nguyên lý xuyên suốt: **đẩy quyết định ra khỏi mô hình ngôn ngữ, vào mã tất định
bất cứ khi nào có thể**. LLM được dùng để *trích xuất* và *đề xuất*; việc *chấp
nhận hay từ chối* do mã kiểm tra.

### 4.1 Phân tích ý định — trước khi truy xuất

Quyết định `ASK` được đưa ra **trước** khi nhìn tài liệu. Lý do: nếu để sau, hệ
thống sẽ hỏi lại chỉ vì không tìm thấy bằng chứng, mà thiếu bằng chứng là lý do
để `ABSTAIN` chứ không phải để hỏi lại.

Mô hình phải khai từng slot ngữ nghĩa (thực thể, thuộc tính được hỏi, thời gian,
địa điểm, phạm vi…) kèm **một đoạn trích nguyên văn từ chính câu hỏi** và một
trạng thái thuộc tập đóng: `RESOLVED` / `REFERENTIAL` / `ABSENT`. Mã nguồn kiểm
tra đoạn trích đó có thật sự xuất hiện trong câu hỏi hay không, rồi **tự tính**
kết luận "câu hỏi có đủ thông tin chưa" — mô hình không được phép tự tuyên bố
điều đó.

Phân biệt `ABSENT` (câu hỏi không ràng buộc chiều này) với `REFERENTIAL` (câu
hỏi có nhắc tới nhưng chưa xác định) là điểm mấu chốt: nó ngăn hệ thống hỏi lại
chỉ vì câu hỏi không nêu năm hay quốc gia trong khi những thứ đó không cần thiết.

### 4.2 Trích xuất bằng chứng có ràng buộc

Mô hình phải trả về, cho mỗi bằng chứng: mã đoạn văn, **trích đoạn nguyên văn**,
giá trị đáp án ứng viên, và loại hỗ trợ (`DIRECT` hoặc `SIMPLE_INFERENCE`).
Không được diễn giải lại, không được ghép thông tin ngoài tài liệu.

### 4.3 Xác minh quan hệ

Một tầng riêng đánh giá xem nguồn có thật sự xác lập **đúng quan hệ được hỏi**
hay không, với ba kết quả: `MATCH` / `CONTRADICTED` / `UNSTATED`. Tầng này tồn
tại để chặn các lỗi mà kiểm tra từ vựng không thấy: đảo chủ thể–tân ngữ, sai
thuộc tính, sai phạm vi thời gian hoặc nhóm đối tượng, tiền đề không được hỗ trợ.

### 4.4 Kiểm chứng tất định trong mã

Đây là tầng quyết định thật sự. Mọi câu trả lời phải qua:

- trích đoạn phải xuất hiện **nguyên văn** trong đoạn văn được trích dẫn;
- giá trị đáp án phải nằm trong trích đoạn đó;
- thực thể được hỏi phải neo được vào cả câu hỏi lẫn nguồn;
- đáp án không được chỉ lặp lại một phần câu hỏi.

Nếu một sự kiện trực tiếp vượt qua các kiểm tra này, **đáp án, trích đoạn và
trích dẫn của nó trở thành bất biến** — tầng sinh ngôn ngữ phía sau chỉ được
diễn đạt lại, không được thay thế hay loại bỏ.

### 4.5 Đường chứng minh suy luận

Với câu hỏi cần một phép tính đơn giản (hiệu, tổng, tỷ lệ), hệ thống yêu cầu
**các toán hạng tường minh**, mỗi toán hạng kèm trích đoạn nguyên văn, rồi
**tính lại phép toán bằng Python**. Đáp án chỉ được chấp nhận nếu kết quả khớp.

Đây là chỗ có một nhận xét kỹ thuật đáng chú ý (mục 6.1).

### 4.6 Kiểm tra chiều quan hệ

Tầng bổ sung so sánh vai của thực thể trong câu hỏi với vai của nó trong nguồn,
bằng đối sánh chuỗi ký tự tất định. Mục đích: bắt các câu hỏi **đảo chiều** —
loại lỗi vượt qua được mọi kiểm tra khác vì thực thể có mặt ở cả hai bên, trích
đoạn vẫn nguyên văn, và đáp án vẫn nằm trong trích đoạn.

## 5. Phương pháp đánh giá

Đánh giá được tách làm **ba bộ độc lập**, và sự tách này quan trọng ngang kiến
trúc:

| Bộ | Vai trò |
| --- | --- |
| **Tuned** (26 ca) | Dùng trong quá trình phát triển — *lạc quan có hệ thống* |
| **Held-out** (10 ca) | Chưa từng dùng để tinh chỉnh — ước lượng gần thực tế |
| **Safety held-out** (12 ca) | Chuyên về đảo quan hệ, lệch thuộc tính, sai mốc thời gian |

Bộ an toàn cố ý chứa **3 ca đối chứng đúng chiều**. Nếu không có chúng, một hệ
thống suy biến kiểu "luôn từ chối" sẽ đạt điểm tuyệt đối. Đây là biện pháp chống
tự lừa dối, không phải thủ tục hình thức.

Ngoài ra: mọi lần chạy chẩn đoán đều **ghim cố định một nhà cung cấp mô hình**.
Cơ chế dự phòng tự động từng âm thầm chuyển sang mô hình khác giữa chừng và tạo
ra một so sánh hoàn toàn vô nghĩa.

## 6. Các phát hiện kỹ thuật

### 6.1 Quan hệ dẫn xuất không thể được xác minh như quan hệ trực tiếp

Với câu hỏi kiểu *"chênh lệch giữa A và B là bao nhiêu?"*, tầng xác minh quan hệ
được hỏi: *"nguồn có phát biểu quan hệ **chênh lệch** không?"* — và luôn trả lời
là không.

Điều này **đúng**: không nguồn nào phát biểu một quan hệ dẫn xuất, vì nếu có thì
nó đã không còn là suy luận. Việc hỏi mô hình câu đó là một **lỗi phạm trù**.
Hậu quả là bộ kiểm chứng số học — vốn đã được viết đúng — không bao giờ được
chạy tới.

Cách xử lý: với suy luận, bỏ phán đoán về quan hệ tổng hợp, thay bằng kiểm chứng
**từng toán hạng** (mỗi cái là một sự kiện được phát biểu tường minh) cộng với
việc **tính lại phép toán trong mã**. Kết quả là an toàn hơn, chứ không phải nới
lỏng hơn: bốn kiểm tra độc lập thay cho một phán đoán của mô hình. Cách này đã
được kiểm chứng trên dữ liệu chưa từng thấy, với các toán hạng nằm ở hai đoạn
văn khác nhau.

### 6.2 Mơ hồ tham chiếu chỉ lộ ra trong bằng chứng, không lộ trong câu hỏi

Các câu như *"Thủ đô nằm ở đâu?"* hay *"Dân số Hà Nội khi đó là bao nhiêu?"*
hoàn chỉnh về mặt cú pháp. Cái thiếu không phải một thành phần ngữ pháp, mà là
**tính xác định của tham chiếu**.

Loại mơ hồ này chỉ quan sát được qua tài liệu: nhiều đoạn văn cùng trả lời quan
hệ được hỏi nhưng cho các giá trị khác nhau, phân biệt bởi một chiều mà câu hỏi
chưa xác định (thời gian, quốc gia, con người). Đã kiểm chứng: các ca mơ hồ có
nhiều đáp án hợp lệ khác nhau, còn các ca trả lời đúng chỉ có **đúng một** đoạn
văn phát biểu quan hệ đó.

Đây là một căng thẳng thiết kế thật, chưa giải quyết được: quyết định hỏi lại
phải đến *trước* truy xuất (mục 4.1), nhưng tín hiệu phân biệt lại chỉ tồn tại
*sau* truy xuất.

### 6.3 Tăng kích thước mô hình không giải quyết được các ca khó

Đo tầng phân tích ý định trên ba mô hình cục bộ:

| Mô hình | Kết quả |
| --- | ---: |
| Qwen2.5-3B | 23/36 |
| Qwen2.5-7B | 23/36 |
| Qwen3-8B (sản xuất) | 29/36 |

3B → 7B **phẳng hoàn toàn**. Quan trọng hơn: **năm ca sai trên cả ba mô hình**.
Chênh lệch điểm đến từ các ca khác dao động, còn lõi khó thì bất biến. Kết luận:
các ca đang chặn hệ thống **không bị giới hạn bởi kích thước mô hình**, nên
"dùng mô hình lớn hơn" là một giả thuyết cần kiểm chứng, không phải một kế hoạch.

### 6.4 Một minh chứng định lượng về overfitting

Trong quá trình phát triển, hai luật được thêm vào để xử lý các ca quan sát
được. Cả hai đều được viết dưới dạng tổng quát, không chứa thực thể hay cụm từ
cụ thể — nhìn bề ngoài là hợp lệ.

Khi kiểm tra bằng các ca phản chứng được thiết kế riêng để **bác bỏ** chúng, cả
hai đều sai: chúng nuốt mất những lời hỏi lại chính đáng.

Gỡ bỏ hai luật này làm mất **đúng một ca**, và **chỉ trên bộ đã tinh chỉnh**;
bộ held-out **không đổi một điểm nào**. Nói cách khác: toàn bộ giá trị của chúng
nằm trên chính tập dữ liệu chúng được thiết kế dựa theo, và bằng không trên dữ
liệu mới.

Đây là lý do bộ held-out tồn tại, và là bài học phương pháp luận đáng giá nhất
của dự án: *một luật viết tổng quát vẫn có thể là fit test, nếu nó được chọn
bằng cách nhìn xem nó sửa được ca nào.*

## 7. Kết quả hiện tại

| Bộ | Kết quả |
| --- | ---: |
| Tuned | 19/26 |
| Held-out | 7/10 |
| Safety held-out | 10/12 |

Chi phí: 3.50 lần gọi mô hình mỗi câu hỏi (giảm 15% sau khi loại một nhánh xử lý
được đo là không bao giờ ảnh hưởng đến quyết định).

Các ca còn sai đã truy được nguyên nhân gốc: hai ca là **truy xuất trượt** (tài
liệu chứa đáp án nằm ngoài phạm vi truy xuất), phần còn lại là **giới hạn năng
lực của mô hình ở hai tầng phán đoán** (phân tích ý định và xác minh quan hệ).

## 8. Hạn chế — nêu thẳng

Hệ thống **vẫn để lọt hai câu trả lời sai** trên tập kiểm tra độc lập: một câu
hỏi đảo chủ thể–tân ngữ được chấp nhận, và một câu hỏi có mốc thời gian chưa xác
định được trả lời.

Cả hai đều kèm trích dẫn hợp lệ và trích đoạn nguyên văn — tức là chúng vượt qua
mọi kiểm tra tất định hiện có. Đây chính là loại lỗi mà hệ thống được sinh ra để
chặn, nên **chưa thể coi là đạt yêu cầu**.

Nguyên nhân đã xác định: hai tầng phán đoán không đáng tin trên mô hình cục bộ
đang dùng, trong khi các tầng trích xuất và kiểm chứng tất định hoạt động tốt.
Tỷ lệ lọt của lỗi đảo quan hệ đo được vào khoảng 30%, và mang tính **chập chờn**
— cùng một cặp thực thể, chỉ khác cách diễn đạt, có lúc bị chặn có lúc lọt.

Tính chập chờn này gợi ý hướng xử lý tiếp theo: lấy mẫu phán đoán nhiều lần và
yêu cầu nhất trí, thay vì tin vào một lần đánh giá duy nhất.

## 9. Đóng góp của dự án

1. Một kiến trúc QA đặt **quyết định chấp nhận** vào mã tất định, chỉ dùng mô
   hình ngôn ngữ để trích xuất và đề xuất.
2. Một đường chứng minh suy luận **tính lại bằng mã**, xuất phát từ nhận xét
   rằng quan hệ dẫn xuất không thể xác minh như quan hệ trực tiếp.
3. Một quy trình đánh giá tách **tuned / held-out / an toàn**, có ca đối chứng
   chống hệ thống suy biến, kèm minh chứng định lượng cho hiện tượng overfitting
   ở mức thiết kế luật.
4. Bằng chứng cho thấy một lớp lỗi cụ thể **không giảm theo kích thước mô hình**,
   qua đó khoanh vùng đâu là giới hạn kiến trúc và đâu là giới hạn năng lực.
