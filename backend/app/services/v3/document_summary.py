"""Deterministic excerpts from clinical OCR, without inference or provider calls."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
import re


_SUMMARY_PREFIX = "资料中记录的近期状态："
_HISTORICAL_SUMMARY_PREFIX = "资料中记录的状态："
_ISO_RECORD_DATE = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
_ZH_RECORD_DATE = re.compile(r"(?<!\d)(\d{4})年(\d{1,2})月(\d{1,2})日?(?!\d)")

# A user-facing state summary must never present a diagnosis or a treatment
# instruction. Approved claim display names are state vocabulary only; this
# guard keeps that invariant enforced if the approved dictionary changes.
_FORBIDDEN_SUMMARY_TERMS = (
    "诊断", "证型", "治疗", "处理意见", "医嘱", "处方", "用药", "建议",
)


_SECTIONS = (
    "主诉", "现病史", "近期症状", "既往史", "四诊", "望闻问切", "体格检查",
    "查体", "舌象", "脉象", "中医诊断", "西医诊断", "初步诊断", "诊断",
    "辨证", "证候", "证型", "检查结果", "检验结果", "辅助检查", "异常结果",
    "治疗方案", "治疗", "处方", "处理建议", "处理", "医嘱", "建议",
)
_HEADING = re.compile(r"(?P<label>" + "|".join(_SECTIONS) + r")[：:]\s*")
_PRIVATE = re.compile(
    r"(?:患者姓名|姓名|患者|联系电话|手机号码|手机号|电话|身份证号?|身份证号码|"
    r"门诊号|住院号|就诊号|病案号|病历号|地址|签名|签字|医师|医生|印章|盖章)\s*[：:]"
)
_BRANDING = re.compile(r"医院|卫生院|卫生服务中心|检验中心|门诊病历|检验报告|检查报告|报告单|签名|签字|印章|盖章")
_CLINICAL = re.compile(r"痛|疲惫|乏力|不适|睡眠|入睡|食欲|咳嗽|发热|舌|脉|胸胁|精神不足|复查|偏高|偏低")


def document_time_context(
    text: str,
    *,
    today: date | None = None,
) -> tuple[str, date | None]:
    """Return document fact semantics and an explicit source record date.

    Only a valid date literally present in OCR may change the semantics. An
    old record is evidence about that recorded encounter, not an assertion
    about the user's current seven-day state.
    """

    reference_day = today or date.today()
    parsed: list[date] = []
    encounter_dates: list[date] = []
    non_encounter_date_seen = False
    for pattern in (_ISO_RECORD_DATE, _ZH_RECORD_DATE):
        for match in pattern.finditer(text or ""):
            # Date roles belong to the nearest field, not to the document's
            # latest calendar date. Printing/export metadata cannot date an
            # encounter. Keep unlabeled dates compatible, but never let them
            # override an explicitly labeled encounter.
            prefix = re.split(r"[\n\r；;。]", (text or "")[:match.start()])[-1]
            labels = list(re.finditer(r"([^：:，,]+)[：:]", prefix))
            label = labels[-1].group(1).strip() if labels else ""
            if re.search(r"打印|印制|导出|下载|出生|预约|复诊预约", label):
                non_encounter_date_seen = True
                continue
            try:
                candidate = date(*(int(part) for part in match.groups()))
            except ValueError:
                continue
            if candidate <= reference_day:
                parsed.append(candidate)
                if re.search(r"就诊|诊疗|入院|出院|就医", label):
                    encounter_dates.append(candidate)
    if encounter_dates:
        if len(set(encounter_dates)) > 1:
            return "source_recorded", None
        parsed = encounter_dates
    elif non_encounter_date_seen:
        # Mixed metadata without an explicit encounter date is ambiguous.
        parsed = []
    if not parsed:
        return "source_recorded", None
    if len(set(parsed)) > 1:
        return "source_recorded", None
    record_date = parsed[0]
    if record_date < reference_day - timedelta(days=7):
        return "source_recorded", record_date
    return "past_7_days", record_date


def summarize_documents(texts: list[str]) -> str:
    """Retain source wording in document order; labeled clinical text wins."""
    summaries = []
    for text in texts:
        sections: list[str] = []
        fallback: list[str] = []
        active = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # A new clinical label also terminates any preceding metadata.
            headings = list(_HEADING.finditer(line))
            if headings:
                for index, heading in enumerate(headings):
                    end = headings[index + 1].start() if index + 1 < len(headings) else len(line)
                    value = line[heading.end():end].strip()
                    private = _PRIVATE.search(value)
                    if private:
                        value = value[:private.start()].rstrip(" ，,；;")
                    if value and not _BRANDING.search(value) and not re.search(r"\d{11,}", value):
                        sections.append(f"{heading.group('label')}：{value}")
                active = True
            elif _PRIVATE.search(line) or _BRANDING.search(line) or re.search(r"\d{11,}", line):
                active = False
            elif line in _SECTIONS:
                active = True
            elif active:
                # Unknown fields delimit clinical sections; never copy their values.
                if re.search(r"[：:]", line):
                    active = False
                else:
                    sections.append(line)
            elif _CLINICAL.search(line) and not re.search(r"[：:]", line):
                fallback.append(line)
        excerpts = sections or fallback
        if excerpts:
            summaries.append("\n".join(dict.fromkeys(excerpts)))
    return "\n".join(summaries) or "材料中未识别到可整理的临床内容，请补充或编辑摘要。"


def summarize_facts(fact_dicts) -> str:
    """Compose a source-grounded recent-state summary from approved facts.

    Only the ``display_name`` of normalized facts is used, so the result cannot
    contain OCR wording, a diagnosis, a treatment instruction or any fact the
    approved claim dictionary does not define. Negated facts are skipped —
    listing an explicitly absent signal as present would misstate the source.
    Returns "" when nothing can be summarised, so callers keep the
    deterministic OCR excerpt as their fallback.
    """

    names: list[str] = []
    for fact in fact_dicts or ():
        if not isinstance(fact, Mapping):
            continue
        if fact.get("negated"):
            continue
        name = fact.get("display_name")
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name or name in names:
            continue
        if any(term in name for term in _FORBIDDEN_SUMMARY_TERMS):
            continue
        names.append(name)
    if not names:
        return ""
    historical = any(
        isinstance(fact, Mapping)
        and fact.get("time_window") == "source_recorded"
        for fact in fact_dicts or ()
    )
    prefix = _HISTORICAL_SUMMARY_PREFIX if historical else _SUMMARY_PREFIX
    return prefix + "、".join(names) + "。"
