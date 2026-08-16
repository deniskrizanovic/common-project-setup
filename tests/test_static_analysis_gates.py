"""Tests for the static-analysis-gates + enforcement-hooks (static gate) specs.

Covers language detection off `Language / runtime:`, per-language gate
registration (ruff / biome+tsc / sf) with distinct stopReasons, BLOCKED on a
missing toolchain (remedy printed, no gate written, no install run), idempotent
re-run, unsupported language registering nothing, tool-defaults-only (no config
file templated), and a failing static gate blocking the commit via commit_gate.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

import scaffold as s

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = REPO_ROOT / "templates"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


commit_gate = _load("commit_gate", TEMPLATES / "scripts" / "commit_gate.py")


def _write_config(project_dir: Path, language: str) -> None:
    """Write an openspec/config.yaml whose context block declares a language."""
    cfg = project_dir / "openspec" / "config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "schema: spec-driven\n"
        "context: |\n"
        "  Purpose: a thing\n"
        "\n"
        "  Tech stack:\n"
        f"  - Language / runtime: {language}\n"
        "  - Testing: pytest\n",
        encoding="utf-8",
    )


def _all_present(monkeypatch):
    """Treat every static-analysis tool as present on PATH."""
    monkeypatch.setattr(s.shutil, "which", lambda tool: f"/usr/bin/{tool}")


def _all_absent(monkeypatch):
    """Treat every tool as absent from PATH."""
    monkeypatch.setattr(s.shutil, "which", lambda tool: None)


# --------------------------------------------------------------------------- #
# 4.1 Language detection
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Python 3.12", "python"),
        ("TypeScript / Node 20", "typescript"),
        ("Node.js", "typescript"),
        ("Salesforce Apex / LWC", "salesforce"),
        ("Apex", "salesforce"),
        # Salesforce wins even when the answer also names a web language.
        ("Salesforce (LWC, JavaScript)", "salesforce"),
    ],
)
def test_detect_supported_languages(project_dir, answer, expected):
    """Each supported `Language / runtime:` answer resolves to its language."""
    _write_config(project_dir, answer)
    assert s.detect_language(project_dir) == expected


@pytest.mark.parametrize("answer", ["COBOL", "Rust", "Elixir/OTP"])
def test_detect_unrecognized_language_is_none(project_dir, answer):
    """An unrecognized answer resolves to None (no gates registered)."""
    _write_config(project_dir, answer)
    assert s.detect_language(project_dir) is None


def test_detect_absent_config_is_none(project_dir):
    """No config.yaml → no language."""
    assert s.detect_language(project_dir) is None


def test_language_read_from_context_block_only(project_dir):
    """The prompt label quoted outside the context block is not a false answer."""
    cfg = project_dir / "openspec" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    # `Language / runtime:` appears as prose above the block; the real block
    # declares Python.
    cfg.write_text(
        "# Language / runtime: mention in a comment\n"
        "schema: spec-driven\n"
        "context: |\n"
        "  Tech stack:\n"
        "  - Language / runtime: Python\n",
        encoding="utf-8",
    )
    assert s.detect_language(project_dir) == "python"


# --------------------------------------------------------------------------- #
# 4.2 Gate registration per language
# --------------------------------------------------------------------------- #
def _gates(project_dir):
    return json.loads(
        (project_dir / ".scaffold" / "gates.json").read_text(encoding="utf-8")
    )["gates"]


def test_python_registers_ruff_gate(project_dir, monkeypatch):
    _all_present(monkeypatch)
    _write_config(project_dir, "Python")
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    ruff = next(g for g in _gates(project_dir) if g["name"] == "lint:ruff")
    assert ruff["cmd"] == ["ruff", "check"]
    assert ruff["stopReason"]


def test_typescript_registers_biome_and_tsc(project_dir, monkeypatch):
    _all_present(monkeypatch)
    _write_config(project_dir, "TypeScript")
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    gates = {g["name"]: g for g in _gates(project_dir)}
    assert gates["lint:biome"]["cmd"] == ["biome", "check"]
    assert gates["typecheck:tsc"]["cmd"] == ["tsc", "--noEmit"]
    # Distinct stopReasons per gate.
    assert gates["lint:biome"]["stopReason"] != gates["typecheck:tsc"]["stopReason"]


def test_salesforce_registers_sf_gate(project_dir, monkeypatch):
    _all_present(monkeypatch)
    _write_config(project_dir, "Salesforce Apex")
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    sf = next(g for g in _gates(project_dir) if g["name"] == "analyze:sf")
    assert sf["cmd"] == ["sf", "code-analyzer", "run"]
    assert sf["stopReason"]


def test_static_gates_appended_after_base_gates(project_dir, monkeypatch):
    """Static gates land after the seeded tests / lint:specs / lint:given gates."""
    _all_present(monkeypatch)
    _write_config(project_dir, "Python")
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    names = [g["name"] for g in _gates(project_dir)]
    assert names == ["tests", "lint:specs", "lint:given", "lint:ruff"]


def test_static_gates_preserve_existing_gates(project_dir, monkeypatch):
    """A pre-existing gates array is extended, not replaced."""
    _all_present(monkeypatch)
    _write_config(project_dir, "Python")
    scaffold_dir = project_dir / ".scaffold"
    scaffold_dir.mkdir()
    (scaffold_dir / "gates.json").write_text(
        json.dumps(
            {
                "noneShareThreshold": 0.5,
                "gates": [{"name": "tests", "cmd": ["pytest"], "stopReason": "x"}],
            }
        ),
        encoding="utf-8",
    )
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    data = json.loads((scaffold_dir / "gates.json").read_text(encoding="utf-8"))
    # Sibling config key preserved; existing gate kept; ruff appended.
    assert data["noneShareThreshold"] == 0.5
    names = [g["name"] for g in data["gates"]]
    assert names == ["tests", "lint:ruff"]


# --------------------------------------------------------------------------- #
# 4.3 BLOCKED on missing toolchain
# --------------------------------------------------------------------------- #
def test_missing_tool_classifies_blocked(
    project_dir, fake_claude_home, monkeypatch
):
    """Absent analyzer → static-analysis BLOCKED (no gate written)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_absent(monkeypatch)
    _write_config(project_dir, "Python")
    status = s.compute_status(project_dir, s.build_registry())
    assert status.file_statuses["static-analysis"] == s.BLOCKED
    assert not (project_dir / ".scaffold" / "gates.json").exists()


