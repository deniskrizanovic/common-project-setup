## ADDED Requirements

### Requirement: Three-layer scenario enforcement
The scaffold SHALL enforce that every spec scenario carries a `> **Tests:**` line and a `- **GIVEN**` clause at three layers: the schema instruction (author-time), a lint gate, and the commit-gate hook.

#### Scenario: schema instruction directs authors
- **WHEN** the traceability component is installed
- **THEN** the project's `specs` schema instruction requires a `> **Tests:**` line and a `- **GIVEN**` clause on every `#### Scenario:`

#### Scenario: missing test line fails lint
- **WHEN** a scenario lacks a `> **Tests:**` line (the literal word `none` is allowed)
- **THEN** the `lint:specs` gate fails

#### Scenario: missing given clause fails lint
- **WHEN** a scenario lacks a `- **GIVEN**` clause
- **THEN** the `lint:given` gate fails

### Requirement: Silence is not permitted
The traceability gate SHALL treat an absent `> **Tests:**` line as a failure rather than a pass, since an absent line is indistinguishable from an overlooked one.

#### Scenario: absent line is not a pass
- **WHEN** a scenario has neither a test citation nor the literal `none`
- **THEN** the gate reports a violation rather than silently passing
