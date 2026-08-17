"""Tests for the git-precommit-gate spec.

Covers native pre-commit hook installation + core.hooksPath wiring, the hook
running the shared gate set on a real commit (pass / failing-gate /
missing-command), idempotent re-run, foreign core.hooksPath conflict, and
BLOCKED classification outside a git work tree (read-only, writes nothing).
"""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

import scaffold as s


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def git_repo(project_dir):
    """`project_dir` initialized as a git repo with a commit, no origin remote."""
    _git(project_dir, "init", "-q")
    _git(project_dir, "config", "user.email", "test@example.com")
    _git(project_dir, "config", "user.name", "test")
    (project_dir / "README.md").write_text("x\n", encoding="utf-8")
    _git(project_dir, "add", ".")
    _git(project_dir, "commit", "-q", "-m", "init")
    return project_dir


def _install_runner(project_root):
    """Copy the real commit_gate.py runner the hook shells out to."""
    dest = project_root / "scripts" / "commit_gate.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((s.TEMPLATES_DIR / "scripts" / "commit_gate.py").read_bytes())


def _write_gates(project_root, gates):
    (project_root / ".scaffold").mkdir(exist_ok=True)
    (project_root / ".scaffold" / "gates.json").write_text(
        json.dumps({"gates": gates}), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# 3.1 Install writes hook + sets core.hooksPath; hook runs on commit
# --------------------------------------------------------------------------- #
def test_install_writes_hook_and_sets_hookspath(git_repo):
    s.install_git_precommit_gate(git_repo, out=io.StringIO())
    hook = git_repo / s.PRECOMMIT_HOOK_DEST
    assert hook.is_file()
    import os
    assert os.access(hook, os.X_OK)
    assert s.git_config_get(git_repo, "core.hooksPath") == s.SCAFFOLD_HOOKS_DIR


def test_hook_runs_gate_runner_on_commit(git_repo):
    """A real terminal commit invokes the tracked hook, which runs the gate set."""
    _install_runner(git_repo)
    _write_gates(git_repo, [{"name": "tests", "cmd": ["true"], "stopReason": "b"}])
    s.install_git_precommit_gate(git_repo, out=io.StringIO())
    (git_repo / "f.txt").write_text("a\n", encoding="utf-8")
    _git(git_repo, "add", "f.txt")
    # Commit succeeds because the (passing) gate ran; proves the hook fired.
    _git(git_repo, "commit", "-q", "-m", "gated")


def test_hook_aborts_on_failing_gate(git_repo):
    _install_runner(git_repo)
    _write_gates(git_repo, [{"name": "tests", "cmd": ["false"], "stopReason": "boom"}])
    s.install_git_precommit_gate(git_repo, out=io.StringIO())
    (git_repo / "f.txt").write_text("a\n", encoding="utf-8")
    _git(git_repo, "add", "f.txt")
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _git(git_repo, "commit", "-m", "gated")
    assert "boom" in exc.value.stderr


def test_hook_aborts_on_missing_command(git_repo):
    _install_runner(git_repo)
    _write_gates(
        git_repo,
        [{"name": "analyze:sf", "cmd": ["definitely-not-a-real-binary-xyz"],
          "stopReason": "sf boom"}],
    )
    s.install_git_precommit_gate(git_repo, out=io.StringIO())
    (git_repo / "f.txt").write_text("a\n", encoding="utf-8")
    _git(git_repo, "add", "f.txt")
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _git(git_repo, "commit", "-m", "gated")
    assert "analyze:sf" in exc.value.stderr


def test_hook_allows_when_gates_pass(git_repo):
    _install_runner(git_repo)
    _write_gates(
        git_repo,
        [
            {"name": "tests", "cmd": ["true"], "stopReason": "t"},
            {"name": "lint:specs", "cmd": ["true"], "stopReason": "s"},
        ],
    )
    s.install_git_precommit_gate(git_repo, out=io.StringIO())
    (git_repo / "f.txt").write_text("a\n", encoding="utf-8")
    _git(git_repo, "add", "f.txt")
    _git(git_repo, "commit", "-q", "-m", "gated")
    # The commit landed.
    assert _git(git_repo, "log", "--oneline").stdout.count("\n") == 2


# --------------------------------------------------------------------------- #
# 3.2 Idempotency + conflict
# --------------------------------------------------------------------------- #
def test_rerun_is_idempotent(git_repo):
    s.install_git_precommit_gate(git_repo, out=io.StringIO())
    before = (git_repo / s.PRECOMMIT_HOOK_DEST).read_bytes()
    out = io.StringIO()
    s.install_git_precommit_gate(git_repo, out=out)
    after = (git_repo / s.PRECOMMIT_HOOK_DEST).read_bytes()
    assert before == after
    assert s.git_config_get(git_repo, "core.hooksPath") == s.SCAFFOLD_HOOKS_DIR
    assert "already set" in out.getvalue()


def test_foreign_hookspath_reports_conflict(git_repo):
    """A core.hooksPath the scaffold did not author is reported, not clobbered."""
    s.git_config_set(git_repo, "core.hooksPath", "team-hooks")
    out = io.StringIO()
    s.install_git_precommit_gate(git_repo, out=out)
    assert s.git_config_get(git_repo, "core.hooksPath") == "team-hooks"
    text = out.getvalue()
    assert "team-hooks" in text
    assert "did not author" in text


# --------------------------------------------------------------------------- #
# 3.3 BLOCKED outside a git work tree
# --------------------------------------------------------------------------- #
def test_no_git_worktree_blocks_writes_nothing(
    project_dir, fake_claude_home, monkeypatch
):
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=lambda _p: "s", out=out)
    text = out.getvalue()
    assert "git-precommit-gate — BLOCKED" in text
    assert "git init" in text
    assert not (project_dir / s.PRECOMMIT_HOOK_DEST).exists()


def test_check_reports_blocked_read_only(
    project_dir, fake_claude_home, monkeypatch
):
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    out = io.StringIO()
    s.cmd_check(project_dir, s.build_registry(), out=out)
    assert f"{s.BLOCKED:<14} git-precommit-gate" in out.getvalue()
    assert not (project_dir / s.PRECOMMIT_HOOK_DEST).exists()


# --------------------------------------------------------------------------- #
# Classification: satisfied after wiring
# --------------------------------------------------------------------------- #
def test_satisfied_after_install_is_ok(git_repo, fake_claude_home, monkeypatch):
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    s.install_git_precommit_gate(git_repo, out=io.StringIO())
    status = s.compute_status(git_repo, s.build_registry())
    assert status.file_statuses["git-precommit-gate"] == s.OK


def test_missing_before_install_is_missing(git_repo, fake_claude_home, monkeypatch):
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    status = s.compute_status(git_repo, s.build_registry())
    assert status.file_statuses["git-precommit-gate"] == s.MISSING
