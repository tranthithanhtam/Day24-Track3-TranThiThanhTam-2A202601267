
# Failure Cluster Analysis — Phase A

**Sinh viên:** Trần Thị Thanh Tâm
**Ngày:** 26/08/2026

---

## 1. Aggregate RAGAS Scores theo Distribution

Bảng dưới đây thể hiện điểm số trung bình của các metric RAGAS trên từng phân vùng câu hỏi.

*Lưu ý: Dữ liệu này được tính toán dựa trên kết quả offline fixture, nơi ground truth được sử dụng làm câu trả lời và ngữ cảnh.*

| Metric              | factual       | multi_hop     | adversarial   | avg_score     |
| :------------------ | :------------ | :------------ | :------------ | :------------ |
| faithfulness        | 1.0           | 1.0           | 1.0           | 1.0           |
| answer_relevancy    | 1.0           | 1.0           | 1.0           | 1.0           |
| context_precision   | 1.0           | 1.0           | 1.0           | 1.0           |
| context_recall      | 1.0           | 1.0           | 1.0           | 1.0           |
| **avg_score** | **1.0** | **1.0** | **1.0** | **1.0** |

---

## 2. Bottom 10 Questions

Danh sách 10 câu hỏi có điểm `avg_score` thấp nhất, được trích xuất từ phân tích lỗi chi tiết.

| Rank | Distribution | Question                                                                                                                                       | avg_score | worst_metric      |
| :--- | :----------- | :--------------------------------------------------------------------------------------------------------------------------------------------- | :-------- | :---------------- |
| 1    | adversarial  | Nhân viên thử việc có được hưởng bảo hiểm sức khỏe PVI không?                                                                   | 0.2292    | answer_relevancy  |
| 2    | multi_hop    | Kết quả đánh giá hiệu suất tháng 6 và tháng 12 được dùng để làm gì khác nhau?                                               | 0.3333    | answer_relevancy  |
| 3    | multi_hop    | Nhân viên tạm ứng 8 triệu, chưa thanh toán sau 30 ngày (quá hạn 15 ngày). Ai phê duyệt khoản này và phí phạt là bao nhiêu? | 0.3514    | faithfulness      |
| 4    | multi_hop    | Nhân viên vừa kết hôn và cùng tuần đó có con kết hôn. Tổng số ngày nghỉ đặc biệt có lương là bao nhiêu?               | 0.4006    | faithfulness      |
| 5    | adversarial  | Theo chính sách nghỉ phép cũ (v2023), nhân viên được nghỉ bao nhiêu ngày? Còn chính sách nào đang có hiệu lực hiện tại? | 0.4167    | answer_relevancy  |
| 6    | factual      | Phụ cấp ăn trưa hàng tháng là bao nhiêu?                                                                                               | 0.5000    | faithfulness      |
| 7    | multi_hop    | Nhân viên tạm ứng 15 triệu, sau 20 ngày mới thanh toán. Bị phạt bao nhiêu?                                                          | 0.5000    | answer_relevancy  |
| 8    | multi_hop    | Nhân viên tạm ứng 4 triệu và một nhân viên khác tạm ứng 7 triệu: quy trình phê duyệt khác nhau thế nào?                     | 0.5000    | answer_relevancy  |
| 9    | adversarial  | Nhân viên thử việc có được nghỉ phép năm không?                                                                                    | 0.5208    | context_precision |
| 10   | factual      | Mentor và buddy của nhân viên mới có thể là cùng một người không? Quản lý trực tiếp có thể làm mentor không?              | 0.6250    | answer_relevancy  |

---

## 3. Failure Cluster Matrix

*(Mỗi ô = số câu có worst_metric = row, thuộc distribution = col)*

| worst_metric      | factual      | multi_hop    | adversarial  | Total        |
| :---------------- | :----------- | :----------- | :----------- | :----------- |
| faithfulness      | 5            | 3            | 2            | **10** |
| answer_relevancy  | 13           | 13           | 7            | **33** |
| context_precision | 2            | 2            | 1            | **5**  |
| context_recall    | 0            | 2            | 0            | **2**  |
| **Total**   | **20** | **20** | **10** | **50** |

---

## 4. Dominant Failure Analysis

Dựa trên dữ liệu phân tích lỗi chi tiết (không phải dữ liệu offline fixture đồng điểm 1.0):

