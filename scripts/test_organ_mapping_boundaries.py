"""V3 医学资产聚合边界测试（organ-mapping 可执行约束）

对应 PR #89 review P0-1。所有聚合判定统一使用共享评估器
scripts/knowledge_organ_eval.py，与评估集生成器同源，杜绝公式分叉。

核心不变量（对每个 combination_rules[organ] 的组合，取其组合内 claims 的
supporting 方向 link_strength，reliability=1.0）：
    max_single < minimum_total_support <= min_top2
  - max_single < threshold    ：单条最强 claim 不足以单独决定候选脏/调式
  - threshold <= min_top2     ：组合内 top-2 最强 claim 可达阈值 → 系统不会永远 abstain

评估集一致性：evals/sprint5/cases.jsonl 的 expected 必须与评估器重算结果一致。

可同时以脚本或 pytest 运行：
    python scripts/test_organ_mapping_boundaries.py
    python -m pytest scripts/test_organ_mapping_boundaries.py -v
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_organ_eval import (
    load_organ_mapping,
    decide_candidates,
    compute_organ_scores,
    organ_claim_counts,
    combo_claims_for,
    ORGAN_ORDER,
)

CASES_PATH = os.path.join(ROOT, "evals", "sprint5", "cases.jsonl")


# --------------------------------------------------------------------------
# 不变量与可达性
# --------------------------------------------------------------------------

def combo_claim_strengths(om, organ):
    """组合内 claims 的 supporting link_strength 列表（reliability=1.0 时单条最大贡献）。"""
    strength = {m["claim_code"]: m for m in om["single_mappings"]}
    out = []
    for claim in combo_claims_for(om, organ):
        m = strength.get(claim)
        if m is not None and m["direction"] == "supporting":
            out.append(m["link_strength"])
    return sorted(out, reverse=True)


def test_invariant_max_single_lt_threshold_le_top2():
    """每个组合：max_single < threshold <= min_top2。"""
    om = load_om()
    threshold = om["thresholds"]["minimum_total_support"]
    for combo in om["combination_rules"]:
        strengths = combo_claim_strengths(om, combo["organ"])
        assert len(strengths) >= combo["min_count"], (
            f"{combo['organ']} 组合内 supporting claims 数 {len(strengths)} < min_count {combo['min_count']}")
        max_single = strengths[0]
        min_top2 = sum(strengths[:combo["min_count"]])
        assert max_single < threshold, (
            f"{combo['organ']} 违反不变量：单条 max_single={max_single} 应 < threshold={threshold}")
        assert threshold <= min_top2, (
            f"{combo['organ']} 违反不变量：threshold={threshold} 应 <= 组合内 top-{combo['min_count']} 之和 {min_top2}；"
            f"阈值不可达，系统会永远 abstain")
    print(f"✅ 不变量: 全部 {len(om['combination_rules'])} 个组合满足 "
          f"max_single < {threshold} <= min_top{min(c['min_count'] for c in om['combination_rules'])}")


def test_single_evidence_never_decides():
    """任何单条组合内 claim（reliability=1.0）不得产生候选脏。"""
    om = load_om()
    strength = {m["claim_code"]: m for m in om["single_mappings"]}
    for combo in om["combination_rules"]:
        organ = combo["organ"]
        for claim in combo_claims_for(om, organ):
            _, primary, _, candidates = decide_candidates(om, {claim: 1.0})
            assert not any(c == organ for c, _ in candidates), (
                f"{claim} 单条证据(link_strength={strength[claim]['link_strength']})即成为候选脏 {organ}")
    total_claims = sum(len(combo_claims_for(om, c["organ"])) for c in om["combination_rules"])
    print(f"✅ 单证据: 全部 {total_claims} 条组合内 claim 单条均不能决定候选脏")


def test_reachability_top_claims_trigger_candidate():
    """可达性：组合内 top-2 最强 claim 同时出现时，该脏必须成为候选（系统不会永远 abstain）。"""
    om = load_om()
    for combo in om["combination_rules"]:
        organ = combo["organ"]
        strength = {m["claim_code"]: m["link_strength"] for m in om["single_mappings"]}
        combo_claims = sorted(combo_claims_for(om, organ),
                              key=lambda c: -strength.get(c, 0.0))
        top_claims = combo_claims[: combo["min_count"]]
        scores, primary, _, candidates = decide_candidates(om, {c: 1.0 for c in top_claims})
        assert any(c == organ for c, _ in candidates), (
            f"{organ} 可达性失败：top-{combo['min_count']} claims {top_claims} 无法触发候选 "
            f"(organ_net={scores[organ]:.3f}，threshold={om['thresholds']['minimum_total_support']})")
    print(f"✅ 可达性: 全部 {len(om['combination_rules'])} 个组合 top-{om['combination_rules'][0]['min_count']} 均可触发候选")


def _strength_of(om, claim):
    for m in om["single_mappings"]:
        if m["claim_code"] == claim:
            return m["link_strength"]
    return 0.0


# --------------------------------------------------------------------------
# 评估集一致性（cases.jsonl 可执行）
# --------------------------------------------------------------------------

def test_eval_cases_consistent_with_evaluator():
    """evals/sprint5/cases.jsonl 每个用例的 expected 必须与评估器重算一致。

    冲突用例（type=conflict）由 Understanding 层判定，expected.abstain 原样保留、
    expected_tones 为空；非冲突用例按候选规则推导 primary/abstain。
    """
    om = load_om()
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    assert cases, f"{CASES_PATH} 为空"

    fails = []
    for case in cases:
        cid = case["case_id"]
        exp = case["expected"]
        evidence = case["input"].get("evidence", {})
        scores, primary, secondary, _ = decide_candidates(om, evidence)

        if case["type"] == "conflict":
            if primary is not None:
                fails.append(f"{cid}: 冲突用例不应有候选脏 primary={primary}")
            if exp["expected_tones"]:
                fails.append(f"{cid}: 冲突用例 expected_tones 应为空")
        else:
            if exp["abstain"] != (primary is None):
                fails.append(f"{cid}: abstain={exp['abstain']} 与候选判定 primary={primary} 不一致")
            if exp["primary_organ"] != primary:
                fails.append(f"{cid}: primary_organ expected={exp['primary_organ']} 实算={primary}")

        if exp["secondary_organs"] != list(secondary):
            fails.append(f"{cid}: secondary_organs expected={exp['secondary_organs']} 实算={list(secondary)}")

        for org in ORGAN_ORDER:
            if abs(scores[org] - exp["organ_net"][org]) > 1e-6:
                fails.append(f"{cid}: organ_net[{org}] expected={exp['organ_net'][org]} 实算={round(scores[org], 6)}")

    assert not fails, f"评估集与评估器不一致：\n" + "\n".join(fails)
    print(f"✅ 评估集: {len(cases)} 个 sprint5 用例与评估器重算一致（主脏/次脏/abstain/organ_net）")


# --------------------------------------------------------------------------
# 结构性校验
# --------------------------------------------------------------------------

def load_om():
    return load_organ_mapping()


def test_all_combos_have_executable_conditions():
    om = load_om()
    for combo in om["combination_rules"]:
        assert combo.get('min_count') is not None, f'{combo["organ"]} 缺 min_count'
        assert combo.get('min_count') >= 2, f'{combo["organ"]} min_count 应 >=2'
        assert combo.get('support_formula'), f'{combo["organ"]} 缺 support_formula'
        assert 'sum(' in combo['support_formula'], f'{combo["organ"]} support_formula 应为 sum 语义'
    print(f'✅ 结构: {len(om["combination_rules"])} 个组合全部可执行（min_count>=2，sum 语义）')


def test_thresholds_fields_present():
    om = load_om()
    t = om['thresholds']
    assert t.get('minimum_total_support') is not None, '缺 minimum_total_support'
    assert t.get('minimum_evidence_count') is not None, '缺 minimum_evidence_count'
    assert t['minimum_evidence_count'] >= 2, 'minimum_evidence_count 应>=2'
    # 阈值有效性由不变量测试保证：max_single < threshold <= min_top2
    print(f'✅ 结构: thresholds minimum_total_support={t["minimum_total_support"]} / minimum_evidence_count={t["minimum_evidence_count"]}')


def test_mapping_version_present():
    om = load_om()
    assert om.get('mapping_version'), '缺 mapping_version'
    print(f'✅ 结构: mapping_version={om["mapping_version"]}')


def test_organ_element_consistent():
    om = load_om()
    oe = om['organ_element']
    for m in om['single_mappings']:
        assert oe[m['organ']] == m['element'], f'{m["claim_code"]} organ/element 不一致'
    print(f'✅ 结构: organ/element 一致性通过')


if __name__ == '__main__':
    test_invariant_max_single_lt_threshold_le_top2()
    test_single_evidence_never_decides()
    test_reachability_top_claims_trigger_candidate()
    test_eval_cases_consistent_with_evaluator()
    test_all_combos_have_executable_conditions()
    test_thresholds_fields_present()
    test_mapping_version_present()
    test_organ_element_consistent()
    print()
    print('🎉 ORGAN MAPPING BOUNDARY TESTS: ALL PASS')
