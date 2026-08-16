## MODIFIED Requirements

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
