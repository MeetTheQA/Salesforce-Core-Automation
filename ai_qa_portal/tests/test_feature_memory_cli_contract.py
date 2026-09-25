"""Contract tests for scripts/feature_memory/cli.py (no live server)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "scripts" / "feature_memory" / "cli.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("feature_memory_cli", CLI_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_help_lists_required_subcommands():
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    for name in (
        "status",
        "features",
        "memory",
        "review-queue",
        "match-rules",
        "stories",
        "seed-templates",
        "cases",
        "scripts",
        "runs",
        "orgs",
        "personas",
    ):
        assert name in out, f"missing subcommand in --help: {name}"


def test_stories_generate_help_mentions_grounded():
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "stories", "generate", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--story" in proc.stdout
    assert "--feature" in proc.stdout


def test_grounded_generate_flags_locked():
    cli = _load_cli()
    flags = cli.grounded_generate_flags()
    assert flags == {
        "context_mode": "feature_memory_only",
        "use_rag": False,
        "use_catalog": False,
    }
    assert cli.assert_grounded_flags(flags) == flags


def test_assert_grounded_flags_rejects_rag():
    cli = _load_cli()
    bad = cli.grounded_generate_flags()
    bad["use_rag"] = True
    with pytest.raises(ValueError, match="use_rag"):
        cli.assert_grounded_flags(bad)


def test_assert_grounded_flags_rejects_missing():
    cli = _load_cli()
    with pytest.raises(ValueError, match="missing"):
        cli.assert_grounded_flags({"context_mode": "feature_memory_only"})


def test_resolve_case_id_by_index():
    cli = _load_cli()
    cases = [
        {"id": "aaa-1", "title": "one"},
        {"id": "bbb-2", "title": "two"},
        {"id": "ccc-3", "title": "three"},
    ]
    assert cli.resolve_case_id(cases, index=3) == "ccc-3"
    assert cli.resolve_case_id(cases, case_id="bbb-2") == "bbb-2"


def test_resolve_case_id_rejects_zero_and_oob():
    cli = _load_cli()
    cases = [{"id": "aaa-1"}, {"id": "bbb-2"}]
    with pytest.raises(ValueError, match=">= 1"):
        cli.resolve_case_id(cases, index=0)
    with pytest.raises(ValueError, match="out of range"):
        cli.resolve_case_id(cases, index=3)
    with pytest.raises(ValueError, match="require --case"):
        cli.resolve_case_id(cases)


def test_number_cases_is_one_based():
    cli = _load_cli()
    numbered = cli.number_cases(
        [
            {"id": "a", "title": "t1", "status": "draft", "stale": False, "script_path": None},
            {"id": "b", "title": "t2", "status": "approved", "stale": False, "script_path": "x.robot"},
        ]
    )
    assert numbered[0]["index"] == 1
    assert numbered[1]["index"] == 2
    assert numbered[1]["script_path"] == "x.robot"
