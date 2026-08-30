"""医学审核元数据落盘测试（PR #89 review 增量项）。

要求：
  1. multi_organ_rules 每条规则明确 来源(source) 与 审核状态(review_status/review_version)。
  2. 评测文件 cases.jsonl 每个用例记录 医学审核版本与审核状态。
"""
import json
import sys
from pathlib import Path

# Windows 中文环境 stdout 默认 GBK，emoji 输出会 UnicodeEncodeError（PR #89 复审问题 2）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_V3 = ROOT / "knowledge" / "v3"
CASES_PATH = ROOT / "evals" / "sprint5" / "cases.jsonl"


def _load_om():
    with open(KNOWLEDGE_V3 / "organ-mapping-v3.0.json", encoding="utf-8") as f:
        return json.load(f)


def _load_cases():
    with open(CASES_PATH, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def test_multi_organ_rules_have_source_and_review_status():
    """每条 multi_organ_rule 须含 source（来源）+ review_status/review_version（审核状态）。"""
    om = _load_om()
    assert om["review_status"] == "approved"
    for rule in om["multi_organ_rules"]:
        assert rule.get("source"), f"{rule['claim_code']} 缺 source（来源）"
        assert rule.get("review_status") == "approved", f"{rule['claim_code']} 缺/错 review_status"
        assert rule.get("review_version"), f"{rule['claim_code']} 缺 review_version"
    print(f"✅ 多脏规则: {len(om['multi_organ_rules'])} 条含 source/review_status/review_version")


def test_eval_cases_record_medical_review():
    """每个评测用例须记录医学审核版本与审核状态。"""
    cases = _load_cases()
    assert cases, "评测集为空"
    for c in cases:
        assert c.get("medical_review_status") == "approved", f"{c['case_id']} 缺/错 medical_review_status"
        assert c.get("medical_review_version"), f"{c['case_id']} 缺 medical_review_version"
    print(f"✅ 评测集: {len(cases)} 个用例含医学审核版本与状态")
