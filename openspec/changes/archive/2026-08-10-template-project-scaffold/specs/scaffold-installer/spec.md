## ADDED Requirements

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
