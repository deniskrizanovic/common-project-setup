"""Tests for config-baseline, enforcement-hooks, cost-tracker, and
spec-test-traceability specs.

empty-template flagged; branch-guard blocks on main; commit-gate blocks on
failing tests + allows on pass; idempotent re-wire adds no duplicates;
cost-tracker installed project-local with provenance stamp; missing
Tests:/GIVEN fails lint.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
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


lint_specs = _load("lint_specs", TEMPLATES / "scripts" / "lint_specs.py")
lint_given = _load("lint_given", TEMPLATES / "scripts" / "lint_given.py")
branch_guard = _load("branch_guard", TEMPLATES / "scripts" / "branch_guard.py")
commit_gate = _load("commit_gate", TEMPLATES / "scripts" / "commit_gate.py")


# --------------------------------------------------------------------------- #
# config-baseline
# --------------------------------------------------------------------------- #
def test_empty_template_flagged(project_dir):
    """The unmodified commented template counts as not satisfied."""
    cfg = project_dir / "openspec" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "schema: spec-driven\n\n# context: |\n#   Add your stack\n", encoding="utf-8"
    )
    assert s._config_is_real(project_dir) is False


def test_installed_config_is_real(project_dir):
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "config-baseline")
    manifest = s.read_manifest(project_dir)
    s.install_file_component(project_dir, comp, manifest, "sha")
    assert s._config_is_real(project_dir) is True
    # And classification flags MISSING for the empty template even with a
    # manifest entry present.
    (project_dir / "openspec" / "config.yaml").write_text(
        "schema: spec-driven\n# context: |\n", encoding="utf-8"
    )
    assert s.classify_file_component(project_dir, comp, manifest, "sha") == s.MISSING


# --------------------------------------------------------------------------- #
# enforcement-hooks: branch-guard
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("branch", ["main", "master"])
def test_branch_guard_asks_on_trunk(branch):
    # Trunk edits are blocked (deny), not one-tap approvable (ask).
    out = branch_guard.decision(branch)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert branch in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_branch_guard_silent_on_feature():
    assert branch_guard.decision("feature/x") is None


# --------------------------------------------------------------------------- #
# enforcement-hooks: commit-gate
# --------------------------------------------------------------------------- #
def test_commit_gate_ignores_non_commit(project_dir):
    assert commit_gate.evaluate(project_dir, {"command": "ls -la"}) is None


def test_commit_gate_blocks_on_failing_gate(project_dir):
    (project_dir / ".scaffold").mkdir()
    (project_dir / ".scaffold" / "gates.json").write_text(
        json.dumps(
            {"gates": [{"name": "tests", "cmd": ["false"], "stopReason": "boom"}]}
        ),
        encoding="utf-8",
    )
    result = commit_gate.evaluate(project_dir, {"command": "git commit -m x"})
    assert result == {"continue": False, "stopReason": "boom"}


def test_commit_gate_allows_on_pass(project_dir):
    (project_dir / ".scaffold").mkdir()
    (project_dir / ".scaffold" / "gates.json").write_text(
        json.dumps(
            {"gates": [{"name": "tests", "cmd": ["true"], "stopReason": "boom"}]}
        ),
        encoding="utf-8",
    )
    assert commit_gate.evaluate(project_dir, {"command": "git commit -m x"}) is None


# --------------------------------------------------------------------------- #
# enforcement-hooks: shared gate runner (run_all_gates)
# --------------------------------------------------------------------------- #
def _write_gates(project_dir, gates):
    (project_dir / ".scaffold").mkdir(exist_ok=True)
    (project_dir / ".scaffold" / "gates.json").write_text(
        json.dumps({"gates": gates}), encoding="utf-8"
    )


def test_run_all_gates_pass(project_dir):
    """All gates passing → None (both hooks share this runner)."""
    _write_gates(project_dir, [{"name": "tests", "cmd": ["true"], "stopReason": "b"}])
    assert commit_gate.run_all_gates(project_dir) is None


def test_run_all_gates_first_failing(project_dir):
    """The first non-zero gate's block is returned; later gates never run."""
    _write_gates(
        project_dir,
        [
            {"name": "tests", "cmd": ["false"], "stopReason": "tests boom"},
            {"name": "lint:specs", "cmd": ["true"], "stopReason": "specs boom"},
        ],
    )
    assert commit_gate.run_all_gates(project_dir) == {
        "continue": False,
        "stopReason": "tests boom",
    }