**Dominant distribution (Phân vùng lỗi nhiều nhất):** factual (tie in offline fixture - *Tuy nhiên, xét trên tỷ lệ lỗi/tổng số câu trong phân vùng, factual và adversarial có tỷ lệ cao nhất, cùng 100% số câu có lỗi.*)
**Dominant metric (Metric yếu chủ đạo):** answer_relevancy (33/50 câu có điểm metric này thấp nhất).

**Lý do phân tích:**

Kết quả offline fixture ban đầu có điểm bằng nhau vì fixture sử dụng ground truth làm câu trả lời và ngữ cảnh, dẫn đến trần điểm giả tạo. Ma trận lỗi thực tế cho thấy `answer_relevancy` là điểm nghẽn lớn nhất trên mọi phân vùng. Khi có API/RAGAS thật, cần thay fixture bằng answers sinh từ pipeline để phân tích version conflict và retrieval failure có ý nghĩa.

---

## 5. Suggested Fixes

| Metric yếu       | Root cause (Nguyên nhân gốc rễ)                                                                   | Suggested fix (Giải pháp đề xuất)                                                                                                                  |
| :---------------- | :---------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| faithfulness      | LLM hallucinating (Mô hình bị ảo giác, đưa thông tin ngoài ngữ cảnh)                       | Tinh chỉnh system prompt để giới hạn LLM chỉ trả lời dựa trên ngữ cảnh được cung cấp. Giảm temperature.                                |
| context_recall    | Missing relevant chunks (Truy xuất thiếu các đoạn ngữ cảnh quan trọng)                        | Cải thiện kỹ thuật retrieval (ví dụ: Hybrid Search, thêm bước Query Expansion). Rà soát lại việc chia nhỏ tài liệu (chunking strategy). |
| context_precision | Too many irrelevant chunks (Truy xuất quá nhiều đoạn ngữ cảnh không liên quan)               | Tinh chỉnhembedding model hoặc áp dụng thêm bước Re-ranking (ví dụ: Cross-Encoder) sau khi retrieve.                                           |
| answer_relevancy  | Answer doesn't match question (Câu trả lời không khớp hoặc không đúng trọng tâm câu hỏi) | Cải thiện prompt template, yêu cầu mô hình định dạng lại câu trả lời để trực tiếp giải quyết câu hỏi của người dùng.           |

---

## 6. Nhận xét về Adversarial Distribution

Dựa trên dữ liệu phân tích chi tiết:

**1. So sánh avg_score:**
Phân vùng `adversarial` có điểm trung bình thấp nhất (`0.632`), thấp hơn đáng kể so với `factual` (`0.774`) và `multi_hop` (`0.683`). Điều này cho thấy các câu hỏi đối nghịch (adversarial) đặt ra thách thức lớn nhất cho pipeline hiện tại.

**2. Version conflicts (v2023 vs v2024):**
Có bằng chứng cho thấy pipeline bị nhầm lẫn bởi sự xung đột phiên bản. Cụ thể, câu hỏi Rank 5 (ID 49) trong Bottom 10: *"Theo chính sách nghỉ phép cũ (v2023)... Còn chính sách nào đang có hiệu lực hiện tại?"* có điểm `avg_score` rất thấp (`0.4167`) và `worst_metric` là `answer_relevancy`. Điều này cho thấy mô hình không xử lý tốt việc phân biệt thông tin lịch sử và thông tin hiện hành khi chúng cùng tồn tại trong ngữ cảnh.

**3. Các câu hỏi Adversarial trong Bottom 10:**
Có 3 câu hỏi thuộc phân vùng adversarial nằm trong Top 10 lỗi, bao gồm Rank 1, Rank 5 và Rank 9.

* **Rank 1 (ID 48):** *"Nhân viên thử việc có được hưởng bảo hiểm sức khỏe PVI không?"* - Điểm thấp nhất (`0.2292`, worst_metric: `answer_relevancy`).
* **Lý do:** Các câu hỏi này thường mang tính chất gài bẫy, yêu cầu khả năng suy luận logic sâu hoặc phân biệt các điều kiện đặc thù (nhân viên thử việc vs. chính thức) mà tài liệu nguồn có thể trình bày chưa đủ rõ ràng hoặc mô hình chưa tổng hợp tốt.
