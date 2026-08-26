from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (TEST_SET_PATH, OPENAI_API_KEY, OPENAI_BASE_URL,
                    JUDGE_MODEL, EMBEDDING_MODEL)

METRIC_NAMES = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _safe_float(value) -> float:
    """RAGAS trả NaN khi metric không tính được → quy về 0.0."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if v != v else v  # NaN != NaN


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY/Groq key is required for real RAGAS evaluation.")

    from ragas import evaluate
    from ragas.metrics import (faithfulness, answer_relevancy,
                               context_precision, context_recall)
    from datasets import Dataset
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_openai import ChatOpenAI

    dataset = Dataset.from_dict({
        "question": questions, "answer": answers,
        "contexts": contexts, "ground_truth": ground_truths,
    })
    llm = ChatOpenAI(model=JUDGE_MODEL, api_key=OPENAI_API_KEY,
                     base_url=OPENAI_BASE_URL or None, temperature=0, n=1)
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    answer_relevancy.strictness = 1
    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
                                        context_precision, context_recall],
                      llm=llm, embeddings=embeddings,
                      raise_exceptions=True)
    df = result.to_pandas()

    per_question = [
        EvalResult(
            question=row["question"], answer=row["answer"],
            contexts=list(row["contexts"]), ground_truth=row["ground_truth"],
            faithfulness=_safe_float(row.get("faithfulness", 0.0)),
            answer_relevancy=_safe_float(row.get("answer_relevancy", 0.0)),
            context_precision=_safe_float(row.get("context_precision", 0.0)),
            context_recall=_safe_float(row.get("context_recall", 0.0)),
        )
        for _, row in df.iterrows()
    ]
    n = max(len(per_question), 1)
    return {**{m: sum(getattr(r, m) for r in per_question) / n
               for m in METRIC_NAMES}, "per_question": per_question}


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    diagnostic_tree = {
        "faithfulness": ("LLM hallucinating",
                         "Tighten prompt, lower temperature"),
        "context_recall": ("Missing relevant chunks",
                           "Improve chunking or add BM25"),
        "context_precision": ("Too many irrelevant chunks",
                              "Add reranking or metadata filter"),
        "answer_relevancy": ("Answer doesn't match question",
                             "Improve prompt template"),
    }

    scored = []
    for r in eval_results:
        metrics = {m: getattr(r, m) for m in METRIC_NAMES}
        avg = sum(metrics.values()) / len(metrics)
        worst_metric = min(metrics, key=metrics.get)
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        scored.append({
            "question": r.question,
            "answer": r.answer,
            "ground_truth": r.ground_truth,
            "avg_score": round(avg, 4),
            "worst_metric": worst_metric,
            "score": round(metrics[worst_metric], 4),
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
        })

    scored.sort(key=lambda x: x["avg_score"])
    return scored[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
