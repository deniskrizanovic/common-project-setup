## 1. Shared gate runner

- [x] 1.1 Extract or expose a reusable gate-running entry point from `templates/scripts/commit_gate.py` (e.g. `run_all_gates(project_dir)`) that both the `PreToolUse` hook and the native hook can call, keeping `load_gates`/`run_gates` as the single implementation
- [x] 1.2 Add a CLI/exit-code mode to that entry point that runs the gates and returns non-zero + prints the failing gate's `stopReason` to stderr (for the native hook), leaving the existing JSON `{continue:false,...}` path unchanged for Claude Code
- [x] 1.3 Update tests for `commit_gate.py` to cover the new entry point (pass, first-failing-gate, missing-command all exercise the shared runner)

## 2. Tracked pre-commit hook template

- [x] 2.1 Add a tracked hook script under `templates/` (default target `.githooks/pre-commit`) that invokes the shared gate runner against the project root
- [x] 2.2 Ensure the hook is written executable and uses a `python3` shebang consistent with `commit_gate.py`

## 3. Scaffold component + wiring

- [x] 3.1 Add tests `tests/test_git_precommit_gate.py` for: hook written + `core.hooksPath` set (`test_install_writes_hook_and_sets_hookspath`), hook runs runner on commit (`test_hook_runs_gate_runner_on_commit`), failing gate aborts (`test_hook_aborts_on_failing_gate`), missing command aborts (`test_hook_aborts_on_missing_command`), passing gates allow (`test_hook_allows_when_gates_pass`)
- [x] 3.2 Add idempotency + conflict tests: `test_rerun_is_idempotent`, `test_foreign_hookspath_reports_conflict`
- [x] 3.3 Add BLOCKED tests: `test_no_git_worktree_blocks_writes_nothing`, `test_check_reports_blocked_read_only`
- [x] 3.4 Add the `git-precommit-gate` component to the scaffold registry with `satisfied()` (hook present + `core.hooksPath` correct), a precondition (`check`/remedy for "not a git work tree"), and a writer
- [x] 3.5 Implement the writer: write the tracked hook, then set project-local `core.hooksPath` only when unset or already the scaffold's dir; detect and report a foreign `core.hooksPath` without clobbering
- [x] 3.6 Wire the component into the idempotent install/update path alongside `wire_hooks`; ensure re-run adds no duplicate and does not re-write correct config

## 4. Spec + docs sync

- [x] 4.1 Run `pytest -q` and the lint gates (`lint:specs`, `lint:given`) green
- [x] 4.2 Update `README.md` to document the native git pre-commit gate and the one-time per-clone `core.hooksPath` activation
- [x] 4.3 Validate the change with `openspec validate --change add-git-precommit-gate` and confirm the enforcement-hooks delta archives cleanly
