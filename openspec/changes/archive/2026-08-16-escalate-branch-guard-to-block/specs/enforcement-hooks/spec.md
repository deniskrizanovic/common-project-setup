## MODIFIED Requirements

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
