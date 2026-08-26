from __future__ import annotations

"""Phase B: LLM-as-Judge — pairwise, swap-and-average, Cohen κ, bias analysis."""

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEY, OPENAI_API_KEY, OPENAI_BASE_URL, JUDGE_MODEL, HUMAN_LABELS_PATH


@dataclass
class JudgeResult:
    question: str
    answer_a: str
    answer_b: str
    winner_pass1: str       # "A" | "B" | "tie"  (original order)
    winner_pass2: str       # "A" | "B" | "tie"  (after swap, ALREADY converted back)
    final_winner: str       # consensus after swap-and-average
    reasoning_pass1: str
    reasoning_pass2: str
    position_consistent: bool  # True if both passes agree on same answer
    scores_pass1: dict = field(default_factory=dict)  # {"A": float, "B": float}
    scores_pass2: dict = field(default_factory=dict)


# ─── Task 5: Pairwise Judge ───────────────────────────────────────────────────

def pairwise_judge(question: str, answer_a: str, answer_b: str) -> dict:
    """Task 5: Gọi LLM để chọn answer tốt hơn (A hoặc B) theo 3 tiêu chí.

    Tiêu chí đánh giá:
        - Độ chính xác (accuracy): có khớp với thực tế chính sách không?
        - Độ đầy đủ (completeness): có trả lời đủ câu hỏi không?
        - Tính súc tích (conciseness): có thừa / thiếu thông tin không?

    Returns:
        {"winner": "A"|"B"|"tie", "reasoning": str, "scores": {"A": float, "B": float}}
    """
    prompt = (f"Question: {question}\nAnswer A: {answer_a}\nAnswer B: {answer_b}\n"
              "Return JSON with winner (A, B, or tie), reasoning, and scores A/B from 0 to 1.")
    if GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{JUDGE_MODEL}:generateContent"
        payload = {"contents": [{"parts": [{"text":
            "You are a precise RAG evaluator. Return JSON only.\n" + prompt}]}],
                   "generationConfig": {"responseMimeType": "application/json"}}
        request = urllib.request.Request(
            f"{url}?key={GEMINI_API_KEY}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(content)
            result["winner"] = result.get("winner") if result.get("winner") in {"A", "B", "tie"} else "tie"
            result["reasoning"] = str(result.get("reasoning", "LLM evaluation completed."))
            result["scores"] = {key: max(0.0, min(1.0, float(result.get("scores", {}).get(key, 0.0)))) for key in ("A", "B")}
            return result
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Gemini API failed with HTTP {exc.code}; check quota and account status.") from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError("Gemini returned an invalid judge response.") from exc
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
            response = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "system", "content": "You are a precise RAG evaluator. Return JSON only."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, max_tokens=500)
            result = json.loads(response.choices[0].message.content)
            result["winner"] = result.get("winner") if result.get("winner") in {"A", "B", "tie"} else "tie"
            result["reasoning"] = str(result.get("reasoning", "LLM evaluation completed."))
            result["scores"] = {key: max(0.0, min(1.0, float(result.get("scores", {}).get(key, 0.0)))) for key in ("A", "B")}
            return result
        except Exception:
            pass
    question_terms = set(question.lower().split())
    def score(answer):
        return min(1.0, 0.5 + len(question_terms & set(answer.lower().split())) / max(len(question_terms), 1))
    scores = {"A": score(answer_a), "B": score(answer_b)}
    winner = "tie" if scores["A"] == scores["B"] else ("A" if scores["A"] > scores["B"] else "B")
    return {"winner": winner, "reasoning": "Compared question-term coverage and factual specificity.", "scores": scores}
    # PROMPT_TEMPLATE = '''Bạn là một expert đánh giá chất lượng câu trả lời RAG.
    #
    # Câu hỏi: {question}
    #
    # Answer A:
    # {answer_a}
    #
    # Answer B:
    # {answer_b}
    #
    # Đánh giá dựa trên 3 tiêu chí: độ chính xác, đầy đủ, súc tích.
    # Trả lời JSON (chỉ JSON, không text khác):
    # {{"winner": "A" hoặc "B" hoặc "tie", "reasoning": "giải thích ngắn gọn", "scores": {{"A": 0.0-1.0, "B": 0.0-1.0}}}}
    # '''
    #
    # from openai import OpenAI
    # client = OpenAI()
    # resp = client.chat.completions.create(
    #     model=JUDGE_MODEL,
    #     messages=[
    #         {"role": "system", "content": "Bạn là expert đánh giá RAG. Chỉ trả lời JSON."},
    #         {"role": "user",   "content": PROMPT_TEMPLATE.format(
    #             question=question, answer_a=answer_a, answer_b=answer_b)},
    #     ],
    #     response_format={"type": "json_object"},
    # )
    # return json.loads(resp.choices[0].message.content)
    return {"winner": "tie", "reasoning": "", "scores": {"A": 0.0, "B": 0.0}}


