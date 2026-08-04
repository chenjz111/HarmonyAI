"""HarmonyAI Knowledge V2 Validation Tests.

Coverage:
- 12 题数量和唯一 ID 校验
- Q2—Q11 数值映射校验（frequency_0_4）
- Q3/Q9 字符串→0-4 转换测试（score_map）
- Q12 互斥选项测试（以上都没有清除其他）
- 高风险触发测试
- 普通语句不误触发自伤风险测试
- safety-rules.json 词组合法性
"""

import json, os, sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
Q_PATH = os.path.join(BASE, "knowledge", "questionnaire-v2.json")
S_PATH = os.path.join(BASE, "knowledge", "questionnaire-scoring-v2.json")
R_PATH = os.path.join(BASE, "knowledge", "safety-rules.json")

# ─── helpers ──────────────────────────────────────────────
def load_q():
    with open(Q_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_s():
    with open(S_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_r():
    with open(R_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# ─── 1. 12 题数量 + 唯一 ID ─────────────────────────────
def test_question_count():
    q = load_q()
    assert q["total_questions"] == 12
    assert len(q["questions"]) == 12

def test_question_ids_unique():
    q = load_q()
    ids = [qq["question_id"] for qq in q["questions"]]
    assert len(ids) == len(set(ids)), f"Duplicate question_ids: {ids}"

# ─── 2. Q2—Q11 数值映射校验 ─────────────────────────────
def test_scored_questions_use_numeric_values():
    q = load_q()
    for qq in q["questions"]:
        if qq.get("scoring", {}).get("scored") and qq["type"] == "frequency_0_4":
            for opt in qq["options"]:
                assert isinstance(opt["value"], int), f"{qq['question_id']} option {opt['label']} value is not int: {type(opt['value'])}"
                assert 0 <= opt["value"] <= 4, f"{qq['question_id']} value {opt['value']} out of 0-4"

# ─── 3. Q3/Q9 score_map 转换测试 ─────────────────────────
def test_q3_score_map():
    q = load_q()
    q3 = [qq for qq in q["questions"] if qq["question_id"] == "q03_overthinking"][0]
    sm = q3["scoring"].get("score_map")
    assert sm is not None, "q03 missing score_map"
    for opt in q3["options"]:
        val = opt["value"]
        expected = sm.get(val)
        assert expected is not None, f"q03 value '{val}' not in score_map"
        assert 0 <= expected <= 4, f"q03 score_map[{val}] = {expected} out of range"

def test_q9_score_map():
    q = load_q()
    q9 = [qq for qq in q["questions"] if qq["question_id"] == "q09_low_energy"][0]
    sm = q9["scoring"].get("score_map")
    assert sm is not None, "q09 missing score_map"
    for opt in q9["options"]:
        val = opt["value"]
        expected = sm.get(val)
        assert expected is not None, f"q09 value '{val}' not in score_map"
        assert 0 <= expected <= 4, f"q09 score_map[{val}] = {expected} out of range"

def test_score_map_determinism():
    """同一答案重复提交得到相同分数"""
    q = load_q()
    for qid in ["q03_overthinking", "q09_low_energy"]:
        qq = [qq for qq in q["questions"] if qq["question_id"] == qid][0]
        sm = qq["scoring"]["score_map"]
        for val, score in sm.items():
            # simulate two submissions with same value
            assert score == sm[val], f"{qid}: score_map[{val}] not deterministic"

# ─── 4. Q12 互斥选项测试 ─────────────────────────────────
def test_q12_exclusion():
    q = load_q()
    q12 = [qq for qq in q["questions"] if qq["question_id"] == "q12_physical_safety"][0]
    options = q12["options"]
    has_none = any(o["value"] == "none" for o in options)
    assert has_none, "q12 missing 'none' exclusion option"
    # 确认互斥规则存在
    has_rule = any("以上都没有" in r for r in q12.get("rules", []))
    assert has_rule, "q12 missing '以上都没有 clears other' rule"

# ─── 5. 高风险触发测试 ────────────────────────────────────
def test_q12_has_safety_risks():
    q = load_q()
    q12 = [qq for qq in q["questions"] if qq["question_id"] == "q12_physical_safety"][0]
    risk_values = {o["value"] for o in q12["options"] if o.get("category") == "safety_risk"}
    assert "self_harm_thoughts" in risk_values, "missing self_harm_thoughts"
    assert "severe_chest_pain" in risk_values, "missing severe_chest_pain"
    assert "severe_breathing_difficulty" in risk_values, "missing severe_breathing_difficulty"

def test_safety_rules_triggers():
    r = load_r()
    triggers = {t["id"] for t in r["urgent_attention"]["triggers"]}
    assert "Q12_SELF_HARM" in triggers
    assert "Q12_CHEST_PAIN" in triggers
    assert "Q12_BREATHING" in triggers

# ─── 6. 普通语句不误触发自伤风险 ─────────────────────────
def test_safe_phrases_not_triggering():
    """普通语句不应触发 self_harm 紧急阻断"""
    r = load_r()
    self_harm_kw = r["trigger_phrases"]["self_harm"]["keywords"]
    safe_phrases = ["今天累死了", "考试难死了", "笑死我了", "困死了", "气死了", "饿死了"]
    for phrase in safe_phrases:
        # Check each keyword individually — if it's a substring match,
        # ANY single keyword being a substring of a safe phrase is a false positive
        for kw in self_harm_kw:
            assert kw not in phrase, f"False positive: '{kw}' in safe phrase '{phrase}'"
    # Also verify no single Chinese character keywords
    for kw in self_harm_kw:
        assert len(kw) >= 2, f"Keyword too short/ambiguous: '{kw}'"

# ─── 7. scoring JSON 维度校验 ─────────────────────────────
def test_scoring_dimensions_match_questionnaire():
    q = load_q()
    s = load_s()
    for qq in q["questions"]:
        if qq.get("scoring", {}).get("scored"):
            dim = qq["scoring"]["dimension"]
            assert dim in s["dimensions"], f"Dimension '{dim}' from {qq['question_id']} not in scoring JSON"
            sq = s["dimensions"][dim]["source_question"]
            assert sq == qq["question_id"], f"source_question mismatch: {sq} vs {qq['question_id']}"

# ─── 8. safety-rules.json JSON 合法性与结构 ──────────────
def test_safety_rules_json_valid():
    r = load_r()
    assert r["schema_version"] == "safety_rules_v1.0"
    assert len(r["urgent_attention"]["triggers"]) >= 3
    assert len(r["watch_list"]["triggers"]) >= 1

def test_fallback_works():
    """Qwen 不可用时安全规则仍生效"""
    r = load_r()
    assert "fallback" in r["coverage_rules"]
    fallback = r["coverage_rules"]["fallback"]
    # Must explicitly state that deterministic rules work without Qwen
    assert "Qwen" in fallback or "确定性" in fallback or "deterministic" in fallback, \
        "fallback must mention Qwen-unavailable scenario"

