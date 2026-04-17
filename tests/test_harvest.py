"""Tests for the session harvester."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from anchormd.analyzers.harvest import _normalize, _project_slug, harvest


def test_normalize_strips_paths_and_numbers() -> None:
    text = "File /home/me/project/foo.py not found (line 42, offset 1000)"
    sig = _normalize(text)
    assert "/home/me" not in sig
    assert "42" not in sig
    assert "1000" not in sig
    assert "File" in sig


def test_normalize_collapses_whitespace() -> None:
    assert _normalize("a    b\t\tc\n\nd") == "a b c d"


def _fake_jsonl(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events))


def _tool_use_event(tool_id: str, name: str, cwd: str) -> dict:
    return {
        "cwd": cwd,
        "message": {
            "content": [{"type": "tool_use", "id": tool_id, "name": name}],
        },
    }


def _tool_result_event(tool_id: str, error_text: str) -> dict:
    return {
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "is_error": True,
                    "content": error_text,
                }
            ],
        },
    }


def test_harvest_surfaces_recurring_errors(tmp_path: Path) -> None:
    project_path = tmp_path / "myproj"
    project_path.mkdir()
    transcripts = tmp_path / ".claude" / "projects" / _project_slug(project_path)
    transcripts.mkdir(parents=True)
    for i in range(3):
        session = transcripts / f"session{i}.jsonl"
        _fake_jsonl(
            session,
            [
                _tool_use_event(f"t{i}", "Edit", str(project_path)),
                _tool_result_event(f"t{i}", "File has not been read yet."),
            ],
        )

    with patch("anchormd.analyzers.harvest.Path.home", return_value=tmp_path):
        report = harvest(project_path, min_count=2)

    assert report.sessions_scanned == 3
    assert report.tool_errors == 3
    assert report.gotchas
    assert report.gotchas[0].tool == "Edit"
    assert report.gotchas[0].count == 3
    assert report.gotchas[0].sessions == 3


def test_harvest_respects_min_count(tmp_path: Path) -> None:
    project_path = tmp_path / "myproj"
    project_path.mkdir()
    transcripts = tmp_path / ".claude" / "projects" / _project_slug(project_path)
    transcripts.mkdir(parents=True)
    session = transcripts / "session.jsonl"
    _fake_jsonl(
        session,
        [
            _tool_use_event("t1", "Bash", str(project_path)),
            _tool_result_event("t1", "rare error"),
        ],
    )

    with patch("anchormd.analyzers.harvest.Path.home", return_value=tmp_path):
        report = harvest(project_path, min_count=2)

    assert report.gotchas == []


def test_harvest_no_transcripts(tmp_path: Path) -> None:
    project_path = tmp_path / "noproj"
    project_path.mkdir()
    with patch("anchormd.analyzers.harvest.Path.home", return_value=tmp_path):
        report = harvest(project_path)
    assert report.transcript_dir is None
    assert report.gotchas == []
