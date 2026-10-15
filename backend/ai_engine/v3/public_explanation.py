"""Public wording over existing evidence/decisions, never a decision authority."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from backend.app.schemas.v3.assessment import FactEvidence, OrganEvidenceLink
from backend.app.schemas.v3.flow_v31 import OrganDominanceDecisionV1
from backend.app.services.v3.knowledge_assets import load_claim_dictionary


ORGAN_NAMES = {"liver": "肝", "heart": "心", "spleen": "脾", "lung": "肺", "kidney": "肾"}
GOAL_NAMES = {"sleep": "助眠", "relaxation": "放松", "emotion_regulation": "情绪调适",
              "focus": "专注", "energy": "提振精神", "stress_relief": "减压"}


@dataclass(frozen=True)
class PublicFact:
    evidence_id: str
    claim_code: str
    name: str
    time_window: str
    organs: tuple[str, ...]


def public_facts(
    evidence: Sequence[FactEvidence],
    links: Sequence[OrganEvidenceLink],
    *,
    excluded_ids: Sequence[str] = (),
    assessment_id: str | None = None,
    revision: int | None = None,
) -> tuple[PublicFact, ...]:
    """Consume canonical effective population, using approved display names only.

    Negation/subject exclusions are supplied by the DB owner. False/zero,
    contradicting, unconfirmed, stale and unresolved-conflict facts cannot be
    presented as positive reasons, even if their mapping links are positive.
    """

    _, dictionary = load_claim_dictionary()
    excluded = set(excluded_ids)
    result = []
    for item in sorted(evidence, key=lambda fact: (fact.claim_code, fact.fact_evidence_id)):
        claim = dictionary.get(item.claim_code)
        if (
            claim is None or not claim.organ_mapping_allowed
            or item.confirmation_status != "confirmed" or item.direction != "supporting"
            or item.fact_evidence_id in excluded or item.fact_id in excluded
            or (assessment_id is not None and item.assessment_id != assessment_id)
            or (revision is not None and item.assessment_revision != revision)
            or item.reliability <= 0 or not item.source_refs
        ):
            continue
        value = item.value.value
        if value is False or value in (0, "none", "unknown", "absent"):
            continue
        organs = tuple(sorted({link.organ.value for link in links
            if link.fact_evidence_id == item.fact_evidence_id
            and link.direction == "supporting" and link.link_strength > 0}))
        result.append(PublicFact(item.fact_evidence_id, item.claim_code,
                                 claim.display_name, item.time_window, organs))
    return tuple(result)


def describe(facts: Sequence[PublicFact]) -> str:
    """Bounded examples, with temporal scope attached to each group."""

    selected = list(facts[:3])
    groups: dict[str, list[str]] = {}
    for fact in selected:
        scope = ("资料记录中" if fact.time_window == "source_recorded"
                 else "近七天确认信息中" if fact.time_window == "past_7_days"
                 else "已确认记录中")
        groups.setdefault(scope, []).append(fact.name)
    return "；".join(f"{scope}的{'、'.join(names)}" for scope, names in groups.items())


def state_tendency(facts: Sequence[PublicFact]) -> str:
    if not facts:
        return "已确认资料中缺少可公开引用的正向状态依据。"
    return f"{describe(facts)}，是本次音乐调适可参考的状态信息。"


def direction_explanation(
    facts: Sequence[PublicFact], decision: OrganDominanceDecisionV1 | None,
    *, mode: str,
) -> tuple[str, list[str]]:
    if decision is not None and decision.regulation_mode == "personalized_five_tone":
        organ = decision.dominant_organ.value
        contributing = [fact for fact in facts if organ in fact.organs]
        if contributing:
            return (f"{describe(contributing[:2])}为{ORGAN_NAMES[organ]}相关音乐调适方向提供参考；"
                    "本次以这一已确定的主要方向安排音乐。",
                    [fact.evidence_id for fact in contributing[:2]])
        return "该主要调适方向缺少可公开引用的具体状态依据，暂不作进一步医学解释。", []
    reason = decision.decision_reason_code if decision is not None else ""
    if reason == "BASIC_EXACT_AUTHORITY_TIE":
        text = "确认资料支持多个并列方向，尚不能确定唯一主音；本次采用基础舒缓，不指定五音主音。"
    elif reason in {"BASIC_UNRESOLVED_DIRECT_CONTRADICTION", "BASIC_UNRESOLVED_MAJOR_CONFLICT"}:
        text = "确认资料中仍有影响主音选择的相反信息；本次采用基础舒缓，不指定五音主音。"
    elif mode == "integrated_regulation":
        text = "本次沿用已保存的综合调适方案，不突出单一五音主音。"
    elif mode == "personalized_five_tone":
        text = "已保存的主音方案缺少可公开引用的主导决策依据，暂不作进一步医学解释。"
    else:
        text = "确认资料对单一主音的依据不足；本次采用基础舒缓，不作五脏或五音主音判断。"
    return text, []


def parameter_explanations(*, spec, profile, rules, user_goal) -> dict[str, str | None]:
    """Verify the selected rule against the existing spec; never select parameters.

    Reuse the authority builder as a verifier. No rule payload, mismatching
    values/explanations, or default-only engineering copy => omit the reason.
    """

    from .agent3 import Agent3Blocked, _goal_codes, _selected_goal_rule, build_generation_spec_v31

    result: dict[str, str | None] = {"bpm": None, "instruments": None, "ambience": None}
    if not isinstance(rules, Mapping):
        return result
    try:
        expected = build_generation_spec_v31(profile=profile, parameter_rules=rules, user_goal=user_goal)
    except (Agent3Blocked, TypeError, ValueError):
        return result
    default = rules["default"]
    primary, secondary = _goal_codes(user_goal)
    goals = rules.get("goals")
    for field in result:
        if (getattr(spec, field) != getattr(expected, field)
            or spec.explanations.get(field) != expected.explanations.get(field)):
            continue
        value = getattr(spec, field)
        selected_goal = None
        for goal in (primary, secondary):
            row = _selected_goal_rule(goals, goal)
            if row is not None and row.get(field) is not None:
                # A same-as-default selection has no distinct goal rationale.
                if value != default.get(field) and goal in GOAL_NAMES:
                    selected_goal = GOAL_NAMES[goal]
                break
        if selected_goal is None:
            continue
        if field == "bpm":
            from .generation_design import derive_generation_design

            # Reuse the existing deterministic arrangement vocabulary, not
            # a new tempo/therapeutic rule or a claim about measured audio.
            energy = derive_generation_design(bpm=value, duration_seconds=spec.duration_seconds).energy_curve
            text = f"围绕本次{selected_goal}诉求，选择 {value} BPM，希望形成{energy}的音乐推进。"
        elif field == "instruments":
            # Main timbre is the existing public instrument role. Do not add
            # unsupported instrument-specific emotional/acoustic effects.
            text = f"围绕本次{selected_goal}诉求，采用{'、'.join(value)}作为主要音色，用于构成音乐主体，而非环境音背景。"
        elif all(name in {"无额外环境音", "none", "no_extra_ambience", "no-extra-ambience"} for name in value):
            text = f"本次调适诉求为{selected_goal}，采用不加入额外环境音层的选项。"
        else:
            text = f"本次调适诉求为{selected_goal}，加入对应的{'、'.join(value)}环境音层。"
            if value == ["微风"]:
                # Candidate D's approved atmosphere vocabulary is
                # 'gentle breeze ambience'; this describes intent only.
                text = f"围绕本次{selected_goal}诉求，加入微风作为背景环境音层，希望营造轻柔的微风氛围。"
        result[field] = text
    return result
