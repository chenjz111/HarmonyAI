from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_mysql_acceptance_rejects_non_isolated_database_urls():
    from tools.s4_mysql_acceptance import validate_acceptance_database_url

    with pytest.raises(ValueError, match="MySQL"):
        validate_acceptance_database_url("sqlite:///harmonyai_s4_acceptance.db")

    with pytest.raises(ValueError, match="harmonyai_s4_acceptance"):
        validate_acceptance_database_url(
            "mysql+pymysql://tester:secret@127.0.0.1/harmonyai"
        )


def test_mysql_acceptance_accepts_only_the_named_isolated_database():
    from tools.s4_mysql_acceptance import validate_acceptance_database_url

    parsed = validate_acceptance_database_url(
        "mysql+pymysql://tester:secret@127.0.0.1:3306/harmonyai_s4_acceptance"
    )

    assert parsed.database == "harmonyai_s4_acceptance"
    assert parsed.drivername == "mysql+pymysql"


def test_mysql_acceptance_cli_refuses_sqlite_without_echoing_url():
    secret_marker = "S4_DB_SECRET_MUST_NOT_APPEAR"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{secret_marker}.db"

    completed = subprocess.run(
        ["python", "-m", "tools.s4_mysql_acceptance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 2
    assert secret_marker not in output
    assert "MySQL" in output


def test_manual_start_check_does_not_echo_database_credentials():
    script = ROOT / "tools" / "start-s4-manual-acceptance.ps1"
    env = os.environ.copy()
    secret_marker = "S4_SECRET_MUST_NOT_APPEAR"
    env["DATABASE_URL"] = (
        "mysql+pymysql://acceptance:" + secret_marker
        + "@127.0.0.1:3306/harmonyai_s4_acceptance"
    )

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-CheckOnly",
            "-LanIp",
            "192.0.2.10",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert secret_marker not in output
    assert "http://192.0.2.10:8000" in output
    assert "DATABASE_URL: SET" in output
