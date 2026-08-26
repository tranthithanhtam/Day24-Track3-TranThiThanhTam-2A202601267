# Failure Cluster Analysis — Phase A

**Sinh viên:** Trần Thị Thanh Tâm
**Ngày:** 26/08/2026

---

## 1. Aggregate RAGAS Scores theo Distribution

Bảng dưới đây thể hiện điểm số trung bình của các metric RAGAS trên từng phân vùng câu hỏi.

| Metric | factual | multi_hop | adversarial |
|:---|:---|:---|:---|
| faithfulness | 0.8167 | 0.7400 | 0.7074 |
| answer_relevancy | 0.4051 | 0.4460 | 0.2875 |
| context_precision | 0.9000 | 0.6500 | 0.7000 |
| context_recall | 0.9750 | 0.8958 | 0.8333 |
| **avg_score** | **0.7742** | **0.6830** | **0.6320** |



## 2. Bottom 10 Questions

Danh sách 10 câu hỏi có điểm `avg_score` thấp nhất, được trích xuất từ phân tích lỗi chi tiết.

| Rank | Distribution | Question | avg_score | worst_metric |
|:---|:---|:---|:---|:---|
| 1 | adversarial | Nhân viên thử việc có được hưởng bảo hiểm sức khỏe PVI không? | 0.2292 | answer_relevancy |
| 2 | multi_hop | Kết quả đánh giá hiệu suất tháng 6 và tháng 12 được dùng để làm gì khác nhau? | 0.3333 | answer_relevancy |
| 3 | multi_hop | Nhân viên tạm ứng 8 triệu, chưa thanh toán sau 30 ngày (quá hạn 15 ngày). Ai phê duyệt khoản này và phí phạt là bao nhiêu? | 0.3514 | faithfulness |
| 4 | multi_hop | Nhân viên vừa kết hôn và cùng tuần đó có con kết hôn. Tổng số ngày nghỉ đặc biệt có lương là bao nhiêu? | 0.4006 | faithfulness |
| 5 | adversarial | Theo chính sách nghỉ phép cũ (v2023), nhân viên được nghỉ bao nhiêu ngày? Còn chính sách nào đang có hiệu lực hiện tại? | 0.4167 | answer_relevancy |
| 6 | factual | Phụ cấp ăn trưa hàng tháng là bao nhiêu? | 0.5000 | faithfulness |
| 7 | multi_hop | Nhân viên tạm ứng 15 triệu, sau 20 ngày mới thanh toán. Bị phạt bao nhiêu? | 0.5000 | answer_relevancy |
| 8 | multi_hop | Nhân viên tạm ứng 4 triệu và một nhân viên khác tạm ứng 7 triệu: quy trình phê duyệt khác nhau thế nào? | 0.5000 | answer_relevancy |
| 9 | adversarial | Nhân viên thử việc có được nghỉ phép năm không? | 0.5208 | context_precision |
| 10 | factual | Mentor và buddy của nhân viên mới có thể là cùng một người không? Quản lý trực tiếp có thể làm mentor không? | 0.6250 | answer_relevancy |



## 3. Failure Cluster Matrix

Ma trận phân loại lỗi dựa trên `worst_metric` (metric có điểm thấp nhất trong 4 metrics RAGAS) của từng câu hỏi.

*(Mỗi ô = số câu có worst_metric = row, thuộc distribution = col)*

| worst_metric | factual | multi_hop | adversarial | Total |
|:---|:---|:---|:---|:---|
| faithfulness | 5 | 3 | 2 | **10** |
| context_recall | 0 | 2 | 0 | **2** |
| context_precision | 2 | 2 | 1 | **5** |
| answer_relevancy | 13 | 13 | 7 | **33** |
| **Total** | **20** | **20** | **10** | **50** |



## 4. Dominant Failure Analysis

Dựa trên dữ liệu tính toán thực tế:

**Dominant distribution (Phân vùng lỗi nhiều nhất):** factual (Tổng số lỗi là 20, chiếm 100% số câu trong phân vùng này - *Xét trên tỷ lệ lỗi/tổng số câu, factual và adversarial có tỷ lệ cao nhất*).
**Dominant metric (Metric yếu chủ đạo):** answer_relevancy (33/50 câu có điểm metric này thấp nhất).

