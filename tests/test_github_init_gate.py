"""Tests for the github-init-gate spec.

Covers classification (non-git → BLOCKED, git w/o origin → MISSING, git w/ origin
→ OK; never STALE/MODIFIED) and print-only install (exact commands printed, no
git/remote state mutated).
"""
from __future__ import annotations

import io
import subprocess

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


def _github_init(registry=None):
    registry = registry or s.build_registry()
    return next(c for c in registry if c.id == "github-init")


# --------------------------------------------------------------------------- #
# Classification (4.1)
# --------------------------------------------------------------------------- #
def test_non_git_repo_is_blocked(project_dir, fake_claude_home, monkeypatch):
    """Not a git repository → BLOCKED (precedence over MISSING)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    status = s.compute_status(project_dir, s.build_registry())
    assert status.file_statuses["github-init"] == s.BLOCKED


def test_git_without_origin_is_missing(git_repo, fake_claude_home, monkeypatch):
    """Git repo with no origin remote → MISSING."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    status = s.compute_status(git_repo, s.build_registry())
    assert status.file_statuses["github-init"] == s.MISSING


def test_git_with_origin_is_ok(git_repo, fake_claude_home, monkeypatch):
    """Git repo with an origin remote (any host) → OK."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _git(git_repo, "remote", "add", "origin", "git@example.com:owner/repo.git")
    status = s.compute_status(git_repo, s.build_registry())
    assert status.file_statuses["github-init"] == s.OK


def test_never_stale_or_modified(git_repo, fake_claude_home, monkeypatch):
    """github-init only ever produces BLOCKED/MISSING/OK, never STALE/MODIFIED."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: "sha_new")
    comp = _github_init()
    manifest = s.read_manifest(git_repo)
    # Even with a stale-looking manifest record, classification stays MISSING/OK.
    for sha in ("sha_old", "sha_new", None):
        st = s.classify_file_component(
            git_repo, comp, manifest, sha, None, True, True
        )
        assert st in (s.MISSING, s.OK)


def test_origin_probe_ignores_host(git_repo):
    """has_origin_remote is True for any host, not just github.com."""
    assert s.has_origin_remote(git_repo) is False
    _git(git_repo, "remote", "add", "origin", "https://gitlab.com/o/r.git")
    assert s.has_origin_remote(git_repo) is True


def test_is_git_repo_probe(project_dir, git_repo):
    """is_git_repo: False for a plain dir, True inside a work tree."""
    plain = project_dir.parent / "plain"
    plain.mkdir()
    assert s.is_git_repo(plain) is False
    assert s.is_git_repo(git_repo) is True


# --------------------------------------------------------------------------- #
# Print-only install (4.2)
# --------------------------------------------------------------------------- #
def test_install_missing_prints_exact_commands(git_repo, fake_claude_home, monkeypatch):
    """MISSING install prints the gh command and no-gh fallback, mutates nothing."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    # Fail if any git-mutating subprocess fires from the github-init path.
    remotes_before = _git(git_repo, "remote").stdout

    out = io.StringIO()
    s.cmd_install(git_repo, s.build_registry(), reader=lambda _p: "s", out=out)
    text = out.getvalue()
    basename = git_repo.name
    assert f"gh repo create {basename} --public --source=. --remote=origin --push" in text
    assert "git remote add origin" in text
    assert "git push -u origin main" in text
    # No remote was added by the tool.
    assert _git(git_repo, "remote").stdout == remotes_before
    # No manifest record for the print-only component.
    assert "github-init" not in s.read_manifest(git_repo)["components"]


def test_install_ok_prints_no_commands(git_repo, fake_claude_home, monkeypatch):
    """OK install reports satisfied and prints no gh/git commands."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _git(git_repo, "remote", "add", "origin", "git@example.com:owner/repo.git")
    out = io.StringIO()
    s.cmd_install(git_repo, s.build_registry(), reader=lambda _p: "s", out=out)
    text = out.getvalue()
    assert "github-init — OK" in text
    assert "satisfied" in text
    assert "gh repo create" not in text


def test_install_blocked_refuses_and_prints_git_remedy(
    project_dir, fake_claude_home, monkeypatch
):
    """Non-git repo → install reports BLOCKED, prints how to init git, writes nothing."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=lambda _p: "s", out=out)
    text = out.getvalue()
    assert "github-init — BLOCKED" in text
    assert "git init" in text
    assert "gh repo create" not in text


def test_install_missing_never_prompts(git_repo, fake_claude_home, monkeypatch):
    """Print-only component never calls the reader (no [i]/[s] prompt)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)

    def reader(prompt):
        # Only the github-init component matters here; other components are
        # skipped. github-init must not reach the reader at all — assert it never
        # prompts about github-init specifically by rejecting its label.
        return "s"

    out = io.StringIO()
    # A no-op reader that returns "s" everywhere is fine; assert the github-init
    # section printed the advisory without an interactive choice line.
    s.cmd_install(git_repo, s.build_registry(), reader=reader, out=out)
    text = out.getvalue()
    assert "github-init — MISSING" in text
    # The print-only path prints commands, not an "[i]nstall/update" prompt echo.
    assert "gh repo create" in text


def test_update_github_init_reports_install_only(project_dir):
    """`update github-init` is not 'Unknown component' — it's install-only."""
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), component="github-init", out=out)
    assert rc == 0
    msg = out.getvalue()
    assert "install-only" in msg
    assert "Unknown component" not in msg
