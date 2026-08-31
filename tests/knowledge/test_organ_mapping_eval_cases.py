"""sprint5 评估集 golden 校验（PR #89 review P0-2）。

打破「自证循环」：golden 期望值在此硬编码为独立锚点（医学侧人工审核），
测试用共享判定器 decide_candidates 重算并与之比对。若资产公式/阈值漂移，
decide_candidates 输出会偏离 golden、测试失败——而非「生成器写 expected、
测试再用同一判定器读 expected」那样永远绿灯。

cases.jsonl 的 expected 字段是同一份人工审核结果的落盘形式，测试同时断言
它与 GOLDEN 一致，防止二者之一被悄悄改动。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge_organ_eval import (  # noqa: E402
    decide_candidates,
    load_organ_mapping,
    ORGAN_ORDER,
)

CASES_PATH = ROOT / "evals" / "sprint5" / "cases.jsonl"
FIVE_TONE_PATH = ROOT / "knowledge" / "v3" / "five-tone-mapping-v3.0.json"
OM = load_organ_mapping()

# 五音映射从 approved 资产加载（单一代码来源，非硬编码）
ORGAN_TONE = {
    row["organ"]: row["tone"]
    for row in json.load(open(FIVE_TONE_PATH, encoding="utf-8"))["organ_tone_table"]
}

# 独立 golden 锚点：主脏 / 次脏 / abstain / 调式 / organ_net（人工审核，勿自动改）。
GOLDEN = {
    "V3_N001": dict(primary="liver", secondary=[], abstain=False, tones=["jiao"],
                    organ_net={"liver": 1.7625, "heart": 0.1375, "spleen": 0.275, "lung": 0.1375, "kidney": 0.0}),
    "V3_N002": dict(primary="lung", secondary=[], abstain=False, tones=["shang"],
                    organ_net={"liver": 0.0, "heart": 0.0, "spleen": 0.1375, "lung": 1.7125, "kidney": 0.0}),
    "V3_N003": dict(primary="kidney", secondary=[], abstain=False, tones=["yu"],
                    organ_net={"liver": 0.0, "heart": 0.24, "spleen": 0.15, "lung": 0.0, "kidney": 1.8325}),
    "V3_I001": dict(primary=None, secondary=[], abstain=True, tones=["wellness_generic"],
                    organ_net={"liver": 0.0, "heart": 0.0, "spleen": 0.0, "lung": 0.0, "kidney": 0.0}),
    "V3_I002": dict(primary=None, secondary=[], abstain=True, tones=["wellness_generic"],
                    organ_net={"liver": 0.1375, "heart": 0.0, "spleen": 0.0, "lung": 0.0, "kidney": 0.0}),
    "V3_C001": dict(primary=None, secondary=[], abstain=False, tones=[],
                    organ_net={"liver": 0.0, "heart": 0.0, "spleen": 0.0, "lung": 0.4125, "kidney": 0.0}),
    "V3_D001": dict(primary="liver", secondary=[], abstain=False, tones=["jiao"],
                    organ_net={"liver": 0.875, "heart": 0.28, "spleen": 0.175, "lung": 0.0, "kidney": 0.14}),
    "V3_D002": dict(primary="spleen", secondary=[], abstain=False, tones=["gong"],
                    organ_net={"liver": 0.0, "heart": 0.0, "spleen": 1.68, "lung": 0.0, "kidney": 0.0}),
    "V3_Q001": dict(primary="spleen", secondary=[], abstain=False, tones=["gong"],
                    organ_net={"liver": 0.0, "heart": 0.0, "spleen": 1.9, "lung": 0.0, "kidney": 0.0}),
}


def _load_cases():
    with open(CASES_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def cases():
    assert CASES_PATH.exists(), f"缺少评估集: {CASES_PATH}"
    return _load_cases()


def test_sprint5_cases_not_empty(cases):
    assert len(cases) >= 9, "sprint5 评估集应至少 9 个用例"


def test_golden_covers_all_cases(cases):
    assert {c["case_id"] for c in cases} == set(GOLDEN), "GOLDEN 与 cases.jsonl 的用例集合不一致"


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["case_id"])
def test_eval_case_matches_golden(case):
    """每个用例：共享判定器重算结果必须命中硬编码 golden，而非文件里的 expected。"""
    cid = case["case_id"]
    g = GOLDEN[cid]
    evidence = case["input"].get("evidence", {})
    scores, primary, secondary, _ = decide_candidates(OM, evidence)

    assert g["primary"] == primary, f"{cid}: primary 偏离 golden（golden={g['primary']} 实算={primary}）"
    assert g["secondary"] == list(secondary), f"{cid}: secondary 偏离 golden"
    for org in ORGAN_ORDER:
        assert abs(scores[org] - g["organ_net"][org]) < 1e-6, (
            f"{cid}: organ_net[{org}] golden={g['organ_net'][org]} 实算={round(scores[org], 6)}")

    # abstain / tones：算法输出（与 regenerate 同语义）必须命中医学锚点 golden。
    # 此前这两项只经「数据文件 expected ↔ golden」校验（两边都是人工值，一致即过），
    # 算法若把 abstain/五音判定改坏测试仍可能全绿；此处用算法输出直接对 golden 验证。
    algo_abstain = (case["type"] != "conflict") and (primary is None)
    assert algo_abstain == g["abstain"], (
        f"{cid}: abstain 偏离 golden（golden={g['abstain']} 实算={algo_abstain}）")
    if case["type"] == "conflict":
        algo_tones = []
    elif primary is None:
        algo_tones = ["wellness_generic"]
    else:
        algo_tones = [ORGAN_TONE[primary]]
    assert algo_tones == g["tones"], (
        f"{cid}: tones 偏离 golden（golden={g['tones']} 实算={algo_tones}）")


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["case_id"])
def test_cases_jsonl_expected_matches_golden(case):
    """落盘的 expected 字段必须与硬编码 golden 一致（同一人工审核结果的两处落地）。"""
    cid = case["case_id"]
    g = GOLDEN[cid]
    exp = case["expected"]

    assert exp["primary_organ"] == g["primary"], f"{cid}: expected.primary_organ 与 golden 不一致"
    assert exp["secondary_organs"] == g["secondary"], f"{cid}: expected.secondary_organs 与 golden 不一致"
    assert exp["abstain"] == g["abstain"], f"{cid}: expected.abstain 与 golden 不一致"
    assert exp["expected_tones"] == g["tones"], f"{cid}: expected.expected_tones 与 golden 不一致"
    for org in ORGAN_ORDER:
        assert abs(exp["organ_net"][org] - g["organ_net"][org]) < 1e-6, (
            f"{cid}: expected.organ_net[{org}] 与 golden 不一致")
