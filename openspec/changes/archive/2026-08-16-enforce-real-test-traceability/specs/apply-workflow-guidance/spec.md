## ADDED Requirements

### Requirement: Apply session backfills concrete test citations
The project-local `spec-driven` schema clone's `apply` artifact instruction SHALL direct the agent, after implementing the tests that exercise a change's scenarios, to backfill the concrete test identifier(s) into each scenario's `> **Tests:**` line, replacing a placeholder `none` where a real test now exists. The instruction SHALL direct the agent to cite the actual test-function name or file path, and SHALL NOT direct the agent to leave `none` in place once a covering test has been written.

#### Scenario: real test citation replaces none after tests written
> **Tests:** none
- **GIVEN** an apply session in which the agent has written a test that exercises a scenario currently citing `> **Tests:** none`
- **WHEN** the agent follows the `apply` instruction after implementing that test
- **THEN** the agent updates that scenario's `> **Tests:**` line to cite the concrete test identifier rather than leaving `none`

#### Scenario: no covering test leaves none intact
> **Tests:** none
- **GIVEN** an apply session in which a scenario still has no test exercising it
- **WHEN** the agent follows the backfill instruction
- **THEN** the agent leaves that scenario's `> **Tests:**` line as `none` and does not fabricate a citation

### Requirement: Backfill guidance is additive
The added backfill instruction text SHALL be additive: it SHALL NOT remove or override the existing `apply` guidance to prompt for model downgrade, read context files, work pending tasks, mark them complete, and pause on blockers or when clarification is needed.

#### Scenario: existing apply directives preserved with backfill added
> **Tests:** none
- **GIVEN** the updated `apply` instruction carrying both the model-downgrade prompt and the test-citation backfill step
- **WHEN** an agent follows it during an apply session
- **THEN** the agent still prompts for model downgrade, reads context files, works pending tasks, marks them complete, pauses on blockers, and additionally backfills concrete test citations after writing tests
