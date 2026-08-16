## ADDED Requirements

### Requirement: Propose instruction ensures a change-scoped branch

The project-local `spec-driven` schema clone's `proposal` artifact instruction SHALL direct the agent, before creating any artifact, to ensure work happens on a dedicated non-trunk branch for the change (for example `change/<change-name>`). When the current branch is `main` or `master`, the instruction SHALL be a hard stop: the agent creates and switches to the change-scoped branch (or asks the user) and SHALL NOT write artifacts on `main`/`master`. When already on a non-trunk branch, the instruction SHALL direct the agent to confirm it is the intended branch for this change before proceeding.

#### Scenario: propose on trunk creates a branch first
> **Tests:** none
- **GIVEN** a propose session begins while the current branch is `main` or `master`
- **WHEN** the agent reads the `proposal` instruction and prepares to write the first artifact
- **THEN** the instruction directs the agent to create and switch to a change-scoped branch (or ask the user) before writing any artifact, and not to author artifacts on `main`/`master`

#### Scenario: propose on a feature branch confirms intent
> **Tests:** none
- **GIVEN** a propose session begins while a non-trunk branch is checked out
- **WHEN** the agent reads the `proposal` instruction
- **THEN** the instruction directs the agent to confirm the checked-out branch is the intended branch for this change before proceeding, rather than assuming it

### Requirement: Apply instruction refuses trunk and ensures a change-scoped branch

The project-local `spec-driven` schema clone's `apply` artifact instruction SHALL direct the agent, before working the first task, to ensure a dedicated non-trunk branch is checked out for the change. When the current branch is `main` or `master`, the instruction SHALL be a hard stop: the agent switches to (or creates) the change-scoped branch, or asks the user, and SHALL NOT edit project code or mark tasks on `main`/`master`.

#### Scenario: apply on trunk stops before task work
> **Tests:** none
- **GIVEN** an apply session begins while the current branch is `main` or `master`
- **WHEN** the agent reads the `apply` instruction and prepares to work the first task
- **THEN** the instruction directs the agent to switch to (or create) a change-scoped branch, or ask the user, before making any task edit, and not to apply on `main`/`master`

#### Scenario: apply on a change branch proceeds
> **Tests:** none
- **GIVEN** an apply session begins while a non-trunk branch scoped to the change is checked out
- **WHEN** the agent reads the `apply` instruction
- **THEN** the branch-isolation step is satisfied and the agent proceeds to work the task list without further branch action

### Requirement: Branch isolation is additive to existing instruction behavior

The branch-isolation text SHALL be additive: it SHALL NOT remove or override the existing `proposal` guidance to create the required artifacts, nor the existing `apply` guidance to prompt for model downgrade, read context files, work pending tasks, mark them complete, and pause on blockers or when clarification is needed.

#### Scenario: existing instruction directives preserved
> **Tests:** none
- **GIVEN** the updated `proposal` and `apply` instructions in the schema clone
- **WHEN** an agent follows them during propose and apply sessions
- **THEN** the agent still produces the required artifacts on propose, and on apply still surfaces the model-downgrade prompt, reads context files, works pending tasks, marks them complete, and pauses on blockers or when clarification is needed
