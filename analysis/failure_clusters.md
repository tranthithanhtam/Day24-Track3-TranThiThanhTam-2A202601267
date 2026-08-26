# Failure Cluster Analysis — Phase A

**Sinh viên:** Trần Thị Thanh Tâm  
**Ngày:** 26/08/2026

---

## 1. Aggregate RAGAS Scores theo Distribution

| Metric | factual | multi_hop | adversarial |
|---|---|---|---|
| faithfulness | 1.0 | 1.0 | 1.0 |
| answer_relevancy | 1.0 | 1.0 | 1.0 |
| context_precision | 1.0 | 1.0 | 1.0 |
| context_recall | 1.0 | 1.0 | 1.0 |
| **avg_score** | 1.0 | 1.0 | 1.0 |

---

## 2. Bottom 10 Questions

| Rank | Distribution | Question | avg_score | worst_metric |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| ... | | | | |

---

## 3. Failure Cluster Matrix

*(Mỗi ô = số câu có worst_metric = row, thuộc distribution = col)*

| worst_metric | factual | multi_hop | adversarial | Total |
|---|---|---|---|---|
| faithfulness | | | | |
| answer_relevancy | | | | |
| context_precision | | | | |
| context_recall | | | | |

---

## 4. Dominant Failure Analysis

**Dominant distribution:** factual (tie in offline fixture)  
**Dominant metric:** faithfulness (tie in offline fixture)

**Lý do phân tích:**

> Kết quả offline có điểm bằng nhau vì fixture dùng ground truth làm answer và context, nên không thể kết luận factual thực sự yếu hơn. Matrix dùng faithfulness và factual làm tie-break. Khi có API/RAGAS thật, cần thay fixture bằng answers sinh từ pipeline để phân tích version conflict và retrieval failure có ý nghĩa.

---

## 5. Suggested Fixes

| Metric yếu | Root cause | Suggested fix |
|---|---|---|
| faithfulness | LLM hallucinating | |
| context_recall | Missing relevant chunks | |
| context_precision | Too many irrelevant chunks | |
| answer_relevancy | Answer doesn't match question | |

---

## 6. Nhận xét về Adversarial Distribution

> [So sánh avg_score của adversarial vs factual vs multi_hop.
>  Pipeline có bị "nhầm" bởi version conflicts (v2023 vs v2024) không?
>  Câu nào trong bottom 10 rơi vào adversarial? Tại sao?]