**Lý do phân tích:**

Mặc dù số lượng câu có `worst_metric` là `answer_relevancy` ở `factual` và `multi_hop` bằng nhau (13 câu), nhưng xét trên tổng số câu của mỗi loại, 100% các câu hỏi `factual` (20/20) và `adversarial` (10/10) đều gặp lỗi nghiêm trọng nhất ở một trong 4 metrics, trong đó `answer_relevancy` là nguyên nhân chính khiến điểm trung bình của `adversarial` thấp nhất và `factual` chỉ đứng trên `adversarial`.



## 5. Suggested Fixes

Dựa trên các metric yếu chủ đạo:

| Metric yếu | Root cause (Nguyên nhân gốc rễ) | Suggested fix (Giải pháp đề xuất) |
|:---|:---|:---|
| faithfulness | LLM hallucinating (Mô hình đưa thông tin không có trong ngữ cảnh) | Tinh chỉnh system prompt, yêu cầu giới hạn câu trả lời chặt chẽ trong phạm vi ngữ cảnh. Giảm temperature của LLM. |
| context_recall | Missing relevant chunks (Truy xuất thiếu các đoạn ngữ cảnh quan trọng) | Cải thiện chiến lược chunking, kết hợp keyword search và vector search (hybrid search), hoặc thêm bước query expansion. |
| context_precision | Too many irrelevant chunks (Truy xuất quá nhiều ngữ cảnh nhiễu) | Tinh chỉnh embedding model, làm sạch dữ liệu nguồn, hoặc thêm bước reranking (cross-encoder) sau khi retrieve. |
| answer_relevancy | Answer doesn't match question (Câu trả lời không đúng trọng tâm câu hỏi) | Tinh chỉnh prompt template để tập trung vào việc trả lời trực tiếp câu hỏi dựa trên ngữ cảnh. Thêm bước kiểm tra Answer Relevancy trước khi output. |



## 6. Nhận xét về Adversarial Distribution

Dựa trên dữ liệu tính toán thực tế:

**1. So sánh avg_score:**
Phân vùng `adversarial` có điểm trung bình thấp nhất (`0.632`), thấp hơn đáng kể so với `factual` (`0.774`) và `multi_hop` (`0.683`). Điều này cho thấy các câu hỏi đối nghịch (adversarial) đặt ra thách thức lớn nhất cho pipeline hiện tại.

**2. Version conflicts (v2023 vs v2024):**
Có bằng chứng cho thấy pipeline bị nhầm lẫn bởi sự xung đột phiên bản trong tài liệu. Cụ thể, câu hỏi Rank 5 (ID 49) trong Bottom 10: *"Theo chính sách nghỉ phép cũ (v2023)... Còn chính sách nào đang có hiệu lực hiện tại?"* có điểm `avg_score` thấp (`0.4167`) và `worst_metric` là `answer_relevancy`. Điều này chỉ ra rằng mô hình không xử lý tốt việc phân biệt thông tin lịch sử và thông tin hiện hành khi chúng cùng tồn tại trong ngữ cảnh.

**3. Các câu hỏi Adversarial trong Bottom 10:**
Có 3 câu hỏi thuộc phân vùng adversarial nằm trong Top 10 lỗi, bao gồm Rank 1, Rank 5 và Rank 9.
*   **Rank 1 (ID 48):** *"Nhân viên thử việc có được hưởng bảo hiểm sức khỏe PVI không?"* - Điểm thấp nhất (`0.2292`, worst_metric: `answer_relevancy`).
*   **Lý do:** Các câu hỏi này thường là dạng "gài", đòi hỏi khả năng suy luận logic sâu hoặc phân biệt các điều kiện ngoại lệ (ví dụ: quy định riêng cho nhân viên thử việc) mà tài liệu nguồn có thể trình bày chưa đủ rõ ràng hoặc mô hình chưa tổng hợp tốt.
