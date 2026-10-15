"""R1/R2 audit -- stage availability against the published team baseline.

The baseline ``team/s7-m1-w2-baseline`` (``ff879f70``) now ships both stages:

* S1 ``backend/app/services/v3/evidence_admission.py``
* S12 ``backend/ai_engine/v3/public_explanation.py``  (note: under ``ai_engine/v3``,
  NOT ``services/v3`` -- this was a mis-lookup on the first pass)

This module records that the two stages are auditable and flips to a real smoke
check if either file is ever missing -- so the audit cannot silently pass with
a stage dropped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

STAGE_S1 = REPO_ROOT / "backend" / "app" / "services" / "v3" / "evidence_admission.py"
STAGE_S12 = REPO_ROOT / "backend" / "ai_engine" / "v3" / "public_explanation.py"


def test_stage_s1_admission_is_present() -> None:
    """Observed: the admission module is in the published baseline."""

    assert STAGE_S1.exists()
    from backend.app.services.v3.evidence_admission import (
        AdmissionFailure,
        admit_projection,
        checksum,
    )

    assert callable(admit_projection)
    assert callable(checksum)


def test_stage_s12_public_explanation_is_present() -> None:
    """Observed: the public-explanation module is in the published baseline."""

    assert STAGE_S12.exists()
    from backend.ai_engine.v3.public_explanation import (
        PublicFact,
        direction_explanation,
        public_facts,
        state_tendency,
    )

    assert callable(public_facts)
    assert callable(direction_explanation)
    assert callable(state_tendency)


def test_sprint7_docs_present_and_scope_not_fully_frozen() -> None:
    """Observed: the dev-baseline doc exists; the four R2-A drafts are NOT all frozen.

    The owner explicitly stated the baseline is a scoped dev package, not a full
    release and not a freeze of all four R2-A drafts. Only two of the four are
    present; this records exactly what the baseline actually ships.
    """

    docs = REPO_ROOT / "docs" / "sprint7"
    assert docs.exists()

    present = sorted(p.name for p in docs.glob("*.md"))
    assert "TEAM_BASELINE_DEVELOPMENT.md" in present

    expected_drafts = {
        "S7_TECHNICAL_CONTRACT_V1_DRAFT.md": False,
        "S7_M1_WORKSTREAM_PLAN.md": False,
        "S7_PRODUCT_ADDENDUM_V1_1.md": False,
        "S7_W2_IMPLEMENTATION_BOUNDARY.md": True,
    }
    for name, should_exist in expected_drafts.items():
        assert (docs / name).exists() is should_exist, name


def test_audit_package_imports_no_network_or_db_client() -> None:
    """Observed: the audit source itself stays offline.

    Checked by parsing the audit package's own imports rather than by watching
    ``sys.modules`` -- other test packages legitimately pull in ``httpx`` and
    SQLAlchemy, and their presence says nothing about this package.
    """

    import ast

    package_dir = Path(__file__).resolve().parent
    forbidden_prefixes = (
        "httpx", "requests", "aiohttp", "urllib.request", "socket",
        "openai", "anthropic", "chromadb", "sqlalchemy", "pymysql",
        "minimax", "dashscope",
    )

    offenders: list[str] = []
    for source_path in sorted(package_dir.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        offenders.append(f"{source_path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(forbidden_prefixes):
                    offenders.append(f"{source_path.name}: from {module} import ...")

    assert offenders == [], f"audit material must stay offline: {offenders}"
