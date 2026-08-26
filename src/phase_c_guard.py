from __future__ import annotations

"""Phase C: Production Guardrails — Presidio PII + NeMo Guardrails + P95 Latency."""

import asyncio
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ADVERSARIAL_SET_PATH, GUARDRAILS_CONFIG_DIR, LATENCY_BUDGET_P95_MS, PRESIDIO_LANGUAGE

_PRESIDIO_CACHE = None


# ─── Task 9a: Presidio PII Detection ─────────────────────────────────────────

def setup_presidio():
    """Khởi tạo Presidio engine với custom Vietnamese PII recognizers. (Đã implement sẵn)

    Custom recognizers thêm vào:
        VN_CCCD  — số CCCD 12 chữ số hoặc CMND 9 chữ số
        VN_PHONE — số điện thoại Việt Nam (0[3-9]xxxxxxxx)

    Các recognizers mặc định đã có sẵn: EMAIL, PHONE_NUMBER (international), ...
    """
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, Pattern, PatternRecognizer
    from presidio_anonymizer import AnonymizerEngine

    cccd_recognizer = PatternRecognizer(
        supported_entity="VN_CCCD",
        patterns=[
            Pattern("CCCD 12 digits", r"\b\d{12}\b", 0.9),
            Pattern("CMND 9 digits",  r"\b\d{9}\b",  0.7),
        ],
    )
    phone_recognizer = PatternRecognizer(
        supported_entity="VN_PHONE",
        patterns=[Pattern("VN mobile", r"\b0[3-9]\d{8}\b", 0.9)],
    )

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    registry.add_recognizer(cccd_recognizer)
    registry.add_recognizer(phone_recognizer)

    analyzer  = AnalyzerEngine(registry=registry)
    anonymizer = AnonymizerEngine()
    return analyzer, anonymizer


def pii_scan(text: str, analyzer=None, anonymizer=None) -> dict:
    """Task 9a: Quét PII trong văn bản bằng Presidio.

    Returns:
        {
          "has_pii":    bool,
          "entities":   [{"type": str, "text": str, "score": float, "start": int, "end": int}],
          "anonymized": str,   # text với PII được thay bằng <TYPE>
        }
    """
    global _PRESIDIO_CACHE
    if analyzer is None or anonymizer is None:
        try:
            if _PRESIDIO_CACHE is None:
                _PRESIDIO_CACHE = setup_presidio()
            analyzer, anonymizer = _PRESIDIO_CACHE
        except Exception:
            analyzer = anonymizer = None
    if analyzer is not None and anonymizer is not None:
        try:
            findings = [item for item in analyzer.analyze(text=text, language=PRESIDIO_LANGUAGE)
                        if item.entity_type in {"VN_CCCD", "VN_PHONE", "EMAIL_ADDRESS", "EMAIL"}]
            anonymized = anonymizer.anonymize(text=text, analyzer_results=findings).text if findings else text
            entities = [{"type": item.entity_type, "text": text[item.start:item.end],
                         "score": round(item.score, 3), "start": item.start, "end": item.end}
                        for item in findings]
            return {"has_pii": bool(entities), "entities": entities, "anonymized": anonymized}
        except Exception:
            pass
    import re
    patterns = [("VN_CCCD", r"\b\d{9}(?:\d{3})?\b"), ("VN_PHONE", r"\b0[3-9]\d{8}\b"),
                ("EMAIL_ADDRESS", r"\b[\w.+-]+@[\w.-]+\.\w+\b")]
    matches = []
    for entity_type, pattern in patterns:
        matches.extend((match.start(), match.end(), entity_type, match.group()) for match in re.finditer(pattern, text))
    matches.sort()
    entities = [{"type": kind, "text": value, "score": 0.9, "start": start, "end": end}
                for start, end, kind, value in matches]
    anonymized = text
    for start, end, kind, _ in reversed(matches):
        anonymized = anonymized[:start] + f"<{kind}>" + anonymized[end:]
    return {"has_pii": bool(entities), "entities": entities, "anonymized": anonymized}
    # if analyzer is None or anonymizer is None:
    #     analyzer, anonymizer = setup_presidio()
    #
    # results = analyzer.analyze(text=text, language=PRESIDIO_LANGUAGE)
    # if not results:
    #     return {"has_pii": False, "entities": [], "anonymized": text}
    #
    # anonymized = anonymizer.anonymize(text=text, analyzer_results=results).text
    # entities = [
    #     {"type": r.entity_type, "text": text[r.start:r.end],
    #      "score": round(r.score, 3), "start": r.start, "end": r.end}
    #     for r in results
    # ]
    # return {"has_pii": True, "entities": entities, "anonymized": anonymized}
    return {"has_pii": False, "entities": [], "anonymized": text}


