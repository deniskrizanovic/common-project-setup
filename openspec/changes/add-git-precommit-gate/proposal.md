## Why

The commit-gate (tests + lint + static-analysis) runs only as a Claude Code `PreToolUse` hook, so it fires only when `git commit` goes through Claude Code's Bash tool. Commits from the terminal or an IDE (e.g. IntelliJ) bypass it entirely — a real project committed with no gate run at all. The static-analysis feature is only enforced for one commit path; it needs a native git gate that runs regardless of how the commit is made.

## What Changes

- Add a new scaffold component that installs a native git `pre-commit` hook, wired via `core.hooksPath` pointing at a tracked hooks directory (default `.githooks/`) so the gate survives clones and applies to terminal and IDE commits.
- The hook runs the same gate set as `commit_gate.py` — the gates in `.scaffold/gates.json` (tests, `lint:specs`, `lint:given`, and the registered static-analysis gates) in file order — so the native gate and the in-session Claude Code hook share one source of truth. On the first non-zero gate the hook blocks the commit and surfaces that gate's `stopReason`; a gate whose command is missing from PATH blocks rather than being skipped.
- Wiring is idempotent: re-running the scaffold does not duplicate the hook and preserves any pre-existing `core.hooksPath` / hook content it did not author (report a conflict rather than clobber a foreign `core.hooksPath`).
- Component classifies **BLOCKED** when not in a git work tree; `check`/`list` report read-only and write nothing, consistent with the existing static-analysis component.

## Capabilities

### New Capabilities
- `git-precommit-gate`: Installs and wires a native git `pre-commit` hook (via `core.hooksPath` + tracked hooks dir) that runs the `.scaffold/gates.json` gate set, so commit gating is enforced for all commit paths, not just Claude Code.

### Modified Capabilities
- `enforcement-hooks`: The commit-gate requirement expands from "Claude Code `PreToolUse` on `git commit`" to also cover a native git `pre-commit` path running the same gate set, and documents that the two share `.scaffold/gates.json`.

## Impact

- `scaffold.py`: new component in the registry (satisfied/precondition/writer), plus hook-directory wiring in `wire_hooks` or a dedicated writer.
- `templates/`: new tracked `pre-commit` hook script (shells the shared gate runner).
- Possible refactor of `commit_gate.py`'s `load_gates`/`run_gates` into a shared entry point the native hook can also invoke, avoiding a second gate-runner implementation.
- `openspec/specs/`: new `git-precommit-gate` spec; delta to `enforcement-hooks`.
- Projects consuming the scaffold gain a `core.hooksPath` git config setting and a tracked hooks directory.
