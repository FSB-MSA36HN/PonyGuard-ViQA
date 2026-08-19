# PonyGuard-ViQA — Thuyết trình 10 phút (5 người × 2 phút)

**Bản dài** (25–30 phút, chi tiết hơn) ở
[`PONYGUARD_BAI_THUYET_TRINH.md`](PONYGUARD_BAI_THUYET_TRINH.md) — dùng làm tài
liệu tra cứu khi hỏi đáp.

> **Cách dùng:** phần chữ thường là **lời nói** (đã canh ~2 phút mỗi người).
> Phần *in nghiêng* là gợi ý slide. Mỗi người **1 slide duy nhất**.

---

## PHẦN 1 — Vấn đề · P1 · 2 phút

*Slide: câu hỏi + câu trả lời có trích dẫn, đóng dấu đỏ "SAI".*

Tôi bắt đầu bằng một câu hỏi:

> *"Tập đoàn Lend Lease được Làng Olympic xây dựng ở đâu?"*

Tài liệu gốc nói ngược lại: **Lend Lease xây Làng Olympic**. Câu hỏi đã đảo vai
chủ thể và tân ngữ.

Hệ thống của chúng tôi, ở phiên bản chưa hoàn thiện, trả lời **"Thung lũng Lower
Lea"** — kèm trích dẫn đúng đoạn văn, trích đoạn nguyên văn không sai một chữ.

Mọi kiểm tra bề mặt đều hợp lệ. Nhưng câu trả lời sai, vì tiền đề của câu hỏi
sai và hệ thống không nhận ra.

Đây là dạng ảo giác nguy hiểm nhất trong RAG: **nó không nghe có vẻ sai**. Nó có
trích dẫn thật, trong tài liệu thật, văn phong trôi chảy. Người dùng không có lý
do để nghi ngờ.

Nguyên nhân gốc rất đơn giản: hệ thống RAG thông thường **luôn trả lời**. Nó
không có khái niệm "câu này không nên trả lời".

Và trong tra cứu y tế, pháp lý hay chính sách, hai loại lỗi **không ngang nhau**:

- Từ chối nhầm — người dùng mất công tra thủ công.
- Trả lời sai kèm trích dẫn — người dùng **tin và hành động theo**.

Nên chúng tôi không tối ưu độ chính xác trung bình. Chúng tôi tối ưu theo hướng:
**thà bỏ lỡ còn hơn nói sai**.

---

## PHẦN 2 — Mục tiêu và cách so sánh · P2 · 2 phút

*Slide: trái — bảng 3 hành động; phải — 3 hộp hệ thống trên cùng một đáy.*

Chúng tôi định nghĩa lại đầu ra: thay vì luôn sinh câu trả lời, hệ thống phải
chọn **một trong ba hành động**, và phải đúng **vì đúng lý do**.

| Hành động | Điều kiện |
| --- | --- |
| `ANSWER` | Tài liệu **chứng minh được** quan hệ được hỏi, kèm trích dẫn và trích đoạn nguyên văn |
| `ASK` | **Câu hỏi** thiếu một thành phần ngữ nghĩa bắt buộc |
| `ABSTAIN` | Câu hỏi rõ, nhưng **bằng chứng** vắng mặt, lệch hoặc không đủ |

Xin nhấn mạnh sự phân biệt giữa hai cái sau: `ASK` là khi **câu hỏi** thiếu,
`ABSTAIN` là khi **tài liệu** thiếu. Trộn hai cái là sai — hỏi lại người dùng
không giải quyết được việc corpus không có dữ liệu.

Để đo được đóng góp của cơ chế kiểm chứng, chúng tôi so ba hệ chạy trên **cùng
corpus, cùng bộ truy xuất, cùng schema đầu ra**:

1. **Basic RAG** — truy xuất rồi trả lời. Đường cơ sở.
2. **Prompt-Safe RAG** — prompt yêu cầu mô hình tự từ chối khi thiếu bằng chứng.
   Đại diện cho cách phổ biến nhất hiện nay: dặn dò bằng lời.
3. **PonyGuard** — kiểm chứng nhiều tầng có cấu trúc.

Giữ mọi thứ khác giống hệt nhau là có chủ đích: nó cô lập đúng biến cần đo.

Và một ràng buộc chúng tôi tự đặt: **không hard-code** bất kỳ thực thể, câu hỏi
hay đáp án nào. Một câu hỏi quan sát được là một **test case**, không phải một
luật thêm vào hệ thống.

Dữ liệu: UIT-ViQuAD 2.0, chia đóng băng bằng manifest có hash.

---

