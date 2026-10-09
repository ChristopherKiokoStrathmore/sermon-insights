import json
from pathlib import Path

import pytest

from sermon_insights.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_help_lists_stages(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    for name in ("run", "catalog", "captions", "transcribe", "detect", "scripture", "songs", "topics", "export"):
        assert name in text


def test_notebook_has_no_outputs_or_drive_ids():
    path = ROOT / "notebooks" / "colab_transcribe.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(notebook)
    assert "DRIVE_FILE_ID" not in blob
    assert "gdown" not in blob
    assert "float16" in blob
    assert "vad_filter" in blob
    assert "ctypes" in blob
    assert "condition_on_previous_text" in blob
    for cell in notebook["cells"]:
        assert cell.get("outputs", []) == []
        assert cell.get("execution_count") in (None,)
