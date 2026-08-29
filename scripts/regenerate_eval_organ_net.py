"""重算 evals/sprint5/cases.jsonl 的 organ 期望值（统一 sum 语义）。

每个用例显式给出 Understanding 抽取出的 evidence（{claim_code: reliability}），
用 scripts/knowledge_organ_eval.py 的共享判定器计算 organ_net / 主脏 / 次脏 / 调式，
保证评估期望值永远与 organ-mapping-v3.0.json 的公式和阈值一致。

运行：python scripts/regenerate_eval_organ_net.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_organ_eval import load_organ_mapping, decide_candidates, ORGAN_ORDER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PATH = os.path.join(ROOT, "evals", "sprint5", "cases.jsonl")
FIVE_TONE_PATH = os.path.join(ROOT, "knowledge", "v3", "five-tone-mapping-v3.0.json")

ORGAN_TONE = {row["organ"]: row["tone"] for row in json.load(open(FIVE_TONE_PATH, encoding="utf-8"))["organ_tone_table"]}

# 9 个用例：input 沿用原样，evidence 为手写审核的 Understanding 抽取结果（reliability 按 scoring_spec）
CASES = [
    {
        "case_id": "V3_N001", "type": "normal", "coverage": "questionnaire+narrative",
        "input": {
            "questionnaire_answers": {"q01": 3, "q02": 1, "q03": 2, "q04": 1, "q05": 0, "q06": ["flank_discomfort", "tendon_stiffness"], "q07": ["none"], "q08": ["none"], "q09": ["none"], "q10": ["none"]},
            "narrative_text": "最近工作压力大，容易烦躁，两边肋骨下面总觉得闷闷的，身体也容易紧绷。",
            "document_text": "",
            "evidence": {"anger_tendency": 0.75, "agitation_tendency": 0.25, "overthinking_tendency": 0.5, "sadness_tendency": 0.25, "flank_discomfort": 1.0, "tendon_stiffness": 1.0},
        },
    },
    {
        "case_id": "V3_N002", "type": "normal", "coverage": "questionnaire+narrative",
        "input": {
            "questionnaire_answers": {"q01": 0, "q02": 0, "q03": 1, "q04": 3, "q05": 0, "q06": ["none"], "q07": ["none"], "q08": ["none"], "q09": ["throat_cough", "nasal_discomfort"], "q10": ["none"]},
            "narrative_text": "最近心情比较低落，总想叹气，还有点咳嗽，鼻子也不太通气。",
            "document_text": "",
            "evidence": {"overthinking_tendency": 0.25, "sadness_tendency": 0.75, "throat_cough": 1.0, "nasal_discomfort": 1.0},
        },
    },
    {
        "case_id": "V3_N003", "type": "normal", "coverage": "questionnaire+narrative",
        "input": {
            "questionnaire_answers": {"q01": 0, "q02": 0, "q03": 0, "q04": 0, "q05": 3, "q06": ["none"], "q07": ["none"], "q08": ["none"], "q09": ["none"], "q10": ["lower_back_knee_weakness", "nocturia"]},
            "narrative_text": "最近总觉得心里不踏实，晚上睡得也不好，腰和腿容易酸，夜里要起来上厕所。",
            "document_text": "",
            "evidence": {"fear_tendency": 0.75, "lower_back_knee_weakness": 1.0, "nocturia": 1.0, "sleep_disturbance": 0.6},
        },
    },
    {
        "case_id": "V3_I001", "type": "insufficient", "coverage": "questionnaire+narrative",
        "input": {
            "questionnaire_answers": {"q01": 0, "q02": 0, "q03": 0, "q04": 0, "q05": 0, "q06": ["none"], "q07": ["none"], "q08": ["none"], "q09": ["none"], "q10": ["none"]},
            "narrative_text": "最近没什么特别的感觉，一切正常。",
            "document_text": "",
            "evidence": {},
        },
    },
    {
        "case_id": "V3_I002", "type": "insufficient", "coverage": "questionnaire_only",
        "input": {
            "questionnaire_answers": {"q01": 1, "q02": 0, "q03": 0, "q04": 0, "q05": 0, "q06": ["none"], "q07": ["none"], "q08": ["none"], "q09": ["none"], "q10": ["none"]},
            "narrative_text": "",
            "document_text": "",
            "evidence": {"anger_tendency": 0.25},
        },
    },
    {
        "case_id": "V3_C001", "type": "conflict", "coverage": "conflict_detected",
        "input": {
            "questionnaire_answers": {"q01": 0, "q02": 0, "q03": 0, "q04": 3, "q05": 0, "q06": ["none"], "q07": ["none"], "q08": ["none"], "q09": ["none"], "q10": ["none"]},
            "narrative_text": "我心情其实挺好的，没有什么低落的感觉，就是最近有点累。",
            "document_text": "",
            "evidence": {"sadness_tendency": 0.75},
            "expected_conflicts": [{"topic": "low_mood", "questionnaire": "q04=3", "narrative": "心情挺好的"}],
        },
    },
    {
        "case_id": "V3_D001", "type": "doc_only", "coverage": "document_only",
        "input": {
            "questionnaire_answers": {},
            "narrative_text": "",
            "document_text": "本人自述：半年来经常胸闷，两侧肋骨胀痛，容易发脾气，睡眠欠佳，时有头晕。西医检查未见明显器质性病变。",
            "evidence": {"flank_discomfort": 0.7, "anger_tendency": 0.7, "sleep_disturbance": 0.7},
        },
    },
    {
        "case_id": "V3_D002", "type": "doc_only", "coverage": "document_only",
        "input": {
            "questionnaire_answers": {},
            "narrative_text": "",
            "document_text": "近期自觉乏力，吃饭没胃口，饭后腹胀，大便偏稀，白天犯困。",
            "evidence": {"poor_appetite": 0.7, "postmeal_bloating": 0.7, "loose_stool": 0.7, "low_energy": 0.7},
        },
    },
    {
        "case_id": "V3_Q001", "type": "q_only", "coverage": "questionnaire_only",
        "input": {
            "questionnaire_answers": {"q01": 0, "q02": 0, "q03": 4, "q04": 0, "q05": 0, "q06": ["none"], "q07": ["none"], "q08": ["poor_appetite", "postmeal_bloating"], "q09": ["none"], "q10": ["none"]},
            "narrative_text": "",
            "document_text": "",
            "evidence": {"overthinking_tendency": 1.0, "poor_appetite": 1.0, "postmeal_bloating": 1.0},
        },
    },
]


def round_net(scores):
    return {org: round(scores[org], 4) for org in ORGAN_ORDER}


def main():
    om = load_organ_mapping()
    lines = []
    for case in CASES:
        scores, primary, secondary, _ = decide_candidates(om, case["input"]["evidence"])
        is_conflict = case["type"] == "conflict"
        if is_conflict:
            # 冲突是 Understanding 层判定，非 abstain；不产生调式
            abstain = False
            tones = []
        elif primary is None:
            abstain = True
            tones = ["wellness_generic"]
        else:
            abstain = False
            tones = [ORGAN_TONE[primary]]

        expected = {
            "primary_organ": primary,
            "secondary_organs": secondary,
            "organ_net": round_net(scores),
            "safety_flags": [],
            "abstain": abstain,
            "expected_tones": tones,
            "coverage": case["coverage"],
        }
        if "expected_conflicts" in case["input"]:
            expected["expected_conflicts"] = case["input"].pop("expected_conflicts")

        out = {
            "case_id": case["case_id"],
            "type": case["type"],
            "input": case["input"],
            "expected": expected,
        }
        lines.append(json.dumps(out, ensure_ascii=False))

    with open(CASES_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✅ 已重写 {len(lines)} 个用例 -> {CASES_PATH}")
    print("\n新旧期望值对照：")
    print(f"{'case':<8} {'old_primary':<10} {'new_primary':<10} {'old_net':<22} {'new_net'}")
    old = {  # 原手写值，仅用于对照
        "V3_N001": ("liver", {"liver": 0.42, "spleen": 0.18, "heart": 0.11}),
        "V3_N002": ("lung", {"lung": 0.38, "liver": 0.06}),
        "V3_N003": ("kidney", {"kidney": 0.4, "heart": 0.1}),
        "V3_I001": (None, {"liver": 0.0}),
        "V3_I002": (None, {"liver": 0.055}),
        "V3_C001": (None, {"lung": 0.055}),
        "V3_D001": ("liver", {"liver": 0.45, "heart": 0.15}),
        "V3_D002": ("spleen", {"spleen": 0.5}),
        "V3_Q001": ("spleen", {"spleen": 0.32}),
    }
    for case in CASES:
        cid = case["case_id"]
        scores, primary, _, _ = decide_candidates(om, case["input"]["evidence"])
        o_p, o_net = old[cid]
        new_top = max(scores.values())
        print(f"{cid:<8} {str(o_p):<10} {str(primary):<10} {str(o_net):<22} {round(new_top, 4)}")


if __name__ == "__main__":
    main()
