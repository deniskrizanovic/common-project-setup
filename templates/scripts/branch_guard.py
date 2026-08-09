#!/usr/bin/env python3
"""Branch-guard PreToolUse hook.

Emits an `ask` permission decision when an Edit/Write/NotebookEdit is attempted
while the current git branch is `main` or `master`, so edits on the trunk
require explicit approval.

Provenance: scaffold component `enforcement-hooks`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def current_branch(project_dir: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(project_dir), "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def decision(branch: str) -> dict | None:
    """Ask JSON when on trunk, else None (no output = allow)."""
    if branch in ("main", "master"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"You are on branch {branch}. Never edit on main/master. "
                    "Approve to edit here anyway, or deny and create a feature "
                    "branch first."
                ),
            }
        }
    return None


def main(argv: list[str]) -> int:
    project_dir = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    out = decision(current_branch(project_dir))
    if out is not None:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
