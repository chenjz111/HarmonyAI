"""sprint5 评估集可执行性：cases.jsonl 的 expected 必须与共享评估器重算一致。

共享评估器是聚合公式的唯一事实来源（scripts/knowledge_organ_eval.py），
与 scripts/test_organ_mapping_boundaries.py 同源，杜绝公式分叉。
本测试让 evals/sprint5/cases.jsonl 真正可执行，防止期望值再次与资产漂移。
"""
import json
import os
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
OM = load_organ_mapping()


def _load_cases():
    """参数化用例在收集时加载。"""
    with open(CASES_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def cases():
    assert CASES_PATH.exists(), f"缺少评估集: {CASES_PATH}"
    with open(CASES_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_sprint5_cases_not_empty(cases):
    assert len(cases) >= 9, "sprint5 评估集应至少 9 个用例"


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["case_id"])
def test_eval_case_consistent(case):
    """每个用例：主脏/次脏/abstain/organ_net 与共享评估器一致。"""
    cid = case["case_id"]
    exp = case["expected"]
    evidence = case["input"].get("evidence", {})
    scores, primary, secondary, _ = decide_candidates(OM, evidence)

    if case["type"] != "conflict":
        assert exp["abstain"] == (primary is None), f"{cid}: abstain 与候选判定不一致"
        assert exp["primary_organ"] == primary, f"{cid}: primary_organ 不一致"
    else:
        assert primary is None, f"{cid}: 冲突用例不应有候选脏"
        assert exp["expected_tones"] == [], f"{cid}: 冲突用例不应有调式"

    assert exp["secondary_organs"] == list(secondary), f"{cid}: secondary_organs 不一致"

    for org in ORGAN_ORDER:
        assert abs(scores[org] - exp["organ_net"][org]) < 1e-6, (
            f"{cid}: organ_net[{org}] expected={exp['organ_net'][org]} 实算={round(scores[org], 6)}")