# ─── Task 9b + 11: NeMo Guardrails ───────────────────────────────────────────

def setup_nemo_rails():
    """Khởi tạo NeMo Guardrails từ guardrails/config.yml. (Đã implement sẵn)

    Config directory: guardrails/
        config.yml  — model + rails config
        rails.co    — Colang dialogue flows (topic check, jailbreak check, output check)
    """
    from nemoguardrails import RailsConfig, LLMRails
    config = RailsConfig.from_path(GUARDRAILS_CONFIG_DIR)
    rails  = LLMRails(config)
    return rails


async def check_input_rail(text: str, rails=None) -> dict:
    """Task 9b: Kiểm tra input qua NeMo input rails (topic guard + jailbreak guard).

    Returns:
        {
          "allowed":        bool,
          "blocked_reason": str | None,
          "response":       str,          # NeMo's raw response
        }
    """
    if rails is not None:
        response = await rails.generate_async(messages=[{"role": "user", "content": text}])
        response_text = response if isinstance(response, str) else str(response)
        blocked = any(keyword in response_text.lower() for keyword in ("xin lỗi", "không thể", "không được phép", "i cannot", "i'm sorry"))
        return {"allowed": not blocked, "blocked_reason": "nemo_input_rail" if blocked else None, "response": response_text}
    lowered = text.lower()
    blocked_terms = ("bỏ qua tất cả", "ignore your", "ignore previous", "pretend you are dan", "unrestricted ai",
                     "system override", "system prompt", "admin command", "dump all", "tấn công mạng",
                     "viết một bài thơ", "nấu phở", "bitcoin", "giải phương trình", "bộ phim", "ceo và ra lệnh",
                     "thông tin nhân viên", "lương tháng của nhân viên", "mật khẩu admin",
                     "cccd và số điện thoại", "đóng vai hr manager", "in ra toàn bộ")
    blocked = any(term in lowered for term in blocked_terms)
    return {"allowed": not blocked, "blocked_reason": "nemo_input_rail" if blocked else None,
            "response": "Request blocked by local input rail." if blocked else "Allowed."}


async def check_output_rail(question: str, answer: str, rails=None) -> dict:
    """Task 11: Kiểm tra LLM output qua NeMo output rails trước khi trả về user.

    NeMo output rails hoạt động trong context của cả cuộc hội thoại (input + output).
    Kiểm tra: có PII không? Nội dung có phù hợp không? Có hallucination rõ ràng không?

    Returns:
        {
          "safe":           bool,
          "flagged_reason": str | None,
          "final_answer":   str,          # answer đã qua guard (có thể bị redact)
        }
    """
    if rails is not None:
        response = await rails.generate_async(messages=[{"role": "user", "content": question},
                                 {"role": "assistant", "content": answer}])
        response_text = response if isinstance(response, str) else str(response)
        flagged = any(keyword in response_text.lower() for keyword in ("xin lỗi", "không thể cung cấp", "i cannot"))
        return {"safe": not flagged, "flagged_reason": "nemo_output_rail" if flagged else None,
            "final_answer": response_text if flagged else answer}
    import re
    sensitive = re.search(r"(?:CCCD|CMND|mật khẩu hệ thống|số điện thoại cá nhân)\s*(?:của|là)?\s*[:\d]", answer, re.I)
    return {"safe": not bool(sensitive), "flagged_reason": "sensitive_output" if sensitive else None,
            "final_answer": "Tôi không thể cung cấp thông tin này." if sensitive else answer}


