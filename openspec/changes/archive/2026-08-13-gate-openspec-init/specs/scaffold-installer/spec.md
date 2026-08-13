## ADDED Requirements

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
