"""Structural checks for the canonical Sprint 4 JSON Schema fixture."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "assessment-v2.1.contract.json"


def load_contract() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_evidence_item_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(load_contract()["evidence_item_schema"])


def test_evidence_value_union_has_four_constrained_branches() -> None:
    branches = load_contract()["evidence_item_schema"]["properties"]["value"]["oneOf"]
    assert [branch["type"] for branch in branches] == ["integer", "string", "array", "object"]
    assert branches[0]["minimum"] == 0 and branches[0]["maximum"] == 4
    assert branches[2]["items"] == {"type": "string", "minLength": 1}
    assert branches[3]["additionalProperties"] is False


def test_coverage_and_source_diversity_are_separate_contract_fields() -> None:
    contract = load_contract()
    assert contract["evidence_coverage"]["source_diversity_affects_follow_up"] is False
    assert contract["source_diversity"]["semantics"] == "descriptive_only"
