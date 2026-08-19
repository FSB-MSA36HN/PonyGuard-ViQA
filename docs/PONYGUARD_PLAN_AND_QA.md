# PonyGuard-ViQA — Chuẩn bị thuyết trình và phản biện

Tài liệu dùng **trước và trong** buổi báo cáo. Kịch bản nói ở
[`PONYGUARD_BAI_THUYET_TRINH_10P.md`](PONYGUARD_BAI_THUYET_TRINH_10P.md);
chi tiết kỹ thuật ở
[`PONYGUARD_THUYET_MINH.md`](PONYGUARD_THUYET_MINH.md).

| # | Phần | Người nói |
| --- | --- | --- |
| 1 | Bài toán và động lực (kèm mở bài) | **Đức** |
| 2 | Mục tiêu và thiết kế thực nghiệm | **Hòa** |
| 3 | Kiến trúc PonyGuard | **Dương** |
| 4 | Cách đánh giá và các phát hiện kỹ thuật | **Hiệp** |
| 5 | Kết quả, hạn chế và hướng phát triển | **Hải** |

---

## Checklist trước khi lên trình bày

- [ ] Mỗi người **một slide**, không quá 6 dòng chữ.
- [ ] Đức và Hải thống nhất dùng **cùng một ví dụ** (Lend Lease) — mở và đóng.
- [ ] Bấm giờ tổng duyệt: 10 phút là rất chặt.
- [ ] Người nói sau **nhắc tên người nói trước** khi bắt đầu (đã viết sẵn).
- [ ] Nếu chạy xong benchmark đầy đủ 2.000 mẫu thì thay số và **bỏ** chú thích
      "mẫu 200".

## Nếu bị cắt còn 7 phút

Cắt theo thứ tự: (1) đoạn mô tả ba hệ ở Phần 2 — chỉ nói tên; (2) tầng 2 và
tầng 5 ở Phần 3; (3) phát hiện thứ nhất ở Phần 4.
**Không cắt:** ví dụ mở bài, bảng metric, phần phân tích chỗ mất recall, và phần hạn chế.

## Câu hỏi phản biện và người trả lời

| Câu hỏi | Người | Trả lời ngắn |
| --- | --- | --- |
| Sao không dùng GPT-4 / Gemini cho khoẻ? | Hiệp | Đã đo: lỗi này **không giảm khi tăng size model** — năm câu sai trên cả ba model. Đổi model là giả thuyết chưa kiểm chứng được. Ngoài ra chạy local có lợi về chi phí và privacy. |
| 200 mẫu có ít quá không? | Hải | Là mẫu 200 của test set 2.000 đã đóng băng, sai số ~±3.5 điểm phần trăm. Nhóm ghi rõ là mẫu con chứ không gọi là kết quả cuối. Chạy đủ 2.000 mất ~20 giờ trên máy local. |
| Recall giảm 30% thì có đáng không? | Hải | Tùy vào chi phí hai loại lỗi không ngang nhau như Phần 1 đã nêu. Và một nửa phần mất là do **giới hạn retriever**, chung cho cả ba hệ. Phần thuộc về PonyGuard là 81% xuống 58%, đó là mục tiêu cải thiện đã xác định. |
| Sao PonyGuard có 26 câu ASK mà tập test không có nhãn ASK? | Hải | Đúng, test set chỉ có nhãn ANSWER/ABSTAIN. 26 câu đó bị tính là không-trả-lời: 16 rơi vào câu gold ABSTAIN nên vô hại, 10 rơi vào câu gold ANSWER nên tính là bỏ sót. Nhóm không cộng điểm ưu tiên nào cho ASK. |
| Làm sao biết không phải fit test? | Hiệp | Đó là phát hiện thứ hai: held-out set chưa từng dùng để chỉnh, và nhóm đã **gỡ bỏ** hai luật khi test phản chứng cho thấy chúng sai — chấp nhận mất điểm. |
| `answer_f1` của PonyGuard thấp hơn Prompt-Safe? | Hải | Đúng, 0.126 so với 0.187. Một phần do recall thấp; một phần do PonyGuard xuất **quote nguyên văn** ngắn gọn nên bị thiệt khi chấm token-F1 với đáp án gold diễn đạt tự do. Đây là hạn chế của metric, nhóm nêu thẳng. |
| Chi phí gấp đôi có chấp nhận được không? | Dương | 4.03 lần gọi LLM so với 2.17, latency median 24.8 giây so với 11.7. Với tra cứu chuyên ngành thì chấp nhận được; với ứng dụng real-time thì chưa. Nhóm đã cắt được 15% chi phí bằng cách bỏ một nhánh **đo được là không ảnh hưởng tới quyết định nào**. |
| `ASK` khác `ABSTAIN` chỗ nào? | Hòa | `ASK` khi **câu hỏi** thiếu; `ABSTAIN` khi **tài liệu** thiếu. Gộp hai cái là sai vì hỏi lại người dùng không giúp gì khi corpus vốn không có dữ liệu. |
