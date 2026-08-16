## ADDED Requirements

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
