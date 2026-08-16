# scaffold-installer Specification

## Purpose

Defines the scaffold script's subcommand interface, drift classification, and non-destructive install behavior.

## Requirements

### Requirement: Subcommand interface
The scaffold script SHALL expose four subcommands — `install`, `check`, `update`, and `list` — and SHALL run with no third-party TUI dependency.

#### Scenario: install runs the interactive picker
- **WHEN** the user runs `scaffold.py install`
- **THEN** the script walks each registered component and prompts install/update/skip per component

#### Scenario: check writes nothing
- **WHEN** the user runs `scaffold.py check`
- **THEN** the script reports each component's status and makes no changes to disk, the manifest, or installed plugins

#### Scenario: list reports status without prompting
- **WHEN** the user runs `scaffold.py list`
- **THEN** the script prints every registered component and its current status and exits without prompting

### Requirement: Drift classification
The script SHALL classify every component into exactly one of MISSING, STALE, MODIFIED, MODIFIED+STALE, or OK by comparing the on-disk state, the manifest, and the source.

#### Scenario: component absent
- **WHEN** a component has no entry in `.scaffold/manifest.json` and its tracked files are absent
- **THEN** the script classifies it MISSING and offers to install it

#### Scenario: source moved ahead
- **WHEN** an installed component's tracked files match its manifest hashes but the source ref has advanced past the installed source SHA
- **THEN** the script classifies it STALE and offers to update it

#### Scenario: local edits detected
- **WHEN** an installed component's tracked files no longer match their manifest hashes
- **THEN** the script classifies it MODIFIED and does not overwrite it without an explicit force flag

### Requirement: Non-destructive by default
The script SHALL never overwrite locally modified files or remove content without explicit confirmation.

#### Scenario: MODIFIED update requires force
- **WHEN** the user runs `scaffold.py update <component>` and that component is MODIFIED
- **THEN** the script refuses to overwrite unless `--force` is supplied, and otherwise reports the conflict and leaves files unchanged

#### Scenario: diff before overwrite
- **WHEN** the user is prompted to update a component during `install`
- **THEN** a `diff` option is offered that shows the unified diff between the on-disk file and the incoming version before any write

### Requirement: Per-component picker prompts
The `install` subcommand SHALL prompt for each component individually, showing its current status before asking for an action.

#### Scenario: present component is skippable
- **WHEN** a component is already OK during `install`
- **THEN** the script reports it current and moves on without rewriting it

### Requirement: OpenSpec-root precondition
The script SHALL treat `config-baseline`, `config-interview`, and `schema-clone` as requiring an initialized OpenSpec root. It SHALL determine initialization by running `openspec list --json` and requiring a non-null `.root`; a missing `openspec` CLI, a non-zero exit, or unparseable output SHALL be treated as not-initialized. When the root is absent, the script SHALL classify each such component BLOCKED and SHALL NOT create or write any file under `openspec/` for it.

#### Scenario: OpenSpec-dependent component blocked when root absent
- **WHEN** the user runs `scaffold.py install` in a project where `openspec list --json` reports a null `.root`
- **THEN** the script classifies `config-baseline`, `config-interview`, and `schema-clone` as BLOCKED, prints the remedy `openspec init . --tools claude`, does not write any file under `openspec/` for them, and does not run `openspec init`

#### Scenario: OpenSpec CLI unavailable is treated as not-initialized
- **WHEN** the `openspec` CLI is absent from `PATH` (or its `list --json` output cannot be parsed) during `install`
- **THEN** the script classifies the OpenSpec-dependent components BLOCKED and prints the init remedy rather than fabricating an `openspec/` tree

#### Scenario: OpenSpec-independent components install without a root
- **WHEN** the user runs `scaffold.py install` in a project with no OpenSpec root
- **THEN** `enforcement-hooks`, `cost-tracker`, `lint-gates`, plugin, and skill components are offered and installed normally, unaffected by the precondition

#### Scenario: components proceed when root present
- **WHEN** the user runs `scaffold.py install` in a project where `openspec list --json` reports a non-null `.root`
- **THEN** `config-baseline`, `config-interview`, and `schema-clone` follow their normal status and install flow

### Requirement: BLOCKED status is read-only in check and list
The `check` and `list` subcommands SHALL report a BLOCKED component's status without writing to disk, the manifest, or any external tool, distinguishing "precondition unmet" (BLOCKED) from "installable now" (MISSING).

#### Scenario: check reports BLOCKED without writing
- **WHEN** the user runs `scaffold.py check` in a project with no OpenSpec root
- **THEN** the OpenSpec-dependent components are reported BLOCKED and no changes are made to disk, the manifest, or installed tools

#### Scenario: list reports BLOCKED without prompting
- **WHEN** the user runs `scaffold.py list` in a project with no OpenSpec root
- **THEN** the OpenSpec-dependent components are printed with BLOCKED status and the script exits without prompting

### Requirement: update evaluates writer components
The `update` subcommand SHALL include writer components (those that derive local
project state instead of copying tracked files) in the set of components it
evaluates, rather than skipping them as install-only. The `update` subcommand
SHALL remain non-interactive and SHALL continue to exclude `filler` (interview)
and `printer` (advisory) components; only `writer` components are added to the
evaluated set. This lets an evolving scaffold propagate a newly-added writer
component (for example, `static-analysis`) into existing child projects through
`update` instead of only through `install`.

#### Scenario: writer component with unmet precondition reports BLOCKED during update
> **Tests:** tests/test_static_analysis_gates.py::test_update_writer_blocked_prints_remedy
- **GIVEN** a project whose inferred language requires an analyzer that is absent from PATH
- **WHEN** the user runs `scaffold.py update` (or `update static-analysis`)
- **THEN** the writer component is reported BLOCKED with its component-specific remedy and no gate is written to `.scaffold/gates.json`

#### Scenario: unsatisfied writer component runs its writer during update
> **Tests:** tests/test_static_analysis_gates.py::test_update_writer_registers_gates_when_ready
- **GIVEN** a project whose inferred language is supported, its analyzer is present on PATH, and its static-analysis gates are not yet registered
- **WHEN** the user runs `scaffold.py update`
- **THEN** the writer runs, the language's static-analysis gates are registered in `.scaffold/gates.json`, and the added gates are reported

#### Scenario: satisfied writer component is a no-op during update
> **Tests:** tests/test_static_analysis_gates.py::test_update_writer_already_registered_noop
- **GIVEN** a project whose writer component is already satisfied (its gates are all registered)
- **WHEN** the user runs `scaffold.py update`
- **THEN** the component is reported current and nothing is written to `.scaffold/gates.json`

#### Scenario: update leaves filler and printer components excluded
> **Tests:** tests/test_static_analysis_gates.py::test_update_still_excludes_filler_and_printer
- **GIVEN** a registry containing filler (interview) and printer (advisory) components
- **WHEN** the user runs `scaffold.py update`
- **THEN** those components are not evaluated by `update` and no interactive prompt is issued