## PHẦN 3 — Kiến trúc · P3 · 2 phút

*Slide: sơ đồ dọc 5 tầng, tiêu đề lớn "LLM đề xuất — Mã quyết định".*

Toàn bộ kiến trúc xoay quanh một nguyên lý:

> **Đẩy quyết định ra khỏi mô hình ngôn ngữ, vào mã tất định.**

Mô hình dùng để **trích xuất** và **đề xuất**. Việc **chấp nhận hay từ chối** do
mã kiểm tra. Lý do: phán đoán của mô hình không ổn định — cùng một loại lỗi, lúc
bắt được lúc không. Mã kiểm tra thì luôn cho cùng kết quả. Ta xây phần bảo đảm
an toàn trên nền tất định.

Năm tầng:

**Một — phân tích ý định, trước khi truy xuất.** Mô hình phải khai từng slot ngữ
nghĩa kèm **đoạn trích nguyên văn từ chính câu hỏi** và một trạng thái thuộc tập
đóng. Rồi **mã** kiểm tra đoạn trích đó có thật trong câu hỏi không và tự tính
kết luận — mô hình không được tự tuyên bố câu hỏi đã đủ thông tin.

Quyết định `ASK` phải đến **trước** khi nhìn tài liệu. Nếu để sau, hệ thống sẽ
hỏi lại chỉ vì không tìm thấy bằng chứng — mà đó là lý do để từ chối, không phải
để hỏi.

**Hai — trích xuất có ràng buộc:** mỗi bằng chứng phải kèm trích đoạn nguyên văn.

**Ba — xác minh quan hệ:** nguồn có xác lập **đúng quan hệ được hỏi** không?
Chặn đảo chủ thể, sai thuộc tính, sai phạm vi.

**Bốn — kiểm chứng tất định trong mã:** trích đoạn phải nguyên văn trong nguồn;
đáp án phải nằm trong trích đoạn; thực thể phải neo được vào cả hai bên. Qua
được thì đáp án **trở thành bất biến** — tầng viết câu trả lời chỉ được diễn đạt
lại, không được thay thế.

**Năm — chứng minh suy luận:** với phép tính, bắt buộc có toán hạng tường minh
và **tính lại bằng mã**.

---

## PHẦN 4 — Hai phát hiện đáng chú ý · P4 · 2 phút

*Slide: chia đôi — trái "Lỗi phạm trù", phải "Overfitting: −1 vs 0".*

**Phát hiện thứ nhất — một lỗi phạm trù của chính chúng tôi.**

Với câu hỏi *"chênh lệch giữa A và B là bao nhiêu?"*, tầng xác minh quan hệ được
hỏi: *"nguồn có phát biểu quan hệ chênh lệch không?"* — và luôn trả lời không.

Câu trả lời đó **đúng**. Không nguồn nào phát biểu một quan hệ **dẫn xuất** — vì
nếu có thì nó đã không còn là suy luận. Chúng tôi đã hỏi sai phạm trù. Hậu quả:
bộ kiểm chứng số học viết hoàn toàn đúng nhưng **không bao giờ chạy tới**.

Cách sửa: bỏ phán đoán về quan hệ tổng hợp, thay bằng kiểm chứng **từng toán
hạng** cộng **tính lại phép toán trong mã**. Kết quả **an toàn hơn**, không phải
lỏng hơn — bốn kiểm tra độc lập thay cho một phán đoán của mô hình.

**Phát hiện thứ hai — minh chứng định lượng về overfitting.**

Chúng tôi từng thêm hai luật để xử lý các ca quan sát được. Cả hai viết hoàn
toàn **tổng quát**, không chứa thực thể nào — nhìn là hợp lệ.

Sau đó chúng tôi viết các **ca phản chứng**, thiết kế riêng để **bác bỏ** chính
hai luật đó. Cả hai đều sai: chúng nuốt mất những lời hỏi lại chính đáng.

Gỡ bỏ hai luật làm mất **đúng một ca**, và **chỉ trên bộ đã tinh chỉnh**. Bộ
held-out **không đổi một điểm nào**.

Toàn bộ giá trị của chúng nằm trên chính tập dữ liệu chúng được thiết kế dựa
theo, và bằng không trên dữ liệu mới.

> Bài học: **một luật viết tổng quát vẫn có thể là fit test**, nếu nó được *chọn*
> bằng cách nhìn xem nó sửa được ca nào. Không hard-code là cần, nhưng chưa đủ.

---

## PHẦN 5 — Kết quả và hạn chế · P5 · 2 phút

*Slide: bảng so sánh 3 hệ + dòng đỏ "còn 2 câu trả lời sai".*