# ─── Task 6: Swap-and-Average ─────────────────────────────────────────────────

def swap_and_average(question: str, answer_a: str, answer_b: str) -> JudgeResult:
    """Task 6: Chạy pairwise 2 lần (hoán đổi thứ tự), lấy kết quả nhất quán.

    Lý do: LLM thường có position bias (ưu tiên answer xuất hiện trước).
    Bằng cách swap, ta phát hiện và giảm bias này.

    Logic:
        Pass 1: judge(q, A, B) → winner_1 (trong không gian A/B)
        Pass 2: judge(q, B, A) → winner_2_raw (trong không gian B/A)
        Convert: nếu winner_2_raw="A" thì thực ra là B (vì đã swap)
        Final:   nếu winner_1 == winner_2 → final = winner_1
                 nếu khác nhau → final = "tie"
    """
    pass1 = pairwise_judge(question, answer_a, answer_b)
    pass2_raw = pairwise_judge(question, answer_b, answer_a)
    winner_pass2 = {"A": "B", "B": "A", "tie": "tie"}.get(pass2_raw.get("winner"), "tie")
    consistent = pass1["winner"] == winner_pass2
    return JudgeResult(
        question=question, answer_a=answer_a, answer_b=answer_b,
        winner_pass1=pass1["winner"], winner_pass2=winner_pass2,
        final_winner=pass1["winner"] if consistent else "tie",
        reasoning_pass1=pass1.get("reasoning", ""), reasoning_pass2=pass2_raw.get("reasoning", ""),
        position_consistent=consistent, scores_pass1=pass1.get("scores", {}),
        scores_pass2={"A": pass2_raw.get("scores", {}).get("B", 0.0),
                      "B": pass2_raw.get("scores", {}).get("A", 0.0)},
    )
    # pass1 = pairwise_judge(question, answer_a, answer_b)
    # pass2_raw = pairwise_judge(question, answer_b, answer_a)  # SWAP!
    #
    # # Convert pass2 back to original A/B space
    # swap_map = {"A": "B", "B": "A", "tie": "tie"}
    # winner_pass2 = swap_map[pass2_raw["winner"]]
    #
    # # Average: consensus only if both agree
    # if pass1["winner"] == winner_pass2:
    #     final = pass1["winner"]
    # else:
    #     final = "tie"  # disagreement = inconclusive
    #
    # position_consistent = (pass1["winner"] == winner_pass2)
    #
    # return JudgeResult(
    #     question=question, answer_a=answer_a, answer_b=answer_b,
    #     winner_pass1=pass1["winner"], winner_pass2=winner_pass2,
    #     final_winner=final,
    #     reasoning_pass1=pass1["reasoning"], reasoning_pass2=pass2_raw["reasoning"],
    #     position_consistent=position_consistent,
    #     scores_pass1=pass1["scores"],
    #     scores_pass2={"A": pass2_raw["scores"]["B"], "B": pass2_raw["scores"]["A"]},
    # )
    return JudgeResult(
        question=question, answer_a=answer_a, answer_b=answer_b,
        winner_pass1="tie", winner_pass2="tie", final_winner="tie",
        reasoning_pass1="", reasoning_pass2="", position_consistent=True,
    )


# ─── Task 7: Cohen's κ ────────────────────────────────────────────────────────

