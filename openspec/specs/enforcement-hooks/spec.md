# enforcement-hooks Specification

## Purpose

Defines the PreToolUse and session hooks the scaffold installs to gate risky actions and record cost.

## Requirements

### Requirement: Branch-guard hook
The scaffold SHALL install a `PreToolUse` hook that intercepts edits when the current git branch is `main` or `master`. On `main`/`master` the hook SHALL return a `deny` permission decision (blocking the edit), not an `ask` decision. The decision reason SHALL name the branch and direct the user to create or switch to a feature branch, and SHALL note that editing trunk requires deliberately creating a branch or disabling the hook.

#### Scenario: edit on main is blocked
> **Tests:** tests/test_file_components.py::test_branch_guard_asks_on_trunk
- **GIVEN** the branch-guard hook is installed and the current branch is `main` or `master`
- **WHEN** an Edit/Write/NotebookEdit is attempted
- **THEN** the hook returns a `deny` permission decision naming the branch, blocking the edit rather than offering one-tap approval

#### Scenario: edit on a feature branch is allowed
> **Tests:** tests/test_file_components.py::test_branch_guard_silent_on_feature
- **GIVEN** the branch-guard hook is installed and the current branch is a non-trunk branch
- **WHEN** an Edit/Write/NotebookEdit is attempted
- **THEN** the hook emits no output and the edit proceeds

### Requirement: Commit-gate hook
The scaffold SHALL install a `PreToolUse` hook on `git commit` that blocks the
commit when tests, the configured lint gates, or the registered
static-analysis gates fail. The hook SHALL run the gates in the order they
appear in `.scaffold/gates.json`, with the static-analysis gates appended after
the existing `tests`, `lint:specs`, and `lint:given` gates. On the first
non-zero gate exit the hook SHALL stop the commit and surface that gate's
`stopReason`. A registered gate whose command is not found on PATH SHALL block
the commit with a gate-specific reason rather than being silently skipped.

#### Scenario: failing tests block commit
> **Tests:** tests/test_file_components.py::test_commit_gate_blocks_on_failing_gate
- **GIVEN** the commit-gate hook is installed and the test suite fails
- **WHEN** a `git commit` is attempted
- **THEN** the hook stops the commit and surfaces the failing output as the stop reason

#### Scenario: failing static-analysis gate blocks commit
> **Tests:** tests/test_static_analysis_gates.py::test_commit_gate_blocks_on_failing_static_gate
- **GIVEN** the commit-gate hook is installed and a registered static-analysis gate exits non-zero
- **WHEN** a `git commit` is attempted
- **THEN** the hook stops the commit and surfaces that gate's `stopReason`

#### Scenario: passing gates allow commit
> **Tests:** tests/test_file_components.py::test_commit_gate_allows_on_pass
- **GIVEN** the commit-gate hook is installed and tests, lint gates, and static-analysis gates all pass
- **WHEN** a `git commit` is attempted
- **THEN** the hook permits the commit

### Requirement: Cost-tracker hook
The scaffold SHALL install SessionStart and SessionEnd hooks that record per-session cost via the project-local cost-tracker.

#### Scenario: session end records a row
- **WHEN** a session ends
- **THEN** the SessionEnd hook upserts one row for that session into the project-local cost csv

### Requirement: Idempotent hook wiring
Hook wiring SHALL be idempotent and SHALL preserve unrelated existing hooks.

#### Scenario: re-run does not duplicate
- **WHEN** the hooks component is installed into a project that already has the same hook commands
- **THEN** the script leaves the existing entries in place and adds no duplicates
