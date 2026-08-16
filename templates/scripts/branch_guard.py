#!/usr/bin/env python3
"""Branch-guard PreToolUse hook.

Emits a `deny` permission decision when an Edit/Write/NotebookEdit is attempted
while the current git branch is `main` or `master`, blocking edits on the trunk
so they require a deliberate branch or hook bypass rather than one-tap approval.

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
    """Deny JSON when on trunk, else None (no output = allow)."""
    if branch in ("main", "master"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"You are on branch {branch}. Editing the trunk is blocked. "
                    "Create or switch to a feature branch, then retry. If you "
                    "truly intend to edit trunk, deliberately create a branch or "
                    "disable this hook first."
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
