"""Deterministic excerpts from clinical OCR, without inference or provider calls."""
from __future__ import annotations

import re


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
