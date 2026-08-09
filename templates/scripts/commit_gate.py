#!/usr/bin/env python3
"""Commit-gate PreToolUse hook.

Blocks `git commit` when the test suite or the configured lint gates fail.
Reads the tool_input JSON from stdin (Claude Code PreToolUse contract); only
acts on commands starting with `git commit`. Runs, in order:

  1. the project test command,
  2. `lint:specs`  (spec traceability gate),
  3. `lint:given`  (GIVEN-clause gate),

and on the first failure emits `{"continue": false, "stopReason": ...}` with
the failing output on stderr. When everything passes it stays silent (allow).

Gate commands are configured in `tokencost/../.scaffold/gates.json` if present,
else default to running the Python lint gates and `pytest`.

Provenance: scaffold component `enforcement-hooks`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load_gates(project_dir: Path) -> list[dict]:
    """[{name, cmd, stopReason}] — from .scaffold/gates.json or defaults."""
    cfg = project_dir / ".scaffold" / "gates.json"
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            gates = data.get("gates")
            if isinstance(gates, list) and gates:
                return gates
        except (json.JSONDecodeError, OSError):
            pass
    scripts = "scripts"
    return [
        {
            "name": "tests",
            "cmd": ["pytest", "-q"],
            "stopReason": "Tests failed — fix all failing tests before committing.",
        },
        {
            "name": "lint:specs",
            "cmd": ["python3", f"{scripts}/lint_specs.py"],
            "stopReason": "lint:specs failed — every scenario needs a '> **Tests:**' line.",
        },
        {
            "name": "lint:given",
            "cmd": ["python3", f"{scripts}/lint_given.py"],
            "stopReason": "lint:given failed — every scenario needs a '- **GIVEN**' clause.",
        },
    ]


def is_git_commit(command: str) -> bool:
    return command.strip().startswith("git commit")


def run_gates(project_dir: Path, gates: list[dict]) -> dict | None:
    """None when all pass; else the {continue:false,...} block for the failure."""
    for gate in gates:
        try:
            proc = subprocess.run(
                gate["cmd"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            print(f"{gate['name']}: command not found: {e}", file=sys.stderr)
            return {
                "continue": False,
                "stopReason": f"{gate['name']} could not run: {e}",
            }
        if proc.returncode != 0:
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return {"continue": False, "stopReason": gate["stopReason"]}
    return None


def evaluate(project_dir: Path, tool_input: dict) -> dict | None:
    """Gate result for a PreToolUse tool_input, or None to allow."""
    command = tool_input.get("command", "")
    if not is_git_commit(command):
        return None
    return run_gates(project_dir, load_gates(project_dir))


def main(argv: list[str]) -> int:
    project_dir = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    result = evaluate(project_dir, tool_input)
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