def test_install_blocked_prints_remedy_writes_nothing(
    project_dir, fake_claude_home, monkeypatch
):
    """BLOCKED install prints the tool remedy and writes no gate."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_absent(monkeypatch)
    _write_config(project_dir, "Python")
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=lambda _p: "s", out=out)
    text = out.getvalue()
    assert "static-analysis — BLOCKED" in text
    assert "ruff" in text
    assert not (project_dir / ".scaffold" / "gates.json").exists()


def test_blocked_missing_tool_runs_no_install_command(
    project_dir, fake_claude_home, monkeypatch
):
    """The scaffold never shells out to install a missing analyzer."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_absent(monkeypatch)
    _write_config(project_dir, "TypeScript")

    # Record every subprocess.run argv; the git-repo probe legitimately shells
    # out, so assert only that no analyzer-install command was run.
    calls: list = []
    real_run = s.subprocess.run

    def recording_run(cmd, *a, **k):
        calls.append(cmd)
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(s.subprocess, "run", recording_run)
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=lambda _p: "s", out=out)
    assert "static-analysis — BLOCKED" in out.getvalue()
    install_markers = ("npm", "install", "biome", "typescript", "tsc", "pip", "uv")
    for cmd in calls:
        argv = cmd if isinstance(cmd, list) else [cmd]
        assert not any(m in str(tok) for tok in argv for m in install_markers), argv


def test_tsc_prefers_local_node_modules_bin(project_dir, monkeypatch):
    """A project-local node_modules/.bin/tsc satisfies the probe with no global tsc."""
    # tsc absent globally; biome present so only tsc's local resolution is tested.
    monkeypatch.setattr(
        s.shutil, "which", lambda tool: None if tool == "tsc" else f"/usr/bin/{tool}"
    )
    _write_config(project_dir, "TypeScript")
    # Without a local binary, tsc is missing.
    assert "tsc" in s.missing_static_tools(project_dir)
    local = project_dir / "node_modules" / ".bin" / "tsc"
    local.parent.mkdir(parents=True)
    local.write_text("#!/bin/sh\n", encoding="utf-8")
    assert "tsc" not in s.missing_static_tools(project_dir)


def test_check_reports_blocked_read_only(
    project_dir, fake_claude_home, monkeypatch
):
    """`check` reports static-analysis BLOCKED and writes nothing."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_absent(monkeypatch)
    _write_config(project_dir, "Python")
    out = io.StringIO()
    s.cmd_check(project_dir, s.build_registry(), out=out)
    assert f"{s.BLOCKED:<14} static-analysis" in out.getvalue()
    assert not (project_dir / ".scaffold" / "gates.json").exists()


# --------------------------------------------------------------------------- #
# 4.4 Idempotent re-run
# --------------------------------------------------------------------------- #
def test_reregister_adds_no_duplicates(project_dir, monkeypatch):
    """Re-running the writer adds no duplicate gates."""
    _all_present(monkeypatch)
    _write_config(project_dir, "TypeScript")
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    names = [g["name"] for g in _gates(project_dir)]
    assert names.count("lint:biome") == 1
    assert names.count("typecheck:tsc") == 1


def test_satisfied_after_registration_is_ok(
    project_dir, fake_claude_home, monkeypatch
):
    """Once registered, the component classifies OK (satisfied), not MISSING."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_present(monkeypatch)
    _write_config(project_dir, "Python")
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    status = s.compute_status(project_dir, s.build_registry())
    assert status.file_statuses["static-analysis"] == s.OK


# --------------------------------------------------------------------------- #
# Unsupported language registers nothing
# --------------------------------------------------------------------------- #
def test_unsupported_language_registers_nothing(project_dir, monkeypatch):
    """No supported language → no gate written, reported as such."""
    _all_present(monkeypatch)
    _write_config(project_dir, "COBOL")
    out = io.StringIO()
    s.register_static_analysis_gates(project_dir, out=out)
    assert "no supported" in out.getvalue().lower()
    assert not (project_dir / ".scaffold" / "gates.json").exists()


