"""校验 evals/sprint5/cases.jsonl 的 golden 期望值是否与共享评估器一致（diff-only）。

**只读**，不写回文件：cases.jsonl 的 expected 字段是医学侧人工审核的 golden 锚点，
本脚本仅用共享判定器 scripts/knowledge_organ_eval.py 重算并打印差异，供人工确认。

为什么不能自动覆盖：若本脚本用 decide_candidates 直接重写 expected，而测试又用同一个
decide_candidates 比对 expected，则评估集沦为「自证循环」，永远绿灯、无法捕获资产公式
漂移。因此 golden 只能人工更新——公式/阈值改动导致漂移时，由医学侧判断「是资产公式
该改，还是 golden 该跟着改」，二者只能动其一。

运行：python scripts/regenerate_eval_organ_net.py
退出码：0 = 全部一致；1 = 存在漂移（CI 可据此阻断）。
"""
import json
import os
import sys

# Windows 中文环境 stdout 默认 GBK，emoji 输出会 UnicodeEncodeError（PR #89 复审问题 2）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_organ_eval import load_organ_mapping, decide_candidates, ORGAN_ORDER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PATH = os.path.join(ROOT, "evals", "sprint5", "cases.jsonl")
FIVE_TONE_PATH = os.path.join(ROOT, "knowledge", "v3", "five-tone-mapping-v3.0.json")

ORGAN_TONE = {row["organ"]: row["tone"] for row in json.load(open(FIVE_TONE_PATH, encoding="utf-8"))["organ_tone_table"]}


def _recompute(om, case):
    """用共享判定器重算单个用例的 expected（与后端消费结构一致）。"""
    evidence = case["input"].get("evidence", {})
    scores, primary, secondary, _ = decide_candidates(om, evidence)

    if case["type"] == "conflict":
        abstain = False
        tones = []
    elif primary is None:
        abstain = True
        tones = ["wellness_generic"]
    else:
        abstain = False
        tones = [ORGAN_TONE[primary]]

    return {
        "primary_organ": primary,
        "secondary_organs": secondary,
        "organ_net": {org: round(scores[org], 4) for org in ORGAN_ORDER},
        "safety_flags": [],
        "abstain": abstain,
        "expected_tones": tones,
    }


def _diff(current, recomputed):
    """返回该用例的漂移字段列表（逐字段 + 逐脏 organ_net）。"""
    changed = []
    for key in ("primary_organ", "secondary_organs", "abstain", "expected_tones"):
        if current.get(key) != recomputed[key]:
            changed.append(key)
    for org in ORGAN_ORDER:
        cur = current.get("organ_net", {}).get(org)
        new = recomputed["organ_net"][org]
        if cur is None or abs(cur - new) >= 1e-6:
            changed.append(f"organ_net[{org}]")
    return changed


def main():
    om = load_organ_mapping()
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    print(f"读取 {len(cases)} 个用例（{CASES_PATH}）\n")
    drifted = 0
    for case in cases:
        cid = case["case_id"]
        current = case.get("expected", {})
        recomputed = _recompute(om, case)
        changed = _diff(current, recomputed)

        if not changed:
            print(f"OK     {cid:<8} primary={recomputed['primary_organ']}")
            continue
        drifted += 1
        print(f"DRIFT  {cid:<8} 差异字段: {', '.join(changed)}")
        for key in changed:
            if key.startswith("organ_net["):
                print(f"         {key}: golden={current['organ_net'][key[10:-1]]}  recomputed={recomputed['organ_net'][key[10:-1]]}")
            else:
                print(f"         {key}: golden={current.get(key)!r}  recomputed={recomputed[key]!r}")

    print()
    if drifted:
        print(f"⚠  {drifted}/{len(cases)} 个用例漂移。请医学侧人工判断后手改 golden 或资产，禁止自动覆盖。")
        sys.exit(1)
    print("✅ 全部用例与共享评估器一致，golden 未漂移。")


if __name__ == "__main__":
    main()
