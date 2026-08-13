# cost-tracker Specification

## Purpose

Defines how the cost-tracker component is installed and versioned within a scaffolded project.

## Requirements

### Requirement: Project-local installation
The cost-tracker SHALL be installed project-locally under `tokencost/`, with hooks pointing at the project copy and no global copy under `~/.claude/hooks/`.

#### Scenario: tokencost scaffolded in project
- **WHEN** the `cost-tracker` component is installed
- **THEN** the tracker script and a `cost.csv` are created under the project's `tokencost/` directory and the hooks reference that project-local path

### Requirement: Provenance stamp
The installed cost-tracker SHALL carry a provenance stamp identifying its component version so future drift is detectable.

#### Scenario: version stamp present
- **WHEN** the cost-tracker is installed
- **THEN** its files and manifest entry record the component version used to install them

### Requirement: ccusage runtime dependency
The cost-tracker component SHALL provision the `ccusage` CLI it depends on to resolve per-session cost, installing it globally via `pnpm` during component install. The component SHALL treat the `pnpm` install runtime as a precondition: when `pnpm` is unavailable it SHALL be classified BLOCKED and SHALL NOT install a tracker that cannot resolve cost.

#### Scenario: ccusage provisioned during install
- **WHEN** the `cost-tracker` component is installed and `pnpm` is available
- **THEN** the scaffold installs the `ccusage` CLI globally via `pnpm` so the tracker's `shutil.which("ccusage")` lookup resolves and cost is recorded in USD rather than `ERROR`

#### Scenario: blocked when runtime absent
- **WHEN** the `cost-tracker` component is evaluated and `pnpm` is not on PATH
- **THEN** the component is classified BLOCKED and `check`/`list`/`install` report the unmet `pnpm` precondition instead of installing a tracker that can only log `ERROR`
