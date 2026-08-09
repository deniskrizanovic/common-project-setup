## ADDED Requirements

### Requirement: Branch-guard hook
The scaffold SHALL install a `PreToolUse` hook that intercepts edits when the current git branch is `main` or `master`.

#### Scenario: edit on main is gated
- **WHEN** an Edit/Write/NotebookEdit is attempted while the current branch is `main` or `master`
- **THEN** the hook returns an `ask` permission decision naming the branch and requiring explicit approval to proceed

### Requirement: Commit-gate hook
The scaffold SHALL install a `PreToolUse` hook on `git commit` that blocks the commit when tests or the configured lint gates fail.

#### Scenario: failing tests block commit
- **WHEN** a `git commit` is attempted and the test suite fails
- **THEN** the hook stops the commit and surfaces the failing output as the stop reason

#### Scenario: passing gates allow commit
- **WHEN** a `git commit` is attempted and tests and lint gates pass
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
