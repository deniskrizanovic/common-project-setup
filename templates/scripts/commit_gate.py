#!/usr/bin/env python3
"""Commit-gate runner shared by two paths.

Blocks `git commit` when the test suite or the configured lint gates fail.
Runs, in order:

  1. the project test command,
  2. `lint:specs`  (spec traceability gate),
  3. `lint:given`  (GIVEN-clause gate),
  4. the registered static-analysis gates (if any).

Two entry points share one runner (`load_gates`/`run_gates`), so the gate set
cannot drift between them:

  * Claude Code `PreToolUse` hook (default): reads the tool_input JSON from
    stdin, acts only on commands starting with `git commit`, and on the first
    failure emits `{"continue": false, "stopReason": ...}` to stdout. When the
    native git hook is wired (`core.hooksPath` -> `.githooks/` with the hook
    present) it defers — the native hook already gates every commit path, so
    running here too would run the whole gate set twice per in-session commit.
  * Native git `pre-commit` hook (`--native`): runs the gates directly (no
    stdin), and on the first failure prints the gate's `stopReason` to stderr
    and exits non-zero so git aborts the commit.

Gate commands are configured in `.scaffold/gates.json` if present, else default
to running the Python lint gates and `pytest`.

Provenance: scaffold components `enforcement-hooks` + `git-precommit-gate`.
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


# The scaffold's tracked hooks dir; mirrors scaffold.SCAFFOLD_HOOKS_DIR. When
# core.hooksPath points here and the hook file exists, the native git
# pre-commit hook runs the same gate set on every commit — so the PreToolUse
# path must NOT also run them (it would double-run tests + analyzers on each
# in-session commit). Kept as a literal to keep this script scaffold-free.
_SCAFFOLD_HOOKS_DIR = ".githooks"


def native_hook_active(project_dir: Path) -> bool:
    """True when the native git pre-commit gate is wired for this repo.

    Both halves must hold, mirroring the scaffold's satisfied() predicate: the
    tracked hook file exists AND project-local core.hooksPath points at it. When
    true the native hook owns gating for every commit path, so the PreToolUse
    hook defers to avoid running the full gate set twice per in-session commit."""
    hook = project_dir / _SCAFFOLD_HOOKS_DIR / "pre-commit"
    if not hook.is_file():
        return False
    try:
        out = subprocess.check_output(
            ["git", "-C", str(project_dir), "config", "--local",
             "--get", "core.hooksPath"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False
    return out == _SCAFFOLD_HOOKS_DIR


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
    if native_hook_active(project_dir):
        # Native git pre-commit hook owns gating for every commit path; running
        # here too would double-run the whole gate set on each in-session commit.
        return None
    return run_all_gates(project_dir)


def run_all_gates(project_dir: Path) -> dict | None:
    """Run the full gate set; None when all pass, else the failure block.

    The single shared entry point both hooks call: it loads `.scaffold/gates.json`
    (or the built-in defaults) and runs every gate in file order. Callers turn the
    returned `{continue: false, stopReason}` block into their own contract (JSON
    for Claude Code, non-zero exit for the native git hook)."""
    return run_gates(project_dir, load_gates(project_dir))


def native_main(project_dir: Path) -> int:
    """Native git `pre-commit` mode: exit non-zero on the first failing gate.

    Runs the shared gate set without touching stdin. `run_gates` already prints
    the failing gate's output to stderr; here we also print its `stopReason` and
    return 1 so git aborts the commit. All gates passing exits 0 (commit proceeds).
    """
    result = run_all_gates(project_dir)
    if result is not None:
        print(result["stopReason"], file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    native = False
    if args and args[0] == "--native":
        native = True
        args = args[1:]
    project_dir = Path(args[0]) if args else Path.cwd()

    if native:
        return native_main(project_dir)

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