def test_unsupported_language_is_ok_not_missing(
    project_dir, fake_claude_home, monkeypatch
):
    """Unsupported language classifies OK (nothing to register), never BLOCKED."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_absent(monkeypatch)  # even with no tools, unsupported = nothing required
    _write_config(project_dir, "COBOL")
    status = s.compute_status(project_dir, s.build_registry())
    assert status.file_statuses["static-analysis"] == s.OK


# --------------------------------------------------------------------------- #
# Tool-defaults-only: no analyzer config file templated
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("language", ["Python", "TypeScript", "Salesforce"])
def test_no_analyzer_config_file_written(project_dir, monkeypatch, language):
    """Registration templates no ruff.toml / biome.json / code-analyzer.yml."""
    _all_present(monkeypatch)
    _write_config(project_dir, language)
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    for name in ("ruff.toml", "biome.json", "code-analyzer.yml", ".ruff.toml"):
        assert not (project_dir / name).exists()
    # Each registered gate command is the analyzer's plain default invocation.
    for gate in _gates(project_dir):
        if gate["name"] in ("lint:ruff", "lint:biome", "typecheck:tsc", "analyze:sf"):
            assert all("--config" not in tok for tok in gate["cmd"])


# --------------------------------------------------------------------------- #
# update evaluates the writer component (no longer install-only)
# --------------------------------------------------------------------------- #
def test_update_writer_blocked_prints_remedy(
    project_dir, fake_claude_home, monkeypatch
):
    """Python project, ruff absent → `update` reports BLOCKED + remedy, no gate."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_absent(monkeypatch)
    _write_config(project_dir, "Python")
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), out=out)
    assert rc == 0
    text = out.getvalue()
    assert f"static-analysis: {s.BLOCKED}" in text
    assert "ruff" in text
    assert not (project_dir / ".scaffold" / "gates.json").exists()


def test_update_writer_registers_gates_when_ready(
    project_dir, fake_claude_home, monkeypatch
):
    """Python project, ruff present, gates not registered → `update` runs writer."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_present(monkeypatch)
    _write_config(project_dir, "Python")
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), out=out)
    assert rc == 0
    names = [g["name"] for g in _gates(project_dir)]
    assert "lint:ruff" in names


def test_update_writer_already_registered_noop(
    project_dir, fake_claude_home, monkeypatch
):
    """Gates already registered → `update` reports current, writes nothing further."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_present(monkeypatch)
    _write_config(project_dir, "Python")
    s.register_static_analysis_gates(project_dir, out=io.StringIO())
    before = (project_dir / ".scaffold" / "gates.json").read_text(encoding="utf-8")
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), out=out)
    assert rc == 0
    assert "static-analysis: current" in out.getvalue()
    after = (project_dir / ".scaffold" / "gates.json").read_text(encoding="utf-8")
    assert before == after


def test_update_still_excludes_filler_and_printer(
    project_dir, fake_claude_home, monkeypatch
):
    """`update` evaluates no filler/printer component and issues no prompt."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _all_present(monkeypatch)
    _write_config(project_dir, "Python")

    def _no_input(_prompt=""):
        raise AssertionError("update must not prompt interactively")

    monkeypatch.setattr("builtins.input", _no_input)
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), out=out)
    assert rc == 0
    text = out.getvalue()
    # Filler (config-interview) and printer (github-init) are never evaluated.
    assert "config-interview" not in text
    assert "github-init" not in text


# --------------------------------------------------------------------------- #
# 4.5 Commit gate blocks on a failing static-analysis gate
# --------------------------------------------------------------------------- #
def test_commit_gate_blocks_on_failing_static_gate(project_dir):
    """A failing registered static gate blocks the commit with its stopReason."""
    (project_dir / ".scaffold").mkdir()
    (project_dir / ".scaffold" / "gates.json").write_text(
        json.dumps(
            {
                "gates": [
                    {"name": "tests", "cmd": ["true"], "stopReason": "t"},
                    {
                        "name": "lint:ruff",
                        "cmd": ["false"],
                        "stopReason": "lint:ruff failed — fix the findings.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    result = commit_gate.evaluate(project_dir, {"command": "git commit -m x"})
    assert result == {
        "continue": False,
        "stopReason": "lint:ruff failed — fix the findings.",
    }


def test_commit_gate_blocks_when_static_command_absent(project_dir):
    """A registered gate whose command is not on PATH blocks with its own reason."""
    (project_dir / ".scaffold").mkdir()
    (project_dir / ".scaffold" / "gates.json").write_text(
        json.dumps(
            {
                "gates": [
                    {
                        "name": "analyze:sf",
                        "cmd": ["definitely-not-a-real-binary-xyz"],
                        "stopReason": "analyze:sf failed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = commit_gate.evaluate(project_dir, {"command": "git commit -m x"})
    assert result["continue"] is False
    assert "analyze:sf" in result["stopReason"]