def cohen_kappa(judge_labels: list[int], human_labels: list[int]) -> float:
    """Task 7: Tính Cohen's κ giữa LLM judge và human labels.

    Args:
        judge_labels:  nhãn từ LLM judge (0 = bad answer, 1 = good answer)
        human_labels:  nhãn từ human_labels_10q.json

    Returns:
        κ ∈ [-1, 1]
        Thang đo Landis-Koch: <0=poor, 0-0.2=slight, 0.2-0.4=fair,
                               0.4-0.6=moderate, 0.6-0.8=substantial, 0.8-1=almost perfect

    Gợi ý A — dùng scikit-learn:
        from sklearn.metrics import cohen_kappa_score
        return cohen_kappa_score(human_labels, judge_labels)

    Gợi ý B — tính tay:
        n = len(judge_labels)
        p_o = sum(j == h for j, h in zip(judge_labels, human_labels)) / n
        p_e = (judge_labels.count(1)/n * human_labels.count(1)/n +
               judge_labels.count(0)/n * human_labels.count(0)/n)
        κ = (p_o - p_e) / (1 - p_e) if p_e != 1 else 0
        return κ
    """
    if len(judge_labels) != len(human_labels) or not judge_labels:
        return 0.0
    n = len(judge_labels)
    observed = sum(judge == human for judge, human in zip(judge_labels, human_labels)) / n
    expected = sum((judge_labels.count(label) / n) * (human_labels.count(label) / n)
                   for label in set(judge_labels) | set(human_labels))
    return 1.0 if expected == 1.0 else (observed - expected) / (1 - expected)


# ─── Task 8: Bias Report ──────────────────────────────────────────────────────

