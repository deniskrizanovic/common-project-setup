## MODIFIED Requirements

### Requirement: Three-layer scenario enforcement
The scaffold SHALL enforce that every spec scenario carries a `> **Tests:**` line and a `- **GIVEN**` clause at three layers: the schema instruction (author-time), a lint gate, and the commit-gate hook. The `> **Tests:**` line SHALL cite either the literal word `none` or one or more concrete test identifiers, and a cited identifier SHALL resolve to a test that exists in the project's test suite.

#### Scenario: schema instruction directs authors
> **Tests:** none
- **GIVEN** a project into which the traceability component is being installed
- **WHEN** the component is installed
- **THEN** the project's `specs` schema instruction requires a `> **Tests:**` line and a `- **GIVEN**` clause on every `#### Scenario:`, and directs authors to cite the concrete test identifier once the test exists rather than leaving `none`

#### Scenario: missing test line fails lint
> **Tests:** `test_missing_tests_line_fails_lint`, `test_absent_line_is_not_pass`
- **GIVEN** a spec scenario in a scanned file
- **WHEN** the scenario lacks a `> **Tests:**` line as its first non-empty following line
- **THEN** the `lint:specs` gate fails

#### Scenario: missing given clause fails lint
> **Tests:** `test_missing_given_fails_lint`
- **GIVEN** a spec scenario in a scanned file
- **WHEN** the scenario lacks a `- **GIVEN**` clause
- **THEN** the `lint:given` gate fails

## ADDED Requirements

### Requirement: Cited tests SHALL resolve to real tests
The `lint:specs` gate SHALL verify that every non-`none` test identifier on a `> **Tests:**` line resolves to a test that exists in the project's test suite. When a cited identifier cannot be resolved, the gate SHALL fail and name the offending scenario, file, line, and unresolved identifier. Resolution SHALL scan the project's test source and match by test-function name or file path, and SHALL remain pure-filesystem and offline: it reads test source, it does not execute the suite.

The set of files and identifier patterns scanned SHALL be derived from the project's declared test technology rather than hard-coded. The gate SHALL read the `Testing` answer already captured in `openspec/config.yaml`'s `context:` block (populated by the `config-interview` component) and map it to discovery patterns for that technology. When the declared technology is not recognized, the gate SHALL fall back to a default pattern set and SHALL log that the technology was unrecognized, so that unconfigured resolution is not mistaken for enforcement.

#### Scenario: discovery follows the declared test technology
> **Tests:** `test_discovery_follows_declared_technology`
- **GIVEN** a project whose `openspec/config.yaml` `context:` block declares `Testing: pytest`
- **WHEN** `lint:specs` resolves a cited identifier
- **THEN** it discovers candidate tests using pytest patterns (for example `test_*` functions under the test tree) derived from that declared technology rather than a hard-coded stack

#### Scenario: unrecognized test technology falls back and is logged
> **Tests:** `test_unrecognized_technology_falls_back`, `test_unrecognized_technology_logged`
- **GIVEN** a project whose declared `Testing` answer matches no known technology mapping
- **WHEN** `lint:specs` runs
- **THEN** it applies the default discovery patterns and logs that the test technology was unrecognized rather than silently passing

#### Scenario: citation naming a nonexistent test fails
> **Tests:** `test_resolution_nonexistent_identifier_fails`
- **GIVEN** a scenario whose `> **Tests:**` line cites `test_does_not_exist`
- **WHEN** `lint:specs` runs and no test with that identifier is found in the test suite
- **THEN** the gate fails and reports the file, line, scenario, and the unresolved identifier `test_does_not_exist`

#### Scenario: citation naming a real test passes
> **Tests:** `test_resolution_real_function_name_passes`, `test_resolution_real_file_path_passes`
- **GIVEN** a scenario whose `> **Tests:**` line cites `test_query_follows_pagination` and that test exists in the suite
- **WHEN** `lint:specs` runs
- **THEN** the gate resolves the citation and does not report the scenario as a violation

#### Scenario: literal none is exempt from resolution
> **Tests:** `test_resolution_none_is_exempt`
- **GIVEN** a scenario whose `> **Tests:**` line is the literal `none`
- **WHEN** `lint:specs` runs
- **THEN** the gate does not attempt test resolution for that scenario and does not fail on resolution grounds

### Requirement: none exemptions SHALL be tracked and bounded
The `lint:specs` gate SHALL count scenarios that cite the literal `none` and report that count alongside the total scanned, so blanket use of `none` is visible rather than invisible. The gate SHALL support a configurable threshold on the share of `none` scenarios; when a threshold is configured and exceeded, the gate SHALL fail. When no threshold is configured, the gate SHALL report the count without failing on that basis.

#### Scenario: none count is reported
> **Tests:** `test_none_count_reported`
- **GIVEN** a set of scanned spec files containing some scenarios that cite `none`
- **WHEN** `lint:specs` runs successfully
- **THEN** the gate's output states how many scenarios cite `none` out of the total scanned

#### Scenario: exceeding the configured none threshold fails
> **Tests:** `test_none_threshold_exceeded_fails`
- **GIVEN** a configured maximum share of `none` scenarios and a spec set whose `none` share exceeds it
- **WHEN** `lint:specs` runs
- **THEN** the gate fails and states that the `none` share exceeded the configured threshold

#### Scenario: no threshold configured does not fail on none
> **Tests:** `test_no_threshold_does_not_fail_on_none`
- **GIVEN** no `none` threshold is configured for the project
- **WHEN** `lint:specs` runs over a spec set that includes `none` scenarios
- **THEN** the gate reports the `none` count and does not fail solely because of `none` usage
