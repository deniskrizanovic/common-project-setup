# static-analysis-gates Specification

## Purpose

Defines the per-language static-analysis gates the scaffold registers into `.scaffold/gates.json` so `commit_gate.py` runs them alongside the existing test and lint gates.

## Requirements

### Requirement: Per-language static-analysis gate registration
The scaffold SHALL register per-language static-analysis gates into
`.scaffold/gates.json` so that `commit_gate.py` runs them alongside the
existing test and lint gates. The registered gate set SHALL depend on the
language read from the `Language / runtime:` answer in the project's
`openspec/config.yaml`:

- **Python** SHALL register `lint:ruff` running `ruff check`.
- **TypeScript** SHALL register `lint:biome` running `biome check` and
  `typecheck:tsc` running `tsc --noEmit`.
- **Salesforce** SHALL register `analyze:sf` running `sf code-analyzer run`.

Each registered gate SHALL carry its own `name` and its own `stopReason` so a
failing gate produces a precise, gate-specific block message.

#### Scenario: Python project registers the ruff gate
> **Tests:** tests/test_static_analysis_gates.py::test_python_registers_ruff_gate
- **GIVEN** a project whose `openspec/config.yaml` `Language / runtime:` answer resolves to Python and `ruff` is present on PATH
- **WHEN** the scaffold installs the static-analysis component
- **THEN** `.scaffold/gates.json` contains a `lint:ruff` gate running `ruff check` with its own `stopReason`

#### Scenario: TypeScript project registers the biome and tsc gates
> **Tests:** tests/test_static_analysis_gates.py::test_typescript_registers_biome_and_tsc
- **GIVEN** a project whose `Language / runtime:` answer resolves to TypeScript and `biome` and `tsc` are present on PATH
- **WHEN** the scaffold installs the static-analysis component
- **THEN** `.scaffold/gates.json` contains a `lint:biome` gate running `biome check` and a `typecheck:tsc` gate running `tsc --noEmit`, each with its own `stopReason`

#### Scenario: Salesforce project registers the code-analyzer gate
> **Tests:** tests/test_static_analysis_gates.py::test_salesforce_registers_sf_gate
- **GIVEN** a project whose `Language / runtime:` answer resolves to Salesforce and the `sf` CLI is present on PATH
- **WHEN** the scaffold installs the static-analysis component
- **THEN** `.scaffold/gates.json` contains an `analyze:sf` gate running `sf code-analyzer run` with its own `stopReason`

### Requirement: Language detection reads the `Language / runtime:` answer
The scaffold SHALL select static-analysis gates from the `Language / runtime:`
answer in the `context:` block of `openspec/config.yaml`. The scaffold SHALL NOT
use the `Testing:` answer for this selection (that answer names a test framework
and is ambiguous for Salesforce/Apex), and SHALL NOT introduce a separate
interview question for static-analysis language selection. When the
`Language / runtime:` answer matches no supported language, the scaffold SHALL
register no static-analysis gates and SHALL report that no gates were registered
rather than guessing a language.

#### Scenario: language taken from the config `Language / runtime:` answer
> **Tests:** tests/test_static_analysis_gates.py::test_detect_supported_languages
- **GIVEN** a project whose `openspec/config.yaml` `Language / runtime:` answer resolves to a supported language
- **WHEN** the scaffold selects static-analysis gates
- **THEN** it uses that answer and prompts for no additional language input

#### Scenario: unrecognized language registers nothing
> **Tests:** tests/test_static_analysis_gates.py::test_unsupported_language_registers_nothing
- **GIVEN** a project whose `openspec/config.yaml` `Language / runtime:` answer matches no supported language
- **WHEN** the scaffold installs the static-analysis component
- **THEN** no static-analysis gate is written to `.scaffold/gates.json` and the scaffold reports that none were registered

### Requirement: Missing toolchain classifies BLOCKED
The scaffold SHALL classify the static-analysis component **BLOCKED** when a
required analyzer for the inferred language is absent from PATH, SHALL print the
install remedy for the missing tool, and SHALL NOT write a gate that could only
fail. The scaffold SHALL NOT auto-install any analyzer toolchain. The `check`
and `list` commands SHALL report BLOCKED read-only and write nothing.

#### Scenario: absent analyzer blocks and is not registered
> **Tests:** tests/test_static_analysis_gates.py::test_install_blocked_prints_remedy_writes_nothing
- **GIVEN** a project whose inferred language requires an analyzer that is not present on PATH
- **WHEN** the scaffold installs the static-analysis component
- **THEN** the component classifies BLOCKED, the install remedy is printed, and no corresponding gate is written to `.scaffold/gates.json`

#### Scenario: scaffold never auto-installs a toolchain
> **Tests:** tests/test_static_analysis_gates.py::test_blocked_missing_tool_runs_no_install_command
- **GIVEN** a project whose inferred language requires an analyzer that is not present on PATH
- **WHEN** the scaffold runs against that project
- **THEN** the scaffold runs no install command for the analyzer and only prints the remedy

#### Scenario: check reports BLOCKED read-only
> **Tests:** tests/test_static_analysis_gates.py::test_check_reports_blocked_read_only
- **GIVEN** a project whose inferred analyzer is absent from PATH
- **WHEN** `check` or `list` is run
- **THEN** the component is reported BLOCKED and nothing is written

### Requirement: Tool defaults only, no templated config
The scaffold SHALL run each analyzer with its zero-config default and SHALL NOT
template a `ruff.toml`, `biome.json`, `code-analyzer.yml`, or equivalent
analyzer config file into the project. The registered gate command SHALL be the
analyzer's plain default invocation.

#### Scenario: no analyzer config file is written
> **Tests:** tests/test_static_analysis_gates.py::test_no_analyzer_config_file_written
- **GIVEN** a project receiving static-analysis gates for its inferred language
- **WHEN** the scaffold installs the static-analysis component
- **THEN** no analyzer configuration file is created and each gate command is the analyzer's default invocation
