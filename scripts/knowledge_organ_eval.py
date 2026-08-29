"""Shared V3 organ-mapping aggregation evaluator（唯一事实来源）。

统一判定语义：organ_net(脏) = Σ(link_strength × reliability × direction_signed)，
对所有映射到该脏的 present claims 求和（sum 语义，与 organ-mapping-v3.0.json 中
thresholds.organ_net_formula 一致）。

本模块被以下两处共用，保证公式、阈值与评估期望值永远一致：
  1. scripts/test_organ_mapping_boundaries.py  —— 边界测试（单证据不决定 / 可达性）
  2. scripts/regenerate_eval_organ_net.py      —— 重算 evals/sprint5/cases.jsonl 期望值

reliability 默认值来自 organ-mapping-v3.0.json 的 scoring_spec.reliability_model，
供医学侧（Medical Knowledge Engineer）复核。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OM_PATH = os.path.join(ROOT, "knowledge", "v3", "organ-mapping-v3.0.json")

ORGAN_ORDER = ["liver", "heart", "spleen", "lung", "kidney"]

# 问卷题目 → claim 代码（questionnaire-v3.0.json 的结构映射）
QUESTION_CLAIMS = {
    "q01": ("anger_tendency", "questionnaire_emotion"),
    "q02": ("agitation_tendency", "questionnaire_emotion"),
    "q03": ("overthinking_tendency", "questionnaire_emotion"),
    "q04": ("sadness_tendency", "questionnaire_emotion"),
    "q05": ("fear_tendency", "questionnaire_emotion"),
    "q06": ("multi", "questionnaire_body"),
    "q07": ("multi", "questionnaire_body"),
    "q08": ("multi", "questionnaire_body"),
    "q09": ("multi", "questionnaire_body"),
    "q10": ("multi", "questionnaire_body"),
}


def load_organ_mapping():
    with open(OM_PATH, encoding="utf-8") as f:
        return json.load(f)


def reliability_for(source, answer_value=None):
    """source ∈ questionnaire_body / questionnaire_emotion / narrative / document。"""
    if source == "questionnaire_body":
        return 1.0
    if source == "questionnaire_emotion":
        # frequency_0_4：得分越高可靠性越高（1→0.25 … 4→1.0）
        if answer_value is None:
            return 0.0
        return max(0.0, min(1.0, float(answer_value) / 4.0))
    if source == "narrative":
        return 0.6
    if source == "document":
        return 0.7
    return 1.0


def _dedup_claims(om, present_claims):
    """按 conflict_rules 去重：
    - worry_control 与 overthinking_tendency 同族，同时出现只计 overthinking（问卷主源）
    - 睡眠家族 sleep_disturbance / unrefreshing_sleep 已由问卷结构避免同源重复，此处不强合并
    """
    present = dict(present_claims)
    if "overthinking_tendency" in present and "worry_control" in present:
        del present["worry_control"]
    return present


def combo_claims_for(om, organ):
    """combination_rules[organ].claims —— 参与该脏候选判定的权威 claim 集合。

    single_mappings 里的多脏/通用 claim（sleep_disturbance、low_energy、daily_impact、
    social_withdrawal、exertional_breathlessness 等）note 明确"不单独决定某脏/不映射单脏"，
    不参与候选的计数与求和；组合内成员以 combination_rules 声明为准（thresholds.organ_net_formula
    ③'该脏组合内最大值'）。
    """
    for combo in om["combination_rules"]:
        if combo["organ"] == organ:
            return set(combo["claims"])
    return set()


def _strength_map(om):
    return {m["claim_code"]: m for m in om["single_mappings"]}


def compute_organ_scores(om, present_claims):
    """present_claims: {claim_code: reliability}。返回 {organ: organ_net}。
    organ_net(脏) = Σ(link_strength × reliability × direction_signed)，仅对该脏
    combination_rules[organ].claims 内的 present claims 求和。
    """
    present = _dedup_claims(om, present_claims)
    strength = _strength_map(om)
    scores = {org: 0.0 for org in ORGAN_ORDER}
    for org in ORGAN_ORDER:
        combo_claims = combo_claims_for(om, org)
        for claim in combo_claims & present.keys():
            m = strength.get(claim)
            if m is None:
                continue
            direction = 1.0 if m["direction"] == "supporting" else -1.0
            scores[org] += m["link_strength"] * present[claim] * direction
    return scores


def organ_claim_counts(om, present_claims):
    """每个脏组合内 present 的不同 claim 条数（≤ combination_rules[organ].claims）。"""
    present = _dedup_claims(om, present_claims)
    counts = {org: 0 for org in ORGAN_ORDER}
    for org in ORGAN_ORDER:
        combo_claims = combo_claims_for(om, org)
        counts[org] = len(combo_claims & present.keys())
    return counts


def decide_candidates(om, present_claims):
    """返回 (scores, primary, secondary, candidates)。

    candidates = [(organ, organ_net)]，按 organ_net 降序（同分按 ORGAN_ORDER）。
    候选规则：present distinct claims ≥ combination_rules[organ].min_count
              且 organ_net ≥ thresholds.minimum_total_support。
    """
    scores = compute_organ_scores(om, present_claims)
    counts = organ_claim_counts(om, present_claims)
    min_count = {c["organ"]: c["min_count"] for c in om["combination_rules"]}
    min_support = om["thresholds"]["minimum_total_support"]

    candidates = []
    for org in ORGAN_ORDER:
        if counts[org] < min_count.get(org, 2):
            continue
        if scores[org] < min_support:
            continue
        candidates.append((org, scores[org]))
    candidates.sort(key=lambda x: (-x[1], ORGAN_ORDER.index(x[0])))
    primary = candidates[0][0] if candidates else None
    secondary = [org for org, _ in candidates[1:]]
    return scores, primary, secondary, candidates


def extract_present_claims(om, q_answers, narrative_claims=(), document_claims=()):
    """把问卷 + 叙述 + 文档的抽取结果统一成 {claim_code: reliability}。

    q_answers:       {question_id: value}；frequency_0_4 为 0-4，multi_choice_evidence 为 option_code 列表
    narrative_claims: 叙述/Understanding 抽取出的 claim 代码列表（rel=narrative 0.6）
    document_claims:  文档/OCR 抽取出的 claim 代码列表（rel=document 0.7）
    """
    present = {}
    for qid, value in (q_answers or {}).items():
        claim, source = QUESTION_CLAIMS.get(qid, (None, None))
        if claim is None:
            continue
        if claim == "multi":
            for opt in (value or []):
                present[opt] = 1.0
        else:
            if value and int(value) > 0:
                present[claim] = reliability_for(source, answer_value=int(value))
    for c in narrative_claims:
        present[c] = reliability_for("narrative")
    for c in document_claims:
        present[c] = reliability_for("document")
    return present
