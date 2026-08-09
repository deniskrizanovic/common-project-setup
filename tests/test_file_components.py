"""Tests for config-baseline, enforcement-hooks, cost-tracker, and
spec-test-traceability specs.

empty-template flagged; branch-guard asks on main; commit-gate blocks on
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
    out = branch_guard.decision(branch)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
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
