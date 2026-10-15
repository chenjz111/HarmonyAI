"""Internal pragmatic admission audit, never a claim of full semantic proof.

Source presence and span bounds are eligibility checks, not semantic entailment.
Only narrowly recognizable contradictions are blocked here. Other interpretation
uncertainty is explicitly retained for audit under the Owner-approved contract.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re


class AdmissionFailure(ValueError):
    pass


def checksum(text):
    return "sha256:" + sha256(text.strip().encode("utf-8")).hexdigest()


def admit_projection(facts, *, sources, summary):
    admitted, candidates = [], []
    for original in facts:
        fact = deepcopy(original)
        if fact["confirmation_status"] == "rejected":
            admitted.append(fact)
            continue
        checks = ["source_binding", "span_bounds", "time_context"]
        uncertainties = ["AI_SEMANTIC_INTERPRETATION_NOT_FULLY_VERIFIED"]
        refs = fact.get("source_refs") or []
        label = str(fact["display_name"]).removesuffix("倾向")
        for clause in re.split(r"[。；;\n]", summary):
            if clause.strip() == label and fact["negated"]:
                raise AdmissionFailure("EXPLICIT_CURRENT_CORRECTION")
            if re.fullmatch(r"(?:否认|没有|无)(?:明显)?" + re.escape(label), clause.strip()):
                checks.append("explicit_summary_correction")
                if not fact["negated"]:
                    raise AdmissionFailure("EXPLICIT_CURRENT_CORRECTION")
        if not refs:
            raise AdmissionFailure("SOURCE_REQUIRED")
        spans, hashes = [], []
        for ref in refs:
            source = sources.get(ref["source_id"])
            if not source or source["kind"] != ref["source_type"]:
                raise AdmissionFailure("SOURCE_MISMATCH")
            if fact["time_window"] != source["time_window"]:
                raise AdmissionFailure("TIME_CONTEXT_MISMATCH")
            try:
                span = json.loads(ref.get("span_ref") or "null")
                start, end = span["start"], span["end"]
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source["text"]):
                    raise ValueError()
            except (ValueError, TypeError, KeyError):
                raise AdmissionFailure("SOURCE_SPAN_REQUIRED") from None
            spans.append({"source_id": ref["source_id"], "start": start, "end": end})
            hashes.append(checksum(source["text"]))
            # Narrow literal clauses only. No alias discovery, substring-based
            # positive authorization, medical causality or conflict scoring.
            clauses = re.split(r"[。；;\n]", source["text"])
            for clause in clauses:
                clause = clause.strip()
                if clause == label and fact["negated"]:
                    raise AdmissionFailure("EXPLICIT_POLARITY_MISMATCH")
                if re.fullmatch(r"(?:否认|没有|无)(?:明显)?" + re.escape(label), clause):
                    checks.append("literal_negation")
                    if not fact["negated"]:
                        raise AdmissionFailure("EXPLICIT_NEGATION_REVERSAL")
                if re.fullmatch(r"(?:母亲|父亲|家属)(?:有|出现)?" + re.escape(label), clause):
                    checks.append("literal_subject")
                    if fact["subject"] == "self":
                        raise AdmissionFailure("EXPLICIT_SUBJECT_MISMATCH")
                for word, value in (("轻度", "mild"), ("中度", "moderate"), ("重度", "severe")):
                    if re.fullmatch(word + re.escape(label), clause):
                        checks.append("literal_severity")
                        if fact["value"]["value"] != value:
                            raise AdmissionFailure("EXPLICIT_VALUE_MISMATCH")
        fact["confirmation_status"] = "confirmed"
        admitted.append(fact)
        candidates.append({"fact_id": fact["fact_id"], "admission_actor": "system",
            "admission_basis": "pragmatic_ai_evidence_contract_v1",
            "source_refs": refs, "source_span": spans, "source_checksums": hashes,
            "checks_performed": sorted(set(checks)), "uncertainty_flags": uncertainties,
            "disposition": "admitted", "reason_codes": []})
    if not candidates:
        raise AdmissionFailure("EMPTY_ADMITTED_PROJECTION")
    return admitted, candidates
