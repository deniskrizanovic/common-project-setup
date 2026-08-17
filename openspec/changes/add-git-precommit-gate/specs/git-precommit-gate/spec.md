## ADDED Requirements

### Requirement: Native git pre-commit hook installation
The scaffold SHALL install a native git `pre-commit` hook so that commit gating
is enforced regardless of how the commit is made (terminal, IDE, or Claude Code
Bash tool). The hook SHALL be installed into a tracked hooks directory (default
`.githooks/`) and wired by setting the project's local `core.hooksPath` to that
directory, so the hook survives clones and is versioned with the project. The
scaffold SHALL NOT write directly into `.git/hooks/`.

#### Scenario: hook installed and core.hooksPath wired
> **Tests:** tests/test_git_precommit_gate.py::test_install_writes_hook_and_sets_hookspath
- **GIVEN** a git work tree with the scaffold's git-precommit-gate component being installed
- **WHEN** the scaffold installs the component
- **THEN** an executable `pre-commit` hook exists in the tracked hooks directory and the project's local `core.hooksPath` points at that directory

#### Scenario: hook runs from the terminal, not only through Claude Code
> **Tests:** tests/test_git_precommit_gate.py::test_hook_runs_gate_runner_on_commit
- **GIVEN** the git-precommit-gate hook is installed and `core.hooksPath` is set
- **WHEN** `git commit` is run from any client (terminal or IDE)
- **THEN** git invokes the tracked `pre-commit` hook, which runs the shared gate set

### Requirement: Pre-commit hook runs the shared gate set
The native `pre-commit` hook SHALL run the same gate set as the Claude Code
commit-gate: the gates in `.scaffold/gates.json` (tests, `lint:specs`,
`lint:given`, and the registered static-analysis gates) in the order they
appear in that file. On the first non-zero gate exit the hook SHALL abort the
commit with a non-zero status and surface that gate's `stopReason`. A gate whose
command is not found on PATH SHALL abort the commit with a gate-specific reason
rather than being silently skipped. The native hook and the Claude Code
commit-gate SHALL share `.scaffold/gates.json` as their single source of truth.

#### Scenario: failing gate aborts the commit
> **Tests:** tests/test_git_precommit_gate.py::test_hook_aborts_on_failing_gate
- **GIVEN** the pre-commit hook is installed and a registered gate exits non-zero
- **WHEN** `git commit` is run
- **THEN** the hook exits non-zero, aborting the commit, and surfaces that gate's `stopReason`

#### Scenario: missing gate command aborts the commit
> **Tests:** tests/test_git_precommit_gate.py::test_hook_aborts_on_missing_command
- **GIVEN** the pre-commit hook is installed and a registered gate's command is absent from PATH
- **WHEN** `git commit` is run
- **THEN** the hook exits non-zero with a gate-specific reason rather than skipping the gate

#### Scenario: all gates pass allows the commit
> **Tests:** tests/test_git_precommit_gate.py::test_hook_allows_when_gates_pass
- **GIVEN** the pre-commit hook is installed and every gate in `.scaffold/gates.json` passes
- **WHEN** `git commit` is run
- **THEN** the hook exits zero and the commit proceeds

### Requirement: Idempotent wiring that preserves foreign configuration
Wiring the git-precommit-gate SHALL be idempotent and SHALL preserve
configuration the scaffold did not author. Re-running the scaffold SHALL NOT
duplicate the hook or re-write an already-correct `core.hooksPath`. When
`core.hooksPath` is already set to a directory the scaffold did not author, the
scaffold SHALL report the conflict and SHALL NOT clobber the foreign value.

#### Scenario: re-run does not duplicate or clobber
> **Tests:** tests/test_git_precommit_gate.py::test_rerun_is_idempotent
- **GIVEN** the git-precommit-gate component is already installed and correctly wired
- **WHEN** the scaffold is run again
- **THEN** the hook is not duplicated, `core.hooksPath` is left in place, and nothing is re-written

#### Scenario: foreign core.hooksPath is not clobbered
> **Tests:** tests/test_git_precommit_gate.py::test_foreign_hookspath_reports_conflict
- **GIVEN** a project whose `core.hooksPath` already points at a directory the scaffold did not author
- **WHEN** the scaffold installs the git-precommit-gate component
- **THEN** the scaffold reports the conflict and does not overwrite the existing `core.hooksPath`

### Requirement: Non-git work tree classifies BLOCKED
The scaffold SHALL classify the git-precommit-gate component **BLOCKED** when
the project root is not inside a git work tree, SHALL print a remedy directing
the user to initialize git, and SHALL write nothing. The `check` and `list`
commands SHALL report BLOCKED read-only.

#### Scenario: absent git work tree blocks and writes nothing
> **Tests:** tests/test_git_precommit_gate.py::test_no_git_worktree_blocks_writes_nothing
- **GIVEN** a project root that is not inside a git work tree
- **WHEN** the scaffold installs the git-precommit-gate component
- **THEN** the component classifies BLOCKED, a remedy is printed, and no hook is written and no git config is set

#### Scenario: check reports BLOCKED read-only
> **Tests:** tests/test_git_precommit_gate.py::test_check_reports_blocked_read_only
- **GIVEN** a project root that is not inside a git work tree
- **WHEN** `check` or `list` is run
- **THEN** the component is reported BLOCKED and nothing is written