def test_run_all_gates_missing_command(project_dir):
    """A gate whose command is absent from PATH blocks (not silently skipped)."""
    _write_gates(
        project_dir,
        [{"name": "analyze:sf", "cmd": ["definitely-not-a-real-binary-xyz"],
          "stopReason": "sf boom"}],
    )
    result = commit_gate.run_all_gates(project_dir)
    assert result["continue"] is False
    assert "analyze:sf" in result["stopReason"]


# --------------------------------------------------------------------------- #
# enforcement-hooks: PreToolUse defers when the native git hook is wired
# --------------------------------------------------------------------------- #
def _wire_native_hook(project_dir):
    """Make native_hook_active() true: tracked hook file + core.hooksPath set."""
    hooks = project_dir / ".githooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-commit").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(project_dir), "init", "-q"], check=True,
        capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(project_dir), "config", "--local",
         "core.hooksPath", ".githooks"],
        check=True, capture_output=True, text=True,
    )


def test_evaluate_defers_when_native_hook_active(project_dir):
    """Native hook wired → PreToolUse returns None even for a FAILING gate.

    Proves the gate set does not run twice per in-session commit: the native
    git hook owns gating, so PreToolUse defers rather than re-running it."""
    _wire_native_hook(project_dir)
    _write_gates(project_dir, [{"name": "tests", "cmd": ["false"], "stopReason": "boom"}])
    assert commit_gate.evaluate(project_dir, {"command": "git commit -m x"}) is None


def test_evaluate_runs_when_native_hook_absent(project_dir):
    """No native hook → PreToolUse still gates (blocks a failing gate)."""
    _write_gates(project_dir, [{"name": "tests", "cmd": ["false"], "stopReason": "boom"}])
    assert commit_gate.evaluate(project_dir, {"command": "git commit -m x"}) == {
        "continue": False,
        "stopReason": "boom",
    }


def test_native_hook_active_false_without_hookspath(project_dir):
    """Hook file present but core.hooksPath unset → not active (would not fire)."""
    (project_dir / ".githooks").mkdir(exist_ok=True)
    (project_dir / ".githooks" / "pre-commit").write_text("x\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(project_dir), "init", "-q"], check=True,
        capture_output=True, text=True,
    )
    assert commit_gate.native_hook_active(project_dir) is False


# --------------------------------------------------------------------------- #
# enforcement-hooks: native git pre-commit mode (exit code)
# --------------------------------------------------------------------------- #
def test_native_main_pass_returns_zero(project_dir):
    _write_gates(project_dir, [{"name": "tests", "cmd": ["true"], "stopReason": "b"}])
    assert commit_gate.native_main(project_dir) == 0


def test_native_main_failing_gate_returns_nonzero(project_dir, capsys):
    _write_gates(project_dir, [{"name": "tests", "cmd": ["false"], "stopReason": "boom"}])
    assert commit_gate.native_main(project_dir) == 1
    assert "boom" in capsys.readouterr().err


def test_native_main_missing_command_returns_nonzero(project_dir, capsys):
    _write_gates(
        project_dir,
        [{"name": "analyze:sf", "cmd": ["definitely-not-a-real-binary-xyz"],
          "stopReason": "sf boom"}],
    )
    assert commit_gate.native_main(project_dir) == 1
    assert "analyze:sf" in capsys.readouterr().err


def test_main_native_flag_dispatches(project_dir):
    """`--native <dir>` runs the exit-code path, leaving JSON path for Claude Code."""
    _write_gates(project_dir, [{"name": "tests", "cmd": ["false"], "stopReason": "boom"}])
    assert commit_gate.main(["commit_gate.py", "--native", str(project_dir)]) == 1


# --------------------------------------------------------------------------- #
# enforcement-hooks: idempotent wiring
# --------------------------------------------------------------------------- #
def test_hook_wiring_idempotent(project_dir):
    s.wire_hooks(project_dir)
    settings_path = project_dir / ".claude" / "settings.json"
    first = json.loads(settings_path.read_text(encoding="utf-8"))
    s.wire_hooks(project_dir)
    second = json.loads(settings_path.read_text(encoding="utf-8"))
    assert first == second
    # Exactly one branch-guard command exists.
    pre = second["hooks"]["PreToolUse"]
    cmds = [h["command"] for g in pre for h in g["hooks"]]
    assert sum("branch_guard.py" in c for c in cmds) == 1


