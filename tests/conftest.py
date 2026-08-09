"""Test fixtures: throwaway project dir + fake ~/.claude, stub git + claude CLI.

Hermetic — no network, no real ~/.claude, no real git remote. A stub git source
repo is created on disk and used as the scaffold source; a stub `claude` CLI is
placed on a temp PATH so plugin install shells out to a no-op recorder.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def project_dir(tmp_path):
    """A throwaway project root."""
    root = tmp_path / "proj"
    root.mkdir()
    return root


@pytest.fixture
def fake_claude_home(tmp_path, monkeypatch):
    """A fake ~/.claude root with an empty installed_plugins.json."""
    home = tmp_path / "claude_home"
    (home / "plugins").mkdir(parents=True)
    (home / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_HOME", str(home))
    return home


@pytest.fixture
def stub_git_source(tmp_path):
    """A real local git repo used as the scaffold source ref.

    Returns (path, initial_sha). Commit more to advance the ref for STALE tests.
    """
    src = tmp_path / "source_repo"
    src.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(src), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (src / "README.md").write_text("scaffold source\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "initial")
    sha = git("rev-parse", "HEAD").stdout.strip()

    return src, sha


@pytest.fixture
def stub_claude_cli(tmp_path, monkeypatch):
    """Put a stub `claude` executable on PATH that records its invocations."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "claude_calls.log"
    script = bindir / "claude"
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{log}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return log


@pytest.fixture
def no_claude_cli(tmp_path, monkeypatch):
    """A PATH with no `claude` executable (CLI-absent scenario)."""
    bindir = tmp_path / "empty_bin"
    bindir.mkdir()
    monkeypatch.setenv("PATH", str(bindir))
    return bindir
