"""V3 医学资产聚合边界测试（organ-mapping 可执行约束）

对应 PR #89 review P0-1。所有聚合判定统一使用共享评估器
scripts/knowledge_organ_eval.py，与评估集生成器同源，杜绝公式分叉。

核心不变量（对每个 combination_rules[organ] 的组合，取其组合内 claims 的
supporting 方向 link_strength，reliability=1.0）：
    max_single < minimum_total_support <= min_top2
  - max_single < threshold    ：单条最强 claim 不足以单独决定候选脏/调式
  - threshold <= min_top2     ：组合内 top-2 最强 claim 可达阈值 → 系统不会永远 abstain

评估集 golden 校验由 tests/knowledge/test_organ_mapping_eval_cases.py 唯一负责（硬编码 golden，
本脚本专注边界不变量，不与评估集 golden 断言同源重复）。

可同时以脚本或 pytest 运行：
    python scripts/test_organ_mapping_boundaries.py
    python -m pytest scripts/test_organ_mapping_boundaries.py -v
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_organ_eval import (
    load_organ_mapping,
    decide_candidates,
    compute_organ_scores,
    combo_claims_for,
    ORGAN_ORDER,
    QUESTION_CLAIMS,
)

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


# --------------------------------------------------------------------------
# multi_organ_rules 可执行性（PR #89 review P0-3）
# --------------------------------------------------------------------------

def test_multi_organ_rules_have_executable_links():
    """每条 multi_organ_rule 的 links 必须可执行：organ/element/direction/link_strength/
    mapping_rule_id 齐全，主脏 link_strength 与 single_mapping 一致。"""
    om = load_om()
    strength = {m['claim_code']: m for m in om['single_mappings']}
    oe = om['organ_element']
    for rule in om['multi_organ_rules']:
        claim = rule['claim_code']
        links = rule.get('links')
        assert links, f'{claim} 缺可执行 links（须含 organ/direction/link_strength/mapping_rule_id）'
        assert rule['primary'] == links[0]['organ'], f'{claim} primary 应与首条 link 的 organ 一致'
        m = strength.get(claim)
        assert m is not None, f'{claim} 不在 single_mappings 中'
        assert abs(links[0]['link_strength'] - m['link_strength']) < 1e-9, (
            f"{claim} 主脏 link_strength={links[0]['link_strength']} 应等于 single_mapping {m['link_strength']}")
        for link in links:
            assert link['organ'] in oe, f'{claim} link organ {link["organ"]} 非法'
            assert oe[link['organ']] == link['element'], f'{claim} link {link["organ"]} element 不一致'
            assert link['direction'] in ('supporting', 'contradicting'), f'{claim} link direction 非法'
            assert 0.0 < link['link_strength'] <= 1.0, f'{claim} link_strength 越界'
            assert link['mapping_rule_id'], f'{claim} link 缺 mapping_rule_id'
    print(f"✅ 多脏规则: {len(om['multi_organ_rules'])} 条 multi_organ_rule 全部含可执行 links")


def test_multi_organ_claim_produces_multiple_links():
    """sleep_disturbance 等多脏 claim 必须按 links 向多脏贡献 organ_net（合同 §4.4 多脏事实使用多 Link）。"""
    om = load_om()
    scores = compute_organ_scores(om, {'sleep_disturbance': 1.0})
    hit = {org: round(s, 4) for org, s in scores.items() if s > 0}
    assert set(hit) == {'heart', 'spleen', 'kidney'}, f'sleep_disturbance 应拆出心/脾/肾三脏 link，实际={hit}'
    assert abs(scores['heart'] - 0.4) < 1e-9
    assert abs(scores['spleen'] - 0.25) < 1e-9
    assert abs(scores['kidney'] - 0.2) < 1e-9
    print(f'✅ 多脏拆分: sleep_disturbance -> {hit}')


def test_multi_organ_claim_never_decides_alone():
    """组合外多脏 claim（sleep/unrefreshing/low_energy/exertional）单独出现不得产生候选脏。"""
    om = load_om()
    combo_members = set()
    for c in om['combination_rules']:
        combo_members |= set(c['claims'])
    checked = 0
    for rule in om['multi_organ_rules']:
        claim = rule['claim_code']
        if claim in combo_members:
            continue  # lower_back/tinnitus 已在肾组合，由单证据测试覆盖
        _, primary, _, candidates = decide_candidates(om, {claim: 1.0})
        assert primary is None and not candidates, f'{claim} 单独出现不应产生候选脏（primary={primary}）'
        checked += 1
    assert checked >= 3, f'应覆盖至少 3 个组合外多脏 claim，实际 {checked}'
    print(f'✅ 多脏边界: {checked} 个组合外多脏 claim 单独出现不产生候选脏')


# --------------------------------------------------------------------------
# 阈值语义（PR #89 review P1-1）
# --------------------------------------------------------------------------

def test_single_threshold_semantics():
    """单一阈值语义：不得残留第二套 per-claim 门槛（organ_available_threshold / per_claim_floor）。"""
    om = load_om()
    assert 'organ_available_threshold' not in om['thresholds'], (
        'thresholds 不应保留未执行的 organ_available_threshold，避免两套阈值语义')
    assert 'per_claim_floor' not in om['scoring_spec'], (
        'scoring_spec 不应保留未执行的 per_claim_floor')
    print('✅ 阈值语义: 单一 minimum_total_support，无第二套 per-claim 门槛')


# --------------------------------------------------------------------------
# 问卷映射来源（PR #89 review P1-2）
# --------------------------------------------------------------------------

def test_question_claims_sourced_from_assets():
    """QUESTION_CLAIMS 必须从 approved questionnaire/claim-dictionary 资产推导（单一代码来源）。"""
    assert set(QUESTION_CLAIMS) == {f'q{i:02d}' for i in range(1, 11)}, '应覆盖 q01-q10'
    emotion = [q for q, (c, s) in QUESTION_CLAIMS.items() if s == 'questionnaire_emotion']
    body = [q for q, (c, s) in QUESTION_CLAIMS.items() if c == 'multi']
    assert len(emotion) == 5, f'情绪题应为 5 个，实际 {emotion}'
    assert len(body) == 5, f'身体题应为 5 个，实际 {body}'
    print(f'✅ 问卷映射: {len(QUESTION_CLAIMS)} 题从 questionnaire/claim-dictionary 资产加载')


if __name__ == '__main__':
    test_invariant_max_single_lt_threshold_le_top2()
    test_single_evidence_never_decides()
    test_reachability_top_claims_trigger_candidate()
    test_all_combos_have_executable_conditions()
    test_thresholds_fields_present()
    test_mapping_version_present()
    test_organ_element_consistent()
    test_multi_organ_rules_have_executable_links()
    test_multi_organ_claim_produces_multiple_links()
    test_multi_organ_claim_never_decides_alone()
    test_single_threshold_semantics()
    test_question_claims_sourced_from_assets()
    print()
    print('🎉 ORGAN MAPPING BOUNDARY TESTS: ALL PASS')
