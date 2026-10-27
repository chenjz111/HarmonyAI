import runpy
import sys
from pathlib import Path
import pytest


def test_frozen_plan_direct_script_cli_starts_from_repository_root(monkeypatch,capsys):
    root = Path(__file__).resolve().parents[2]
    # Exercise the real __main__ entrypoint under the SAME offline Guard.
    # A nested subprocess is forbidden by that Guard.
    # No provider work happens for --help; existing exit/options assertions stay.
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys,'argv',['evals/run_sprint4_eval.py','--help'])
    monkeypatch.setattr(sys,'path',[str(root/'evals'),*[p for p in sys.path if Path(p or '.').resolve()!=root]])
    with pytest.raises(SystemExit) as completed:
        runpy.run_path(str(root/'evals/run_sprint4_eval.py'),run_name='__main__')
    output=capsys.readouterr()
    assert completed.value.code == 0, output.err
    assert '--cases' in output.out
