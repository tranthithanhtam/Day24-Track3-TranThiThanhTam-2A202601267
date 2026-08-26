# LLM Judge Bias Report — Phase B

**Sinh viên:** Trần Thị Thanh Tâm  
**Ngày:** 26/08/2026
**Judge model:** gpt-4o-mini

---

## 1. Pairwise Judge Results

*(Chạy pairwise_judge() trên ít nhất 5 cặp answers)*

| # | Question (tóm tắt) | Winner | Reasoning tóm tắt |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| ... | | | |

---

## 2. Swap-and-Average Results

*(Chạy swap_and_average() trên cùng các cặp)*

| # | Pass 1 Winner | Pass 2 Winner | Final | Position Consistent? |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

**Position bias rate:** 0% (= 0/1 case không nhất quán)

---

## 3. Cohen's κ Analysis

**Human labels:** `human_labels_10q.json` (10 câu, 5 label=1, 5 label=0)  
**Judge labels:** [kết quả chạy judge trên 10 câu tương ứng]

| Question ID | Human Label | Judge Label | Agree? |
|---|---|---|---|
| 1 | | | |
| 5 | | | |
| 12 | | | |
| 21 | | | |
| 23 | | | |
| 29 | | | |
| 33 | | | |
| 41 | | | |
| 46 | | | |
| 50 | | | |

**Cohen's κ:** 0.000 (placeholder judge labels trong scaffold)  
**Interpretation:** poor; cần chạy judge thật trên 10 câu human trước khi dùng làm quality gate.

---

## 4. Verbosity Bias

Trong các case có winner rõ ràng (không phải tie):
- A thắng + A dài hơn B: 1 / 1 cases
- B thắng + B dài hơn A: 0 / 1 cases  
- **Verbosity bias rate:** 100%

**Kết luận:** [LLM có xu hướng chọn answer dài hơn không? Tại sao điều này là vấn đề?]

---

## 5. Nhận xét chung

> κ hiện là 0.0 vì main demo dùng placeholder labels, chưa phải phép đo judge trên 10 câu human. Position bias demo là 0%, dưới ngưỡng 30%; swap-and-average vẫn cần giữ để phát hiện bất nhất. Production nên chạy nhiều mẫu, lưu reasoning, theo dõi κ theo thời gian và không dùng judge làm gate duy nhất.