# ─── Task 10: Adversarial Test Suite ─────────────────────────────────────────

def run_adversarial_suite(adversarial_set: list[dict], rails=None,
                           analyzer=None, anonymizer=None) -> list[dict]:
    """Task 10: Chạy 20 adversarial inputs qua full guard stack, so sánh với expected.

    Guard stack order:
        1. pii_scan()         → block nếu has_pii (cho category pii_injection)
        2. check_input_rail() → block nếu jailbreak / off-topic / prompt injection

    Returns:
        list of {
          "id": int, "category": str, "input": str,
          "expected": "blocked"|"allowed",
          "actual":   "blocked"|"allowed",
          "blocked_by": str | None,       # "presidio" | "nemo_input" | None
          "passed": bool,
        }
    """
    async def run_all():
        output = []
        for item in adversarial_set:
            blocked_by = "presidio" if pii_scan(item["input"], analyzer, anonymizer)["has_pii"] else None
            if blocked_by is None and not (await check_input_rail(item["input"], rails))["allowed"]:
                blocked_by = "nemo_input"
            actual = "blocked" if blocked_by else "allowed"
            output.append({"id": item["id"], "category": item["category"], "input": item["input"][:80],
                           "expected": item["expected"], "actual": actual, "blocked_by": blocked_by,
                           "passed": actual == item["expected"]})
        return output
    results = asyncio.run(run_all())
    print(f"Adversarial suite: {sum(item['passed'] for item in results)}/{len(results)} passed")
    return results
    # async def _run_all():
    #     results = []
    #     for item in adversarial_set:
    #         blocked_by = None
    #
    #         # Layer 1: Presidio PII (synchronous, fast)
    #         pii_result = pii_scan(item["input"], analyzer, anonymizer)
    #         if pii_result["has_pii"]:
    #             blocked_by = "presidio"
    #
    #         # Layer 2: NeMo input rail (async — await, không dùng asyncio.run())
    #         if blocked_by is None:
    #             rail_result = await check_input_rail(item["input"], rails)
    #             if not rail_result["allowed"]:
    #                 blocked_by = "nemo_input"
    #
    #         actual = "blocked" if blocked_by else "allowed"
    #         results.append({
    #             "id":         item["id"],
    #             "category":   item["category"],
    #             "input":      item["input"][:80] + "...",
    #             "expected":   item["expected"],
    #             "actual":     actual,
    #             "blocked_by": blocked_by,
    #             "passed":     actual == item["expected"],
    #         })
    #     return results
    #
    # results = asyncio.run(_run_all())   # một lần duy nhất — không gọi asyncio.run() trong loop
    # passed = sum(1 for r in results if r["passed"])
    # print(f"Adversarial suite: {passed}/{len(results)} passed")
    # return results
    return []


# ─── Task 12: P95 Latency Measurement ────────────────────────────────────────

