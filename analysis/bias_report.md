# LLM Judge Bias Report — Phase B

**Judge model:** openai/gpt-oss-20b

## 1. Pairwise Judge Results

| # | Question | Winner | Reasoning |
|---|---|---|---|
| 1 | Nhân viên được nghỉ bao nhiêu ngày khi kết hôn? | tie | Both answers are identical and provide the same correct information. |
| 2 | Bảo hiểm sức khỏe PVI có hạn mức bao nhiêu cho nhân viên? | tie | Both answers are identical, so there is no winner. |
| 3 | Phụ cấp ăn trưa hàng tháng là bao nhiêu? | tie | Both Answer A and Answer B provide the same information: the monthly lunch allowance is 1,000,000 VND and is paid with the salary. Since they are identical and both contain the same correct statement, neither is superior, resulting in a tie. |
| 4 | Mentor và buddy của nhân viên mới có thể là cùng một người không? Quản lý trực tiếp có thể làm mentor không? | tie | Compared question-term coverage and factual specificity. |
| 5 | Muốn mua thiết bị trị giá 55 triệu cần ai phê duyệt? | tie | Both answers give the same correct information that a purchase over 50 million VND requires CEO approval. |

## 2. Swap-and-Average Results

| # | Pass 1 | Pass 2 | Final | Position consistent? |
|---|---|---|---|---|
| 1 | tie | tie | tie | True |
| 2 | tie | tie | tie | True |
| 3 | tie | tie | tie | True |
| 4 | tie | tie | tie | True |
| 5 | tie | tie | tie | True |
| 6 | tie | tie | tie | True |
| 7 | tie | tie | tie | True |
| 8 | tie | tie | tie | True |
| 9 | tie | tie | tie | True |
| 10 | tie | tie | tie | True |

**Position bias rate:** 0.0% (= 0/50 inconsistent cases)

## 3. Cohen's κ Analysis

| Question ID | Human label | Judge label | Agree? |
|---|---:|---:|---|
| 1 | 1 | 0 | False |
| 5 | 0 | 0 | True |
| 12 | 1 | 0 | False |
| 21 | 1 | 0 | False |
| 23 | 1 | 0 | False |
| 29 | 0 | 0 | True |
| 33 | 1 | 0 | False |
| 41 | 0 | 0 | True |
| 46 | 1 | 0 | False |
| 50 | 0 | 0 | True |

**Cohen's κ:** 0.000
**Interpretation:** slight agreement.

## 4. Verbosity Bias

- A thắng và A dài hơn B: 0
- B thắng và B dài hơn A: 0
- **Verbosity bias rate:** 0.0%

## 5. Nhận xét chung

> Đã chạy judge trên 50 câu trả lời và đối chiếu 10 câu có nhãn người. Position bias thấp — judge ổn định. κ phản ánh mức đồng thuận giữa judge và human trên tập kiểm chứng.
