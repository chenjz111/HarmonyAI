"""V3 医学资产聚合边界测试（organ-mapping 可执行约束）

对应陈家智 PR #89 review P0-1：
- 单题/单证据不得直接决定候选脏或调式
- combination_rules 必须可执行（min_count / minimum_total_support）
- 单证据失败必须有自动测试

运行：python scripts/test_organ_mapping_boundaries.py
"""
import json
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OM_PATH = os.path.join(ROOT, 'knowledge', 'v3', 'organ-mapping-v3.0.json')


def load_om():
    with open(OM_PATH, encoding='utf-8') as f:
        return json.load(f)


def combo_claims_for(om, organ):
    for combo in om['combination_rules']:
        if combo['organ'] == organ:
            return combo
    return None


def evaluate_single_claim(om, claim_code):
    """模拟只有单条 claim 证据时的判定：应因不满足 min_count / minimum_total_support 而失败"""
    # 找 claim 归属的组合
    organ = None
    link_strength = 0.0
    for m in om['single_mappings']:
        if m['claim_code'] == claim_code:
            organ = m['organ']
            link_strength = m['link_strength']
            break
    if organ is None:
        return None, None, 'claim not in single_mappings'

    combo = combo_claims_for(om, organ)
    if combo is None:
        return None, None, 'no combo for organ'

    # 模拟判定：单条证据
    evidence_count = 1  # 只有这一条
    total_support = link_strength  # reliability=1.0（问卷确定性）

    min_count = combo['min_count']
    min_support = om['thresholds']['minimum_total_support']

    passed = (evidence_count >= min_count) and (total_support >= min_support)
    return organ, link_strength, passed


def test_single_evidence_never_decides():
    """核心测试：任何单条 claim 都不能决定候选脏"""
    om = load_om()
    failures = []
    for m in om['single_mappings']:
        organ, strength, passed = evaluate_single_claim(om, m['claim_code'])
        if passed is True:
            failures.append(f"{m['claim_code']} (strength={strength}) 单条证据即通过聚合判定")
    assert not failures, f'单证据判定失败项: {failures}'
    print(f'✅ 测试1: 全部 {len(om["single_mappings"])} 条 claim 单证据均不能决定候选脏')


def test_all_combos_have_executable_conditions():
    """每个组合必须有 min_count + required_groups + support_formula"""
    om = load_om()
    for combo in om['combination_rules']:
        assert combo.get('min_count') is not None, f'{combo["name"]} 缺 min_count'
        assert 'required_groups' in combo, f'{combo["name"]} 缺 required_groups'
        assert combo.get('support_formula'), f'{combo["name"]} 缺 support_formula'
        assert combo.get('min_count') >= 2, f'{combo["name"]} min_count 应 >=2'
    print(f'✅ 测试2: {len(om["combination_rules"])} 个组合全部可执行（min_count>=2）')


def test_thresholds_fields_present():
    """thresholds 必须有 minimum_total_support / minimum_evidence_count"""
    om = load_om()
    t = om['thresholds']
    assert t.get('minimum_total_support') is not None, '缺 minimum_total_support'
    assert t.get('minimum_evidence_count') is not None, '缺 minimum_evidence_count'
    assert t['minimum_total_support'] > 0.70, f'minimum_total_support 应>0.70（当前 {t["minimum_total_support"]}）'
    assert t['minimum_evidence_count'] >= 2, 'minimum_evidence_count 应>=2'
    print(f'✅ 测试3: thresholds 含 minimum_total_support={t["minimum_total_support"]} / minimum_evidence_count={t["minimum_evidence_count"]}')


def test_mapping_version_present():
    om = load_om()
    assert om.get('mapping_version'), '缺 mapping_version'
    print(f'✅ 测试4: mapping_version={om["mapping_version"]}')


def test_organ_element_consistent():
    om = load_om()
    oe = om['organ_element']
    for m in om['single_mappings']:
        assert oe[m['organ']] == m['element'], f'{m["claim_code"]} organ/element 不一致'
    print(f'✅ 测试5: organ/element 一致性通过')


if __name__ == '__main__':
    test_single_evidence_never_decides()
    test_all_combos_have_executable_conditions()
    test_thresholds_fields_present()
    test_mapping_version_present()
    test_organ_element_consistent()
    print()
    print('🎉 ORGAN MAPPING BOUNDARY TESTS: ALL PASS')