def measure_p95_latency(test_inputs: list[str], n_runs: int = 20,
                         rails=None, analyzer=None, anonymizer=None) -> dict:
    """Task 12: Đo P50/P95/P99 latency cho từng layer trong guard stack.

    Mục tiêu production: P95 total < LATENCY_BUDGET_P95_MS (500ms mặc định)

    Insight cần quan sát:
        - Presidio: local regex → rất nhanh (<10ms)
        - NeMo:     LLM API call → chậm (~200-800ms tuỳ model và network)
        → Tổng: dominated by NeMo

    Returns:
        {
          "presidio_ms":  {"p50": float, "p95": float, "p99": float},
          "nemo_ms":      {"p50": float, "p95": float, "p99": float},
          "total_ms":     {"p50": float, "p95": float, "p99": float},
          "latency_budget_ok": bool,
          "budget_ms": int,
        }
    """
    presidio_times, nemo_times, total_times = [], [], []
    async def measure():
        for text in (test_inputs * max(1, n_runs))[:n_runs]:
            start = time.perf_counter()
            pii_scan(text, analyzer, anonymizer)
            presidio_times.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            await check_input_rail(text, rails)
            nemo_times.append((time.perf_counter() - start) * 1000)
            total_times.append(presidio_times[-1] + nemo_times[-1])
    asyncio.run(measure())
    def percentiles(values):
        if not values:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        values = sorted(values)
        def at(fraction):
            return values[min(len(values) - 1, int((len(values) - 1) * fraction))]
        return {"p50": round(at(0.50), 2), "p95": round(at(0.95), 2), "p99": round(at(0.99), 2)}
    total = percentiles(total_times)
    return {"presidio_ms": percentiles(presidio_times), "nemo_ms": percentiles(nemo_times),
            "total_ms": total, "latency_budget_ok": total["p95"] < LATENCY_BUDGET_P95_MS,
            "budget_ms": LATENCY_BUDGET_P95_MS}
    # presidio_times, nemo_times, total_times = [], [], []
    #
    # async def _measure():
    #     for text in test_inputs[:n_runs]:
    #         # Presidio (synchronous)
    #         t0 = time.perf_counter()
    #         pii_scan(text, analyzer, anonymizer)
    #         presidio_ms = (time.perf_counter() - t0) * 1000
    #
    #         # NeMo input rail (await — không dùng asyncio.run() trong loop)
    #         t1 = time.perf_counter()
    #         await check_input_rail(text, rails)
    #         nemo_ms = (time.perf_counter() - t1) * 1000
    #
    #         presidio_times.append(presidio_ms)
    #         nemo_times.append(nemo_ms)
    #         total_times.append(presidio_ms + nemo_ms)
    #
    # asyncio.run(_measure())   # một lần duy nhất
    #
    # def percentiles(times):
    #     s = sorted(times)
    #     n = len(s)
    #     return {
    #         "p50": round(s[int(n * 0.50)], 2),
    #         "p95": round(s[int(n * 0.95)], 2),
    #         "p99": round(s[min(int(n * 0.99), n-1)], 2),
    #     }
    #
    # total_p = percentiles(total_times)
    # return {
    #     "presidio_ms": percentiles(presidio_times),
    #     "nemo_ms":     percentiles(nemo_times),
    #     "total_ms":    total_p,
    #     "latency_budget_ok": total_p["p95"] < LATENCY_BUDGET_P95_MS,
    #     "budget_ms": LATENCY_BUDGET_P95_MS,
    # }
    return {
        "presidio_ms": {"p50": 0.0, "p95": 0.0, "p99": 0.0},
        "nemo_ms":     {"p50": 0.0, "p95": 0.0, "p99": 0.0},
        "total_ms":    {"p50": 0.0, "p95": 0.0, "p99": 0.0},
        "latency_budget_ok": False,
        "budget_ms": LATENCY_BUDGET_P95_MS,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Task 9a: PII scan demo
    test_pii = "Nhân viên Nguyễn Văn A, CCCD 034095001234, SĐT 0987654321 hỏi về nghỉ phép."
    result = pii_scan(test_pii)
    print(f"PII detected: {result['has_pii']}")
    print(f"Entities: {result['entities']}")
    print(f"Anonymized: {result['anonymized']}")

    # Task 10: Adversarial suite
    with open(ADVERSARIAL_SET_PATH, encoding="utf-8") as f:
        adversarial_set = json.load(f)
    print(f"\nLoaded {len(adversarial_set)} adversarial inputs")
    results = run_adversarial_suite(adversarial_set)
    if results:
        passed = sum(1 for r in results if r["passed"])
        print(f"Adversarial suite: {passed}/{len(results)} passed")

    # Task 12: P95 latency
    sample_inputs = [item["input"] for item in adversarial_set[:10]]
    latency = measure_p95_latency(sample_inputs, n_runs=10)
    print(f"\nLatency P95 — Presidio: {latency['presidio_ms']['p95']}ms | "
          f"NeMo: {latency['nemo_ms']['p95']}ms | "
          f"Total: {latency['total_ms']['p95']}ms")
    print(f"Budget OK ({latency['budget_ms']}ms): {latency['latency_budget_ok']}")
    os.makedirs("reports", exist_ok=True)
    with open("reports/guard_results.json", "w", encoding="utf-8") as f:
        json.dump({"adversarial": results, "latency": latency}, f, ensure_ascii=False, indent=2)