def test_hook_wiring_preserves_unrelated(project_dir):
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {"hooks": {"PreToolUse": [
                {"matcher": "Read", "hooks": [{"type": "command", "command": "echo keep"}]}
            ]}}
        ),
        encoding="utf-8",
    )
    s.wire_hooks(project_dir)
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    cmds = [h["command"] for g in settings["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert "echo keep" in cmds


# --------------------------------------------------------------------------- #
# cost-tracker
# --------------------------------------------------------------------------- #
def test_cost_tracker_project_local_with_provenance(project_dir):
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "cost-tracker")
    manifest = s.read_manifest(project_dir)
    s.install_file_component(project_dir, comp, manifest, "sha")
    tracker = project_dir / "tokencost" / "cost-tracker.py"
    provenance = project_dir / "tokencost" / ".provenance"
    assert tracker.is_file()
    assert provenance.is_file()
    assert "scaffold-component: cost-tracker" in provenance.read_text(encoding="utf-8")
    # Manifest entry records the component version (provenance).
    assert manifest["components"]["cost-tracker"]["version"] == comp.version
    # Installed project-local, not into the project's own ~/.claude hooks dir.
    assert not (project_dir / ".claude" / "hooks" / "cost-tracker.py").exists()


# --------------------------------------------------------------------------- #
# spec-test-traceability
# --------------------------------------------------------------------------- #
def test_missing_tests_line_fails_lint():
    content = "#### Scenario: does a thing\n- **GIVEN** state\n- **WHEN** x\n- **THEN** y\n"
    assert lint_specs.find_violations(content)


def test_tests_none_allowed():
    content = (
        "#### Scenario: does a thing\n> **Tests:** none\n"
        "- **GIVEN** state\n- **WHEN** x\n- **THEN** y\n"
    )
    assert not lint_specs.find_violations(content)


def test_absent_line_is_not_pass():
    """Silence (no citation, no `none`) is a violation, not a pass."""
    content = "#### Scenario: silent\n- **GIVEN** g\n- **WHEN** w\n- **THEN** t\n"
    violations = lint_specs.find_violations(content)
    assert len(violations) == 1


def test_missing_given_fails_lint():
    content = "#### Scenario: no given\n> **Tests:** none\n- **WHEN** x\n- **THEN** y\n"
    assert lint_given.find_violations(content)


def test_given_present_passes():
    content = (
        "#### Scenario: has given\n> **Tests:** none\n"
        "- **GIVEN** g\n- **WHEN** w\n- **THEN** t\n"
    )
    assert not lint_given.find_violations(content)


def test_lint_scans_change_deltas(tmp_path):
    """collect_spec_files picks up openspec/changes/*/specs deltas."""
    openspec = tmp_path / "openspec"
    delta = openspec / "changes" / "c1" / "specs" / "cap"
    delta.mkdir(parents=True)
    (delta / "spec.md").write_text("#### Scenario: x\n- **GIVEN** g\n", encoding="utf-8")
    files = lint_specs.collect_spec_files(openspec)
    assert any("spec.md" in str(f) for f in files)


# --------------------------------------------------------------------------- #
# spec-test-traceability: cited tests resolve to real tests
# --------------------------------------------------------------------------- #
def _discovered(func_names=(), paths=()):
    paths = set(paths)
    return {
        "func_names": set(func_names),
        "paths": paths,
        "basenames": {p.rsplit("/", 1)[-1] for p in paths},
        "stems": {p.rsplit("/", 1)[-1].rsplit(".", 1)[0] for p in paths},
    }


def test_resolution_nonexistent_identifier_fails():
    """A citation naming a test the suite does not contain is unresolved."""
    content = (
        "#### Scenario: cites missing test\n"
        "> **Tests:** `test_does_not_exist`\n"
        "- **GIVEN** g\n- **WHEN** w\n- **THEN** t\n"
    )
    result = lint_specs.analyze(content, _discovered(func_names={"test_real"}))
    assert len(result["unresolved"]) == 1
    assert result["unresolved"][0]["token"] == "test_does_not_exist"


def test_resolution_real_function_name_passes():
    """A citation matching a discovered test-function name resolves clean."""
    content = (
        "#### Scenario: cites real test\n"
        "> **Tests:** `test_query_follows_pagination`\n"
        "- **GIVEN** g\n- **WHEN** w\n- **THEN** t\n"
    )
    disc = _discovered(func_names={"test_query_follows_pagination"})
    result = lint_specs.analyze(content, disc)
    assert result["unresolved"] == []


def test_resolution_real_file_path_passes():
    """A file-path citation resolves against a discovered test file."""
    content = (
        "#### Scenario: cites real file\n"
        "> **Tests:** [`tests/test_notion.py`](../tests/test_notion.py)\n"
        "- **GIVEN** g\n- **WHEN** w\n- **THEN** t\n"
    )
    disc = _discovered(paths={"tests/test_notion.py"})
    result = lint_specs.analyze(content, disc)
    assert result["unresolved"] == []


def test_resolution_none_is_exempt():
    """The literal `none` is never resolved and never unresolved."""
    content = (
        "#### Scenario: untested\n> **Tests:** none\n"
        "- **GIVEN** g\n- **WHEN** w\n- **THEN** t\n"
    )
    result = lint_specs.analyze(content, _discovered())
    assert result["unresolved"] == []
    assert result["none_count"] == 1


# --------------------------------------------------------------------------- #
# spec-test-traceability: none accounting + threshold
# --------------------------------------------------------------------------- #
def test_none_count_reported():
    content = (
        "#### Scenario: a\n> **Tests:** none\n- **GIVEN** g\n"
        "#### Scenario: b\n> **Tests:** `test_x`\n- **GIVEN** g\n"
        "#### Scenario: c\n> **Tests:** none\n- **GIVEN** g\n"
    )
    result = lint_specs.analyze(content, _discovered(func_names={"test_x"}))
    assert result["none_count"] == 2
    assert result["total"] == 3


def test_none_threshold_exceeded_fails(tmp_path, capsys):
    """Configured threshold fails the gate when the none share exceeds it."""
    openspec = tmp_path / "openspec"
    spec = openspec / "specs" / "cap"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text(
        "#### Scenario: a\n> **Tests:** none\n- **GIVEN** g\n"
        "#### Scenario: b\n> **Tests:** none\n- **GIVEN** g\n",
        encoding="utf-8",
    )
    scaffold = tmp_path / ".scaffold"
    scaffold.mkdir()
    (scaffold / "gates.json").write_text(
        json.dumps({"noneShareThreshold": 0.5}), encoding="utf-8"
    )
    rc = lint_specs.main(["lint_specs.py", str(tmp_path)])
    assert rc == 1
    assert "threshold" in capsys.readouterr().err.lower()


def test_no_threshold_does_not_fail_on_none(tmp_path, capsys):
    """With no threshold configured, all-`none` specs still pass."""
    openspec = tmp_path / "openspec"
    spec = openspec / "specs" / "cap"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text(
        "#### Scenario: a\n> **Tests:** none\n- **GIVEN** g\n"
        "#### Scenario: b\n> **Tests:** none\n- **GIVEN** g\n",
        encoding="utf-8",
    )
    rc = lint_specs.main(["lint_specs.py", str(tmp_path)])
    assert rc == 0
    assert "2/2 cite 'none'" in capsys.readouterr().out


def test_read_none_threshold_nested_and_absent(tmp_path):
    assert lint_specs.read_none_threshold(tmp_path) is None
    scaffold = tmp_path / ".scaffold"
    scaffold.mkdir()
    (scaffold / "gates.json").write_text(
        json.dumps({"lint_specs": {"noneShareThreshold": 0.25}}), encoding="utf-8"
    )
    assert lint_specs.read_none_threshold(tmp_path) == 0.25


# --------------------------------------------------------------------------- #
# spec-test-traceability: test-technology mapping
# --------------------------------------------------------------------------- #
def test_discovery_follows_declared_technology(tmp_path):
    openspec = tmp_path / "openspec"
    openspec.mkdir(parents=True)
    (openspec / "config.yaml").write_text(
        "schema: spec-driven\ncontext: |\n  - Testing: pytest\n", encoding="utf-8"
    )
    answer = lint_specs.read_testing_answer(openspec)
    assert answer == "pytest"
    patterns, recognized = lint_specs.discovery_patterns(answer)
    assert recognized
    assert "**/test_*.py" in patterns["globs"]


def test_unrecognized_technology_falls_back(capsys):
    patterns, recognized = lint_specs.discovery_patterns("cobol-unit-thing")
    assert recognized is False
    assert patterns is lint_specs._DEFAULT_PATTERNS


def test_unrecognized_technology_logged(tmp_path, capsys):
    openspec = tmp_path / "openspec"
    spec = openspec / "specs" / "cap"
    spec.mkdir(parents=True)
    (openspec / "config.yaml").write_text(
        "schema: spec-driven\ncontext: |\n  - Testing: bespoke-runner\n",
        encoding="utf-8",
    )
    (spec / "spec.md").write_text(
        "#### Scenario: a\n> **Tests:** none\n- **GIVEN** g\n", encoding="utf-8"
    )
    lint_specs.main(["lint_specs.py", str(tmp_path)])
    assert "not recognized" in capsys.readouterr().err


def test_jest_test_titles_resolve(tmp_path):
    """jest/vitest `it('title')` names discover as function identifiers."""
    src = tmp_path / "sum.test.ts"
    src.write_text("it('adds numbers', () => {});\n", encoding="utf-8")
    patterns, _ = lint_specs.discovery_patterns("vitest")
    disc = lint_specs.discover_tests(tmp_path, patterns)
    assert "adds numbers" in disc["func_names"]
