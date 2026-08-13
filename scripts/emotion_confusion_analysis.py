"""Offline per-label emotion confusion analysis on saved evaluation JSON.

Reads the already-executed evaluation report and computes per-label
TP / FP / FN / precision / recall / F1 without re-invoking Qwen.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def per_label_analysis(report: dict) -> dict:
    """Compute per-label confusion stats from per_case results."""
    # Only consider non-ERROR, non-safety cases
    per_case = report.get("per_case", [])
    normal = [
        c for c in per_case
        if c.get("status") != "ERROR"
        and c.get("expected_summary", {}).get("expected_safety_block") is not True
    ]

    # Accumulate per-label TP/FP/FN
    label_tp: dict[str, int] = defaultdict(int)
    label_fp: dict[str, int] = defaultdict(int)
    label_fn: dict[str, int] = defaultdict(int)

    for case in normal:
        actual = set(case.get("actual_summary", {}).get("emotion_labels", []))
        expected = set(case.get("expected_summary", {}).get("emotion_labels", []))

        for label in actual & expected:
            label_tp[label] += 1
        for label in actual - expected:
            label_fp[label] += 1
        for label in expected - actual:
            label_fn[label] += 1

    # Compute per-label metrics
    all_labels = sorted(set(list(label_tp) + list(label_fp) + list(label_fn)))
    per_label = {}
    for label in all_labels:
        tp = label_tp.get(label, 0)
        fp = label_fp.get(label, 0)
        fn = label_fn.get(label, 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_label[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    # Sort by impact on overall F1 (largest FN first)
    ranked = sorted(per_label.items(), key=lambda kv: (-kv[1]["fn"], -kv[1]["fp"]))

    # Compute micro-average
    total_tp = sum(label_tp.values())
    total_fp = sum(label_fp.values())
    total_fn = sum(label_fn.values())
    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall) > 0
        else 0.0
    )

    return {
        "per_label": dict(ranked),
        "summary": {
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "micro_precision": round(micro_precision, 4),
            "micro_recall": round(micro_recall, 4),
            "micro_f1": round(micro_f1, 4),
            "n_cases": len(normal),
        },
    }


def main() -> int:
    eval_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "evals/sprint4/results/s4-06-evaluation.json"
    )
    report = load_report(eval_path)
    analysis = per_label_analysis(report)

    print("=" * 60)
    print("PER-LABEL EMOTION CONFUSION ANALYSIS")
    print("=" * 60)
    print(f"Cases analyzed: {analysis['summary']['n_cases']}")
    print(f"Micro F1: {analysis['summary']['micro_f1']}")
    print(f"Micro Precision: {analysis['summary']['micro_precision']}")
    print(f"Micro Recall: {analysis['summary']['micro_recall']}")
    print(f"Total TP: {analysis['summary']['total_tp']}")
    print(f"Total FP: {analysis['summary']['total_fp']}")
    print(f"Total FN: {analysis['summary']['total_fn']}")
    print()

    print(f"{'Label':<25} {'TP':>4} {'FP':>4} {'FN':>4} {'Prec':>7} {'Rec':>7} {'F1':>7} {'Impact'}")
    print("-" * 75)
    for label, stats in analysis["per_label"].items():
        impact = "LO" if stats["f1"] < 0.6 else ("MID" if stats["f1"] < 0.8 else "OK")
        print(
            f"{label:<25} {stats['tp']:>4} {stats['fp']:>4} {stats['fn']:>4} "
            f"{stats['precision']:>7.4f} {stats['recall']:>7.4f} {stats['f1']:>7.4f}  {impact}"
        )

    # Also show cases with the biggest mismatches
    print()
    print("=" * 60)
    print("CASES WITH EMOTION MISMATCH (top 20 by |Δ|)")
    print("=" * 60)
    normal = [
        c for c in report.get("per_case", [])
        if c.get("status") != "ERROR"
        and c.get("expected_summary", {}).get("expected_safety_block") is not True
    ]
    case_deltas = []
    for case in normal:
        actual = set(case.get("actual_summary", {}).get("emotion_labels", []))
        expected = set(case.get("expected_summary", {}).get("emotion_labels", []))
        missing = expected - actual
        extra = actual - expected
        case_deltas.append((case["case_id"], missing, extra, len(missing) + len(extra)))

    case_deltas.sort(key=lambda x: -x[3])
    for cid, missing, extra, delta in case_deltas[:20]:
        print(f"  {cid} (Δ={delta}): missing={sorted(missing)}, extra={sorted(extra)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