Trên tập test đóng băng, mẫu 200 câu cân bằng:

| Hệ | Trả lời | Từ chối | **Ảo giác** | Bỏ lỡ |
| --- | ---: | ---: | ---: | ---: |
| Basic RAG | 83 | 117 | **39** | 59 |
| Prompt-Safe RAG | 72 | 128 | **31** | 62 |
| PonyGuard | *(điền)* | | | |

*"Ảo giác" = câu đáng lẽ phải từ chối nhưng vẫn trả lời.*

Điểm đáng chú ý nhất: **Prompt-Safe chỉ giảm ảo giác từ 39 xuống 31** — khoảng
20% — trong khi **bỏ lỡ nhiều hơn**. Nghĩa là dặn dò bằng prompt chỉ làm mô hình
**rụt rè hơn chứ không chính xác hơn**. Nó từ chối thêm, nhưng phần lớn là từ
chối nhầm. Đây chính là lý do cần kiểm chứng có cấu trúc.

Trên các bộ chẩn đoán: **19/26** trên bộ đã tinh chỉnh, **7/10** trên bộ chưa
từng thấy, **10/12** trên bộ an toàn. Khoảng cách giữa 19/26 và 7/10 là lý do
chúng tôi không báo cáo một con số duy nhất.

**Và đây là phần chúng tôi chưa làm được.**

Hệ thống **vẫn để lọt hai câu trả lời sai** — trong đó có đúng ví dụ mở đầu bài
thuyết trình. Cả hai đều kèm trích dẫn hợp lệ và trích đoạn nguyên văn, tức là
vượt qua **mọi** kiểm tra tất định hiện có. Nên chúng tôi **không coi dự án là
đã đạt yêu cầu**.

Nguyên nhân đã khoanh vùng: hai **tầng phán đoán** không đáng tin trên mô hình
đang dùng, trong khi các tầng trích xuất và kiểm chứng tất định hoạt động tốt.
Và chúng tôi đã đo: tăng kích thước mô hình **không** giải quyết được — cùng năm
ca sai trên cả ba mô hình khác nhau.

Tỷ lệ lọt khoảng 30%, và **chập chờn** — cùng cặp thực thể, khác cách diễn đạt,
lúc chặn được lúc không. Chính tính chập chờn đó gợi ra hướng tiếp theo: **lấy
mẫu phán đoán nhiều lần và chỉ chấp nhận khi tất cả đồng ý**.

> Kết quả có giá trị nhất của dự án không phải con số pass rate, mà là chúng tôi
> biết **chính xác** cái gì đang chặn mình — và chứng minh được bằng phép đo,
> thay vì bằng phỏng đoán.

---

## Checklist trước khi trình bày

- [ ] Điền dòng **PonyGuard** ở bảng Phần 5 (lấy từ `reports/final_results.md`).
- [ ] Mỗi người **một slide**, không quá 6 dòng chữ.
- [ ] P1 và P5 thống nhất dùng **cùng một ví dụ** (Lend Lease) để khép vòng.
- [ ] Tổng duyệt một lượt: 10 phút là rất chặt, phải bấm giờ.

## Nếu bị cắt còn 7 phút

Cắt theo thứ tự: (1) đoạn 3 hệ thống ở Phần 2 — chỉ nói tên; (2) tầng 2 và 5 ở
Phần 3; (3) phát hiện thứ nhất ở Phần 4. **Không cắt** Phần 1, bảng số ở Phần 5,
và phần hạn chế.

## Câu hỏi hay bị hỏi (bản rút gọn)

| Câu hỏi | Trả lời ngắn |
| --- | --- |
| Sao không dùng GPT-4/Gemini? | Đã đo: lớp lỗi này **không giảm theo kích thước mô hình** — 5 ca sai trên cả 3 mô hình. Đổi mô hình là giả thuyết chưa được kiểm chứng. |
| 200 mẫu ít quá không? | Là mẫu con của tập 2000 đóng băng, sai số ~±3.5%. Chúng tôi ghi rõ là mẫu con, không gọi là kết quả cuối. |
| Sao từ chối nhiều thế? | Chi phí hai loại lỗi không đối xứng. Nhưng bộ an toàn có **3 ca đối chứng đúng chiều** để bảo đảm hệ không suy biến thành "luôn từ chối". |
| Làm sao biết không phải fit test? | Đó là phát hiện thứ hai: bộ held-out chưa từng dùng để tinh chỉnh, và chúng tôi đã **gỡ luật** khi ca phản chứng cho thấy sai — chấp nhận mất điểm. |