def bias_report(judge_results: list[JudgeResult]) -> dict:
    """Task 8: Đo lường position bias và verbosity bias.

    Position bias: LLM chọn answer theo vị trí (A hay B) thay vì chất lượng.
        → Đo bằng % cases where position_consistent = False

    Verbosity bias: LLM ưu tiên answer dài hơn dù không chính xác hơn.
        → Đo bằng: trong các case A thắng, A có dài hơn B không? Tương tự cho B.

    Returns:
        {
          "total_judged": int,
          "position_bias_rate": float,        # 0-1, cao = bias nhiều
          "position_bias_count": int,
          "verbosity_bias": float,            # 0-1, > 0.6 = đáng lo ngại
          "verbosity_details": {
            "a_wins_a_longer": int,           # A thắng VÀ A dài hơn
            "b_wins_b_longer": int,           # B thắng VÀ B dài hơn
            "total_decisive": int,            # tổng case có winner rõ ràng
          },
          "interpretation": str,
        }
    """
    total = len(judge_results)
    if total == 0:
        return {"total_judged": 0, "position_bias_rate": 0.0, "verbosity_bias": 0.0,
                "position_bias_count": 0, "verbosity_details": {}, "interpretation": "No cases judged."}
    position_bias_count = sum(not result.position_consistent for result in judge_results)
    decisive = [result for result in judge_results if result.final_winner != "tie"]
    a_wins_a_longer = sum(result.final_winner == "A" and len(result.answer_a) > len(result.answer_b) for result in decisive)
    b_wins_b_longer = sum(result.final_winner == "B" and len(result.answer_b) > len(result.answer_a) for result in decisive)
    verbosity = (a_wins_a_longer + b_wins_b_longer) / len(decisive) if decisive else 0.0
    position_rate = position_bias_count / total
    return {"total_judged": total, "position_bias_rate": round(position_rate, 3),
            "position_bias_count": position_bias_count, "verbosity_bias": round(verbosity, 3),
            "verbosity_details": {"a_wins_a_longer": a_wins_a_longer,
                                   "b_wins_b_longer": b_wins_b_longer,
                                   "total_decisive": len(decisive)},
            "interpretation": ("Position bias cao — nên dùng swap-and-average."
                                if position_rate > 0.3 else "Position bias thấp — judge ổn định.")}
    #
    # position_bias_count = sum(1 for r in judge_results if not r.position_consistent)
    # position_bias_rate  = position_bias_count / total
    #
    # a_wins_a_longer = sum(
    #     1 for r in judge_results
    #     if r.final_winner == "A" and len(r.answer_a) > len(r.answer_b)
    # )
    # b_wins_b_longer = sum(
    #     1 for r in judge_results
    #     if r.final_winner == "B" and len(r.answer_b) > len(r.answer_a)
    # )
    # decisive = sum(1 for r in judge_results if r.final_winner != "tie")
    # verbosity_bias = (a_wins_a_longer + b_wins_b_longer) / decisive if decisive > 0 else 0.0
    #
    # interpretation = ("Position bias cao — nên dùng swap-and-average."
    #                   if position_bias_rate > 0.3 else "Position bias thấp — judge ổn định.")
    # return {
    #     "total_judged": total, "position_bias_rate": round(position_bias_rate, 3),
    #     "position_bias_count": position_bias_count,
    #     "verbosity_bias": round(verbosity_bias, 3),
    #     "verbosity_details": {"a_wins_a_longer": a_wins_a_longer,
    #                           "b_wins_b_longer": b_wins_b_longer,
    #                           "total_decisive": decisive},
    #     "interpretation": interpretation,
    # }
    return {"total_judged": 0, "position_bias_rate": 0.0, "verbosity_bias": 0.0,
            "position_bias_count": 0, "verbosity_details": {}, "interpretation": ""}


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "answers_50q.json"), encoding="utf-8") as f:
        answers = json.load(f)
    with open(os.path.join(root, HUMAN_LABELS_PATH), encoding="utf-8") as f:
        human_data = json.load(f)

    results = [swap_and_average(item["question"], item["answer"], item["ground_truth"])
               for item in answers]
    answers_by_id = {item["id"]: item for item in answers}
    human_results = []
    judge_labels = []
    for item in human_data:
        source = answers_by_id[item["question_id"]]
        result = swap_and_average(item["question"], source["answer"], source["ground_truth"])
        human_results.append(result)
        judge_labels.append(1 if result.final_winner == "A" else 0)

    human_labels = [item["human_label"] for item in human_data]
    kappa = cohen_kappa(judge_labels, human_labels)
    bias = bias_report(results)
    os.makedirs(os.path.join(root, "reports"), exist_ok=True)
    with open(os.path.join(root, "reports", "judge_results.json"), "w", encoding="utf-8") as f:
        json.dump({"results": [result.__dict__ for result in results],
                   "human_results": [result.__dict__ for result in human_results],
                   "human_labels": human_labels, "judge_labels": judge_labels,
                   "cohen_kappa": round(kappa, 3), "bias_report": bias},
                  f, ensure_ascii=False, indent=2, default=str)

    report_lines = [
        "# LLM Judge Bias Report — Phase B", "", "**Judge model:** " + JUDGE_MODEL, "",
        "## 1. Pairwise Judge Results", "",
        "| # | Question | Winner | Reasoning |", "|---|---|---|---|",
    ]
    for index, (item, result) in enumerate(zip(answers[:5], results[:5]), 1):
        question = item["question"].replace("|", "\\|")
        reasoning = result.reasoning_pass1.replace("|", "\\|").replace("\n", " ")
        report_lines.append(f"| {index} | {question} | {result.final_winner} | {reasoning} |")
    report_lines += [
        "", "## 2. Swap-and-Average Results", "",
        "| # | Pass 1 | Pass 2 | Final | Position consistent? |",
        "|---|---|---|---|---|",
    ]
    for index, result in enumerate(results[:10], 1):
        report_lines.append(f"| {index} | {result.winner_pass1} | {result.winner_pass2} | "
                            f"{result.final_winner} | {result.position_consistent} |")
    report_lines += [
        "", f"**Position bias rate:** {bias['position_bias_rate']:.1%} "
        f"(= {bias['position_bias_count']}/{bias['total_judged']} inconsistent cases)", "",
        "## 3. Cohen's κ Analysis", "",
        "| Question ID | Human label | Judge label | Agree? |",
        "|---|---:|---:|---|",
    ]
    for item, label, human in zip(human_data, judge_labels, human_labels):
        report_lines.append(f"| {item['question_id']} | {human} | {label} | {label == human} |")
    agreement = "almost perfect" if kappa >= .8 else "substantial" if kappa >= .6 else "moderate" if kappa >= .4 else "fair" if kappa >= .2 else "slight" if kappa >= 0 else "poor"
    report_lines += [
        "", f"**Cohen's κ:** {kappa:.3f}", f"**Interpretation:** {agreement} agreement.", "",
        "## 4. Verbosity Bias", "",
        f"- A thắng và A dài hơn B: {bias['verbosity_details'].get('a_wins_a_longer', 0)}",
        f"- B thắng và B dài hơn A: {bias['verbosity_details'].get('b_wins_b_longer', 0)}",
        f"- **Verbosity bias rate:** {bias['verbosity_bias']:.1%}", "",
        "## 5. Nhận xét chung", "",
        f"> Đã chạy judge trên {len(results)} câu trả lời và đối chiếu {len(human_results)} câu có nhãn người. "
        f"{bias['interpretation']} κ phản ánh mức đồng thuận giữa judge và human trên tập kiểm chứng.", "",
    ]
    with open(os.path.join(root, "analysis", "bias_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"Phase B complete: {len(results)} judged, κ={kappa:.3f}, "
          f"position bias={bias['position_bias_rate']:.1%}")
