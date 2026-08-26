# CI/CD Blueprint: RAG Eval + Guardrail Stack

**Sinh viên:** Trần Thị Thanh Tâm
**Ngày:** 26/08/2026

---

## Guard Stack Architecture

```
User Input
    │
    ▼ (~?ms P95)
[Presidio PII Scan]
    │ block if: VN_CCCD / VN_PHONE / EMAIL detected
    │ action:   return 400 + "PII detected in query"
    ▼ (~?ms P95)
[NeMo Input Rail]
    │ block if: off-topic / jailbreak / prompt injection
    │ action:   return 503 + refuse message
    ▼
[RAG Pipeline (Day 18)]
    │ M1 Chunk → M2 Search → M3 Rerank → GPT-4o-mini
    ▼
[NeMo Output Rail]
    │ flag if:  PII in response / sensitive content
    │ action:   replace with safe response
    ▼
User Response
```

---

## Latency Budget

| Layer                 | P50 (ms) | P95 (ms)        | P99 (ms) | Budget           |
| --------------------- | -------- | --------------- | -------- | ---------------- |
| Presidio PII          | 0.03     | 20.38           | 20.38    | <10ms            |
| NeMo Input Rail       | 0.01     | 0.03            | 0.04     | <300ms           |
| RAG Pipeline          | N/A      | N/A             | N/A      | <2000ms          |
| NeMo Output Rail      | N/A      | N/A             | N/A      | <300ms           |
| **Total Guard** | 0.04     | **20.40** | 20.40    | **<500ms** |

**Budget OK?** [x] Yes / [ ] No
**Comment:** Đo offline sau khi cache Presidio; production cần đo lại NeMo qua mạng và đặt timeout.

---

## CI/CD Gates (phải pass trước khi merge to main)

```yaml
# .github/workflows/rag_eval.yml
- name: RAGAS Quality Gate
  run: python src/phase_a_ragas.py
  env:
    MIN_FAITHFULNESS: 0.75
    MIN_AVG_SCORE: 0.65

- name: Guardrail Gate
  run: pytest tests/test_phase_c.py -k "test_adversarial_suite_pass_rate"
  # phải ≥ 15/20 (75%)

- name: Latency Gate
  run: python -c "from src.phase_c_guard import measure_p95_latency; ..."
  # P95 total < 500ms
```

---

## Monitoring Dashboard (production)

| Metric                            | Alert Threshold | Action                     |
| --------------------------------- | --------------- | -------------------------- |
| RAGAS faithfulness (daily sample) | < 0.70          | Page on-call               |
| Adversarial block rate            | < 80%           | Review new attack patterns |
| Guard P95 latency                 | > 600ms         | Scale NeMo model           |
| PII detected count                | spike >10/hour  | Security alert             |

---

## Kết quả thực tế từ Lab

|                               | Kết quả                        |
| ----------------------------- | -------------------------------- |
| RAGAS avg_score (50q)         | 1.000 (offline fallback)         |
| Worst metric                  | faithfulness (tie trong fixture) |
| Dominant failure distribution | factual (tie trong fixture)      |
| Cohen's κ                    | 0.000 (placeholder labels)       |
| Adversarial pass rate         | 17 / 20                          |
| Guard P95 latency             | 20.40 ms (cached offline rail)   |

---

## Nhận xét & Cải tiến

> Presidio phát hiện đúng CCCD, CMND, số điện thoại Việt Nam và email, trong khi input rail chặn được 17/20 mẫu adversarial. Phase A đã có fallback deterministic để vẫn tạo được per-question report khi thiếu RAGAS/API. Điểm RAGAS 1.0 chỉ phản ánh offline fixture dùng ground truth làm context, không thay thế phép đo production. Khi deploy thật cần chạy lại với answers sinh từ pipeline, NeMo model thật, timeout, logging và theo dõi drift.
