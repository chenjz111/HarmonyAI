"""Offline rescore of saved evaluation JSON after evaluator taxonomy fixes.

Does NOT re-invoke Qwen. Applies taxonomy corrections to both
actual and expected emotion label sets and recomputes micro-F1.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rescore(report: dict, removed_labels: set[str]) -> dict:
    """Apply label removals and recompute all metrics."""
    per_case = report.get("per_case", [])
    normal = [
        c for c in per_case
        if c.get("status") != "ERROR"
        and c.get("expected_summary", {}).get("expected_safety_block") is not True
    ]

    # Recompute emotion pairs with label fixes
    fixed_pairs = []
    for case in normal:
        actual = set(case.get("actual_summary", {}).get("emotion_labels", []))
        expected = set(case.get("expected_summary", {}).get("emotion_labels", []))
        actual_fixed = actual - removed_labels
        expected_fixed = expected - removed_labels
        fixed_pairs.append((actual_fixed, expected_fixed))

    # Recompute micro-F1
    tp = sum(len(a & e) for a, e in fixed_pairs)
    pred_count = sum(len(a) for a, _ in fixed_pairs)
    gold_count = sum(len(e) for _, e in fixed_pairs)
    if pred_count == 0 and gold_count == 0:
        new_f1 = 1.0
        new_precision = 1.0
        new_recall = 1.0
    elif pred_count == 0 or gold_count == 0:
        new_f1 = 0.0
        new_precision = 0.0
        new_recall = 0.0
    else:
        new_precision = tp / pred_count
        new_recall = tp / gold_count
        new_f1 = 2 * new_precision * new_recall / (new_precision + new_recall)

    # Also recompute per-label stats
    label_tp = defaultdict(int)
    label_fp = defaultdict(int)
    label_fn = defaultdict(int)
    for actual, expected in fixed_pairs:
        for label in actual & expected:
            label_tp[label] += 1
        for label in actual - expected:
            label_fp[label] += 1
        for label in expected - actual:
            label_fn[label] += 1

    all_labels = sorted(set(list(label_tp) + list(label_fp) + list(label_fn)))
    per_label = {}
    for label in all_labels:
        l_tp = label_tp.get(label, 0)
        l_fp = label_fp.get(label, 0)
        l_fn = label_fn.get(label, 0)
        prec = l_tp / (l_tp + l_fp) if (l_tp + l_fp) > 0 else 0.0
        rec = l_tp / (l_tp + l_fn) if (l_tp + l_fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        per_label[label] = {"tp": l_tp, "fp": l_fp, "fn": l_fn, "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}

    # Count how many cases changed
    cases_changed = 0
    for case in normal:
        actual_old = set(case.get("actual_summary", {}).get("emotion_labels", []))
        expected_old = set(case.get("expected_summary", {}).get("emotion_labels", []))
        actual_new = actual_old - removed_labels
        expected_new = expected_old - removed_labels
        if actual_old != actual_new or expected_old != expected_new:
            cases_changed += 1

    return {
        "removed_labels": sorted(removed_labels),
        "cases_affected": cases_changed,
        "n_cases": len(normal),
        "old_f1": report["metrics"]["emotion_f1"],
        "new_f1": round(new_f1, 4),
        "new_precision": round(new_precision, 4),
        "new_recall": round(new_recall, 4),
        "new_tp": tp,
        "new_fp": pred_count - tp,
        "new_fn": gold_count - tp,
        "per_label": per_label,
    }


def main() -> int:
    eval_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "evals/sprint4/results/s4-06-evaluation.json"
    )
    report = load_report(eval_path)

    # Fix 1: Remove worry_control (scored=false, weight=0 per frozen contract)
    print("=" * 60)
    print("FIX 1: Remove worry_control from emotion taxonomy")
    print("       (scored=false, weight=0 per frozen contract)")
    print("=" * 60)
    r1 = rescore(report, {"worry_control"})
    print(f"  Old emotion_f1: {r1['old_f1']:.4f}")
    print(f"  New emotion_f1: {r1['new_f1']:.4f}")
    print(f"  New precision:  {r1['new_precision']:.4f}")
    print(f"  New recall:     {r1['new_recall']:.4f}")
    print(f"  Cases affected: {r1['cases_affected']}")
    print(f"  TP: {r1['new_tp']}, FP: {r1['new_fp']}, FN: {r1['new_fn']}")
    print()
    print("  Per-label after fix:")
    for label, stats in sorted(r1["per_label"].items(), key=lambda kv: -kv[1]["fn"]):
        impact = "LO" if stats["f1"] < 0.6 else ("MID" if stats["f1"] < 0.8 else "OK")
        print(
            f"  {label:<25} TP={stats['tp']:>2} FP={stats['fp']:>2} FN={stats['fn']:>2} "
            f"P={stats['precision']:.4f} R={stats['recall']:.4f} F1={stats['f1']:.4f} {impact}"
        )

    cumulative = r1["new_f1"]
    print()
    print(f"  Cumulative emotion_f1 after Fix 1: {cumulative:.4f}")

    # Fix 2: emotional_recovery and calm_wellbeing are positive/recovery states.
    # The model produces them very rarely. Let's check if removing them
    # would pass the threshold (as a diagnostic, not as a fix).
    print()
    print("=" * 60)
    print("DIAGNOSTIC: What if calm_wellbeing + emotional_recovery were excluded?")
    print("           (NOT a recommended fix — just understanding impact)")
    print("=" * 60)
    r2 = rescore(report, {"worry_control", "calm_wellbeing", "emotional_recovery"})
    print(f"  Old emotion_f1: {r1['old_f1']:.4f}")
    print(f"  New emotion_f1: {r2['new_f1']:.4f}")
    print(f"  New precision:  {r2['new_precision']:.4f}")
    print(f"  New recall:     {r2['new_recall']:.4f}")
    print(f"  TP: {r2['new_tp']}, FP: {r2['new_fp']}, FN: {r2['new_fn']}")

    # Fix 3: What if we also fixed the low_mood recall issue?
    # low_mood has 10 FN. If even half of those were recovered...
    print()
    print("=" * 60)
    print("WHAT-IF: Improve low_mood recall from 0.50 to 0.75")
    print("         (recover 5 of 10 FN — requires model/prompt fix)")
    print("=" * 60)
    # Simulate: recover 5 low_mood FN
    simulated_tp = r1["new_tp"] + 5
    simulated_fn = r1["new_fn"] - 5
    sim_prec = simulated_tp / (simulated_tp + r1["new_fp"]) if (simulated_tp + r1["new_fp"]) > 0 else 0
    sim_rec = simulated_tp / (simulated_tp + simulated_fn) if (simulated_tp + simulated_fn) > 0 else 0
    sim_f1 = 2 * sim_prec * sim_rec / (sim_prec + sim_rec) if (sim_prec + sim_rec) > 0 else 0
    print(f"  Simulated emotion_f1: {sim_f1:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
