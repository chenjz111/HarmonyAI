"""Pytest fixtures for the Sprint 7 R1/R2 evidence counterfactual audit.

Scope (Issue #154, status ``BLOCKED_BY_TEAM_BASELINE``)
------------------------------------------------------
* This package is **audit material only**. It never modifies a production
  algorithm, a rule asset, a GenerationSpec, a provider or a production
  schema -- it only calls them.
* ``backend/app/services/v3/evidence_admission.py`` and
  ``backend/app/services/v3/public_explanation.py`` do **not exist in the
  published tree**. Stage ``S1`` (admission) and ``S12`` (public Explanation)
  are therefore ``NOT RUN`` here; see ``README.md``.
* Zero provider / network / production-DB access. Every case is built from the
  approved JSON assets under ``knowledge/v3`` plus pure functions.
"""

from __future__ import annotations

import pytest

from tests.sprint7_audit.harness import AuditAssets, load_audit_assets


@pytest.fixture(scope="session")
def assets() -> AuditAssets:
    """The three approved assets plus their verified identity."""

    return load_audit_assets()


@pytest.fixture(scope="session")
def mapping(assets: AuditAssets) -> dict:
    return assets.mapping


@pytest.fixture(scope="session")
def five_tone(assets: AuditAssets) -> dict:
    return assets.five_tone


@pytest.fixture(scope="session")
def dominance_rule(assets: AuditAssets) -> dict:
    return assets.dominance_rule
