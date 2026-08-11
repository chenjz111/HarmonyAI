import subprocess
import sys
from pathlib import Path


def test_frozen_plan_direct_script_cli_starts_from_repository_root():
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "evals/run_sprint4_eval.py", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--cases" in completed.stdout
