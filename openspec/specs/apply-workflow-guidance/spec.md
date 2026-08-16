# apply-workflow-guidance Specification

## Purpose

Defines project-local behavior baked into the `spec-driven` schema clone's `apply` instruction — starting with the once-per-session model-downgrade prompt.

## Requirements

### Requirement: Apply session prompts for model downgrade

The project-local `spec-driven` schema clone's `apply` artifact instruction SHALL direct the agent to prompt the user, once per apply session and before working any task, about downgrading the implementation model (for example Opus to Sonnet) because applying tasks is largely mechanical. The instruction SHALL state that the agent cannot switch models itself and SHALL direct the user to run `/model` (or `/fast`) to downgrade. The instruction SHALL require the agent to halt after asking: it SHALL NOT read context files, work any task, or make any edits in the same turn as the prompt, and SHALL wait for the user's answer before proceeding.

#### Scenario: prompt appears once before task work
> **Tests:** none
- **GIVEN** an apply session begins for a change whose tasks are not yet complete
- **WHEN** the agent reads the `apply` instruction and prepares to work the first task
- **THEN** the agent asks the user whether to downgrade the implementation model before making any task edits

#### Scenario: agent halts and waits after prompting
> **Tests:** none
- **GIVEN** the agent has surfaced the model-downgrade prompt in an apply session
- **WHEN** the same turn continues
- **THEN** the agent does not read context files, work any task, or make any edits in that turn, and instead ends its turn waiting for the user's answer

#### Scenario: agent defers the switch to the user
> **Tests:** none
- **GIVEN** the agent has surfaced the model-downgrade prompt
- **WHEN** the user wants the downgrade
- **THEN** the instruction has told the user to run `/model` (or `/fast`) rather than implying the agent switches the model itself, and the agent waits for the user's choice before proceeding

#### Scenario: no re-prompt after asked or declined
> **Tests:** none
- **GIVEN** the model-downgrade prompt has already been shown once in the current apply session
- **WHEN** the agent continues to subsequent tasks in the same session
- **THEN** the agent does not prompt about the model again and continues working the task list

### Requirement: Downgrade prompt does not weaken existing apply behavior

The added instruction text SHALL be additive: it SHALL NOT remove or override the existing directive to read context files, work through pending tasks, mark them complete, and pause on blockers or when clarification is needed.

#### Scenario: existing apply directives preserved
> **Tests:** none
- **GIVEN** the updated `apply` instruction in the schema clone
- **WHEN** an agent follows it during an apply session, after the user has answered the downgrade prompt
- **THEN** the agent still reads context files, works pending tasks, marks them complete, and pauses on blockers or when clarification is needed
